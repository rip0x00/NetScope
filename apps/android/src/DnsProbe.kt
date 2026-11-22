package com.netscope.app

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import kotlin.random.Random

/**
 * DNS probing, a port of the core's dnsprobe.
 *
 * DNS is looked at from two directions: what the operating system's
 * resolver returns (InetAddress), and what public resolvers return
 * when asked directly with the hand-built wire-format queries from
 * DnsWire.kt (UDP port 53). Disagreement between the two views is
 * the signal this module exists to surface.
 */

val DEFAULT_RESOLVERS = listOf("1.1.1.1", "8.8.8.8", "9.9.9.9")

private class QueryOutcome(val message: DnsMessage, val latencyMs: Double)

private fun queryUdp(resolver: String, hostname: String, qtype: Int, timeoutSec: Double): QueryOutcome {
    val txid = Random.nextInt(0, 65536)
    val packet = buildQuery(hostname, qtype, txid)
    val socket = DatagramSocket()
    try {
        socket.soTimeout = (timeoutSec * 1000).toInt()
        val start = System.nanoTime()
        socket.send(DatagramPacket(packet, packet.size, InetAddress.getByName(resolver), 53))
        val buffer = ByteArray(4096)
        while (true) {
            val response = DatagramPacket(buffer, buffer.size)
            socket.receive(response)
            val data = buffer.copyOf(response.length)
            if (data.size >= 2 && ((data[0].toInt() and 0xFF) shl 8 or (data[1].toInt() and 0xFF)) == txid) {
                val latencyMs = (System.nanoTime() - start) / 1_000_000.0
                return QueryOutcome(parseResponse(data), latencyMs)
            }
        }
    } finally {
        socket.close()
    }
}

/** Ask one public resolver for a host's addresses over UDP/53. */
fun queryResolver(resolver: String, hostname: String, timeoutSec: Double = 4.0): ResolverResult {
    val outcome = try {
        queryUdp(resolver, hostname, QTYPE_A, timeoutSec)
    } catch (exc: SocketTimeoutException) {
        return ResolverResult(resolver = resolver, status = "timeout")
    } catch (exc: Exception) {
        return ResolverResult(resolver = resolver, status = "error", error = exc.message)
    }
    val message = outcome.message
    return when (message.rcode) {
        3 -> ResolverResult(resolver = resolver, status = "nxdomain", latencyMs = outcome.latencyMs)
        2 -> ResolverResult(resolver = resolver, status = "servfail", latencyMs = outcome.latencyMs)
        5 -> ResolverResult(resolver = resolver, status = "refused", latencyMs = outcome.latencyMs)
        0 -> {
            var addresses = message.addressesFor(hostname)
            if (addresses.isEmpty()) {
                // No A records (for example a bare CNAME target or an
                // IPv6-only host); try AAAA before giving up.
                try {
                    val message6 = queryUdp(resolver, hostname, QTYPE_AAAA, timeoutSec).message
                    if (message6.rcode == 0) addresses = message6.addressesFor(hostname)
                } catch (ignored: Exception) {
                    // Keep the empty A result.
                }
            }
            ResolverResult(
                resolver = resolver, status = "ok",
                addresses = addresses, latencyMs = outcome.latencyMs
            )
        }
        else -> ResolverResult(
            resolver = resolver, status = "error", latencyMs = outcome.latencyMs,
            error = "unexpected rcode ${message.rcodeName}"
        )
    }
}

// ---------------------------------------------------------------------------
// Arbitrary record lookup (Tools)
// ---------------------------------------------------------------------------

/** Outcome of one wire-format lookup of an arbitrary record type. */
class DnsLookupOutcome(
    val resolver: String,
    val qname: String,
    val qtypeName: String,
    val status: String, // ok | nxdomain | servfail | refused | timeout | error
    val records: List<DnsRecord> = emptyList(),
    val authority: List<DnsRecord> = emptyList(),
    val latencyMs: Double? = null,
    val error: String? = null
)

/** Query [resolver] for [qtype] records of [name] over UDP/53. */
fun lookupRecords(
    resolver: String,
    name: String,
    qtype: Int,
    timeoutSec: Double = 5.0
): DnsLookupOutcome {
    val typeName = when (qtype) {
        QTYPE_A -> "A"
        QTYPE_NS -> "NS"
        QTYPE_CNAME -> "CNAME"
        QTYPE_SOA -> "SOA"
        QTYPE_PTR -> "PTR"
        QTYPE_MX -> "MX"
        QTYPE_TXT -> "TXT"
        QTYPE_AAAA -> "AAAA"
        QTYPE_SRV -> "SRV"
        QTYPE_CAA -> "CAA"
        else -> "TYPE$qtype"
    }
    val outcome = try {
        queryUdp(resolver, name, qtype, timeoutSec)
    } catch (exc: SocketTimeoutException) {
        return DnsLookupOutcome(resolver, name, typeName, "timeout")
    } catch (exc: Exception) {
        return DnsLookupOutcome(resolver, name, typeName, "error", error = exc.message)
    }
    val message = outcome.message
    val status = when (message.rcode) {
        0 -> "ok"
        3 -> "nxdomain"
        2 -> "servfail"
        5 -> "refused"
        else -> "error"
    }
    return DnsLookupOutcome(
        resolver = resolver,
        qname = name,
        qtypeName = typeName,
        status = status,
        records = message.answers,
        authority = message.authority,
        latencyMs = outcome.latencyMs,
        error = if (status == "error") "unexpected rcode ${message.rcodeName}" else null
    )
}

/** Reverse-lookup name for an IPv4 address ("1.2.3.4" → "4.3.2.1.in-addr.arpa"). */
fun reverseNameForIpv4(ip: String): String? {
    val parts = ip.trim().split(".")
    if (parts.size != 4) return null
    if (parts.any { part -> part.toIntOrNull() !in 0..255 }) return null
    return parts.reversed().joinToString(".") + ".in-addr.arpa"
}

// ---------------------------------------------------------------------------
// System resolution + comparison report
// ---------------------------------------------------------------------------

private class SystemOutcome(
    val addresses: List<String>,
    val error: String?,
    val latencyMs: Double
)

private fun systemResolve(hostname: String): SystemOutcome {
    val start = System.nanoTime()
    return try {
        val addresses = InetAddress.getAllByName(hostname).map { it.hostAddress ?: it.toString() }
        val unique = addresses.distinct()
        SystemOutcome(unique, null, (System.nanoTime() - start) / 1_000_000.0)
    } catch (exc: UnknownHostException) {
        SystemOutcome(emptyList(), exc.message, (System.nanoTime() - start) / 1_000_000.0)
    } catch (exc: Exception) {
        SystemOutcome(emptyList(), exc.message, (System.nanoTime() - start) / 1_000_000.0)
    }
}

/** Timed system resolution, exposed for the Overview DNS status line. */
fun systemResolveTimed(hostname: String): Triple<List<String>, String?, Double> {
    val outcome = systemResolve(hostname)
    return Triple(outcome.addresses, outcome.error, outcome.latencyMs)
}

/** Resolve [hostname] via the system resolver and public resolvers. */
fun probeDns(
    hostname: String,
    resolvers: List<String> = DEFAULT_RESOLVERS,
    timeoutSec: Double = 4.0
): DnsReport {
    val report = DnsReport(hostname)
    val system = systemResolve(hostname)
    report.systemAddresses = system.addresses
    report.systemError = system.error
    report.systemLatencyMs = system.latencyMs
    report.resolvers = resolvers.map { queryResolver(it, hostname, timeoutSec) }

    val okSets = report.resolvers
        .filter { it.status == "ok" && it.addresses.isNotEmpty() }
        .map { it.addresses.toSet() }
    if (system.addresses.isNotEmpty() && okSets.isNotEmpty()) {
        val systemSet = system.addresses.toSet()
        if (okSets.all { public -> systemSet.intersect(public).isEmpty() }) {
            report.suspectPoisoning = true
        }
    }

    val statuses = report.resolvers.map { it.status }.toSet()
    if ("nxdomain" in statuses && "ok" in statuses) {
        report.partialNxdomain = true
    }
    return report
}
