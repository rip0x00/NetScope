package com.netscope.app

import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket
import java.security.cert.X509Certificate
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.TimeUnit
import javax.net.ssl.SNIHostName
import javax.net.ssl.SSLException
import javax.net.ssl.SSLSocket
import javax.net.ssl.SSLSocketFactory
import javax.security.auth.x500.X500Principal

/**
 * TLS handshake probing, a port of the core's tlsprobe.
 *
 * The connect phase and the handshake phase are timed and reported
 * separately. A connection that is accepted at TCP level and then
 * reset during the handshake — after the ClientHello, which carries
 * the server name (SNI) — is the classic signature of SNI-based
 * filtering.
 */

private fun formatCertDate(date: Date): String {
    // Match the shape of Python's getpeercert() date strings,
    // e.g. "Nov 12 23:59:59 2027 GMT".
    val format = SimpleDateFormat("MMM dd HH:mm:ss yyyy 'GMT'", Locale.US)
    format.timeZone = TimeZone.getTimeZone("UTC")
    return format.format(date)
}

private fun formatPrincipal(principal: X500Principal): String =
    // RFC 2253 gives "CN=example.com,O=Example Inc"; the Python core
    // prints the same attributes joined with ", ".
    principal.getName(X500Principal.RFC2253).replace(",", ", ")

private class HandshakeOutcome(
    val tls: SSLSocket,
    val connectMs: Double,
    val handshakeMs: Double,
    val cert: X509Certificate?
)

private fun openTls(
    hostname: String,
    connectTarget: String,
    port: Int,
    timeoutMs: Int
): HandshakeOutcome {
    val raw = Socket()
    val connectStart = System.nanoTime()
    try {
        raw.connect(InetSocketAddress(connectTarget, port), timeoutMs)
    } catch (exc: IOException) {
        closeQuietly(raw)
        throw TlsConnectException(exc)
    }
    val connectMs = (System.nanoTime() - connectStart) / 1_000_000.0

    raw.soTimeout = timeoutMs
    val factory = SSLSocketFactory.getDefault() as SSLSocketFactory
    val tls = factory.createSocket(raw, hostname, port, true) as SSLSocket
    tls.soTimeout = timeoutMs
    val params = tls.sslParameters
    params.serverNames = listOf(SNIHostName(hostname))
    tls.sslParameters = params

    val handshakeStart = System.nanoTime()
    try {
        tls.startHandshake()
    } catch (exc: IOException) {
        closeQuietly(tls)
        throw TlsHandshakeException(exc, connectMs)
    }
    val handshakeMs = (System.nanoTime() - handshakeStart) / 1_000_000.0
    val cert = tls.session.peerCertificates.firstOrNull() as? X509Certificate
    return HandshakeOutcome(tls, connectMs, handshakeMs, cert)
}

private class TlsConnectException(val io: IOException) : Exception(io.message)
private class TlsHandshakeException(val io: IOException, val connectMs: Double) :
    Exception(io.message)

/** Run one TLS handshake with SNI set to [hostname]. */
fun probeTls(
    hostname: String,
    target: String? = null,
    port: Int = 443,
    timeoutSec: Double = 6.0
): TlsResult {
    val connectTarget = target ?: hostname
    val timeoutMs = (timeoutSec * 1000).toInt()
    val outcome = try {
        openTls(hostname, connectTarget, port, timeoutMs)
    } catch (exc: TlsConnectException) {
        return TlsResult(
            hostname = hostname, target = connectTarget, port = port,
            failedPhase = "connect",
            errorKind = classifySocketError(exc.io), error = exc.io.message
        )
    } catch (exc: TlsHandshakeException) {
        val io = exc.io
        val kind = when {
            io is SSLException && hasCertificateCause(io) -> "certificate"
            io is SSLException -> "protocol"
            else -> classifySocketError(io)
        }
        return TlsResult(
            hostname = hostname, target = connectTarget, port = port,
            connectMs = exc.connectMs,
            failedPhase = "handshake", errorKind = kind, error = io.message
        )
    }
    val session = outcome.tls.session
    val cert = outcome.cert
    val result = TlsResult(
        hostname = hostname, target = connectTarget, port = port,
        ok = true,
        protocol = session.protocol,
        certSubject = cert?.let { formatPrincipal(it.subjectX500Principal) },
        certIssuer = cert?.let { formatPrincipal(it.issuerX500Principal) },
        certNotAfter = cert?.let { formatCertDate(it.notAfter) },
        connectMs = outcome.connectMs,
        handshakeMs = outcome.handshakeMs
    )
    closeQuietly(outcome.tls)
    return result
}

// ---------------------------------------------------------------------------
// Certificate inspection (Tools)
// ---------------------------------------------------------------------------

/** Detailed certificate view for the TLS inspector tool. */
class TlsInfo(
    val hostname: String,
    val ok: Boolean,
    val protocol: String? = null,
    val cipherSuite: String? = null,
    val subject: String? = null,
    val issuer: String? = null,
    val notBefore: String? = null,
    val notAfter: String? = null,
    val daysRemaining: Long? = null,
    val errorKind: String? = null,
    val error: String? = null
)

/** Connect to [hostname]:443 and report the peer certificate in detail. */
fun inspectTls(hostname: String, port: Int = 443, timeoutSec: Double = 8.0): TlsInfo {
    val timeoutMs = (timeoutSec * 1000).toInt()
    val outcome = try {
        openTls(hostname, hostname, port, timeoutMs)
    } catch (exc: TlsConnectException) {
        return TlsInfo(
            hostname = hostname, ok = false,
            errorKind = classifySocketError(exc.io), error = exc.io.message
        )
    } catch (exc: TlsHandshakeException) {
        val io = exc.io
        val kind = when {
            io is SSLException && hasCertificateCause(io) -> "certificate"
            io is SSLException -> "protocol"
            else -> classifySocketError(io)
        }
        return TlsInfo(hostname = hostname, ok = false, errorKind = kind, error = io.message)
    }
    val session = outcome.tls.session
    val cert = outcome.cert
    val now = System.currentTimeMillis()
    val days = cert?.let {
        TimeUnit.MILLISECONDS.toDays(it.notAfter.time - now)
    }
    val info = TlsInfo(
        hostname = hostname,
        ok = true,
        protocol = session.protocol,
        cipherSuite = session.cipherSuite,
        subject = cert?.let { formatPrincipal(it.subjectX500Principal) },
        issuer = cert?.let { formatPrincipal(it.issuerX500Principal) },
        notBefore = cert?.let { formatCertDate(it.notBefore) },
        notAfter = cert?.let { formatCertDate(it.notAfter) },
        daysRemaining = days
    )
    closeQuietly(outcome.tls)
    return info
}

private fun closeQuietly(socket: Socket) {
    try {
        socket.close()
    } catch (ignored: IOException) {
        // Nothing useful to do about a failed close.
    }
}
