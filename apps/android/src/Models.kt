package com.netscope.app

/**
 * Probe result types, mirroring the Python core's result models
 * (dnsprobe / tcpprobe / tlsprobe / httpprobe) and the shared JSON
 * Schema contract in shared/schemas/. Pure JVM — no Android APIs —
 * so the classifier and rules built on these types are covered by
 * the JVM unit tests in tests/.
 */

object VerdictCodes {
    const val OK = "OK"
    const val DNS_POISONED = "DNS_POISONED"
    const val DNS_BLOCKED = "DNS_BLOCKED"
    const val TCP_BLOCKED = "TCP_BLOCKED"
    const val TLS_SNI_BLOCKED = "TLS_SNI_BLOCKED"
    const val HTTP_FILTERED = "HTTP_FILTERED"
    const val SERVER_DOWN = "SERVER_DOWN"
    const val NETWORK_UNREACHABLE = "NETWORK_UNREACHABLE"
    const val SLOW_UNSTABLE = "SLOW_UNSTABLE"
    const val UNKNOWN = "UNKNOWN"

    val ALL = listOf(
        OK, DNS_POISONED, DNS_BLOCKED, TCP_BLOCKED, TLS_SNI_BLOCKED,
        HTTP_FILTERED, SERVER_DOWN, NETWORK_UNREACHABLE, SLOW_UNSTABLE, UNKNOWN
    )
}

data class Verdict(val code: String, val explanation: String, val confidence: String)

// ---------------------------------------------------------------------------
// DNS results (mirror of dnsprobe.ResolverResult / DNSReport)
// ---------------------------------------------------------------------------

data class ResolverResult(
    val resolver: String,
    val status: String, // ok | nxdomain | servfail | refused | timeout | error
    val addresses: List<String> = emptyList(),
    val latencyMs: Double? = null,
    val error: String? = null
)

class DnsReport(val hostname: String) {
    var systemAddresses: List<String> = emptyList()
    var systemError: String? = null
    var systemLatencyMs: Double? = null
    var resolvers: List<ResolverResult> = emptyList()
    var suspectPoisoning: Boolean = false
    var partialNxdomain: Boolean = false

    /** Best available addresses: system resolver first, then public ones. */
    val resolvedAddresses: List<String>
        get() {
            if (systemAddresses.isNotEmpty()) return systemAddresses.toList()
            for (result in resolvers) {
                if (result.status == "ok" && result.addresses.isNotEmpty()) {
                    return result.addresses.toList()
                }
            }
            return emptyList()
        }
}

// ---------------------------------------------------------------------------
// TCP results (mirror of tcpprobe.Attempt / TCPResult)
// ---------------------------------------------------------------------------

data class TcpAttempt(
    val ok: Boolean,
    val latencyMs: Double? = null,
    val errorKind: String? = null,
    val error: String? = null
)

class TcpResult(val target: String, val port: Int, val attempts: List<TcpAttempt>) {

    val successes: Int
        get() = attempts.count { it.ok }

    val lossPct: Double
        get() = if (attempts.isEmpty()) 100.0
        else 100.0 * (attempts.size - successes) / attempts.size

    val avgLatencyMs: Double?
        get() {
            val values = successfulLatencies
            return if (values.isEmpty()) null else values.average()
        }

    /** Latencies of the successful attempts, in attempt order. */
    val successfulLatencies: List<Double>
        get() = attempts.filter { it.ok && it.latencyMs != null }.map { it.latencyMs!! }

    /** Full shared-definition statistics over the successful attempts. */
    val latency: LatencyStats
        get() = latencyStats(successfulLatencies)

    val dominantError: String?
        get() {
            val counts = LinkedHashMap<String, Int>()
            for (attempt in attempts) {
                val kind = attempt.errorKind
                if (!attempt.ok && kind != null) counts[kind] = (counts[kind] ?: 0) + 1
            }
            if (counts.isEmpty()) return null
            return counts.maxByOrNull { it.value }?.key
        }
}

// ---------------------------------------------------------------------------
// TLS result (mirror of tlsprobe.TLSResult)
// ---------------------------------------------------------------------------

data class TlsResult(
    val hostname: String,
    val target: String,
    val port: Int = 443,
    val ok: Boolean = false,
    val protocol: String? = null,
    val certSubject: String? = null,
    val certIssuer: String? = null,
    val certNotAfter: String? = null,
    val connectMs: Double? = null,
    val handshakeMs: Double? = null,
    val failedPhase: String? = null, // "connect" | "handshake"
    val errorKind: String? = null, // reset | timeout | refused | unreachable | certificate | protocol | error
    val error: String? = null
)

// ---------------------------------------------------------------------------
// HTTP result (mirror of httpprobe.HTTPResult)
// ---------------------------------------------------------------------------

data class HttpResult(
    val scheme: String,
    val url: String,
    val ok: Boolean = false, // true when an HTTP response was received at all
    val status: Int? = null,
    val reason: String? = null,
    val finalUrl: String? = null,
    val redirects: Int = 0,
    val sizeBytes: Int = 0,
    val bodySha256: String? = null,
    val markers: List<String> = emptyList(),
    val latencyMs: Double? = null,
    val errorKind: String? = null,
    val error: String? = null
) {
    /** Host of the final URL after redirects, when it can be read. */
    val finalHost: String?
        get() = try {
            java.net.URI(finalUrl ?: url).host?.lowercase()
        } catch (exc: Exception) {
            null
        }
}

// ---------------------------------------------------------------------------
// Aggregate (mirror of models.HostReport)
// ---------------------------------------------------------------------------

class HostReport(
    val host: String,
    val dns: DnsReport,
    val tcp: Map<Int, TcpResult>,
    val tls: TlsResult?,
    val http: Map<String, HttpResult>,
    val verdict: Verdict
)
