package com.netscope.app

import java.util.Locale

/**
 * The verdict classifier, a port of the Python core's
 * verdict.classify. It is a pure function of the probe results: it
 * walks the layers in the order a connection is actually built
 * (DNS, TCP, TLS, HTTP) and returns the first layer that explains
 * the failure, with a plain-language explanation and a confidence
 * level. Pure JVM — no Android APIs — so it is covered by the JVM
 * unit tests in tests/.
 */

private fun fmt0(value: Double): String = String.format(Locale.US, "%.0f", value)

fun classify(
    dns: DnsReport,
    tcp: Map<Int, TcpResult>,
    tls: TlsResult?,
    http: Map<String, HttpResult>
): Verdict {
    // ---- DNS layer -------------------------------------------------------
    if (dns.suspectPoisoning) {
        return Verdict(
            VerdictCodes.DNS_POISONED,
            "Your resolver returns addresses that no public resolver returns. " +
                "The DNS answer has likely been forged or hijacked on this network.",
            "high"
        )
    }

    val systemOk = dns.systemAddresses.isNotEmpty()
    val publicOk = dns.resolvers.any { it.status == "ok" && it.addresses.isNotEmpty() }
    if (!systemOk) {
        if (publicOk) {
            return Verdict(
                VerdictCodes.DNS_BLOCKED,
                "Your normal (system) resolver cannot resolve this name, but " +
                    "public resolvers can. DNS is being blocked or filtered locally.",
                "high"
            )
        }
        val statuses = dns.resolvers.map { it.status }
        if (statuses.isNotEmpty() && statuses.all { it == "nxdomain" }) {
            return Verdict(
                VerdictCodes.DNS_BLOCKED,
                "Every resolver says this name does not exist (NXDOMAIN). " +
                    "Either the domain really does not exist, or DNS answers are being forged.",
                "medium"
            )
        }
        if (statuses.isNotEmpty() && statuses.all { it == "timeout" || it == "error" }) {
            return Verdict(
                VerdictCodes.NETWORK_UNREACHABLE,
                "Nothing answers DNS queries at all — not the system resolver " +
                    "and not any public resolver. The network path itself looks broken.",
                "medium"
            )
        }
        return Verdict(
            VerdictCodes.UNKNOWN,
            "DNS resolution failed in inconsistent ways across resolvers, " +
                "so no single cause can be named.",
            "low"
        )
    }

    // ---- TCP layer -------------------------------------------------------
    val tcp443 = tcp[443]
    val tcp80 = tcp[80]
    val dead443 = tcp443 != null && tcp443.successes == 0
    val dead80 = tcp80 != null && tcp80.successes == 0

    if (dead443 && dead80) {
        val errors = setOf(tcp443!!.dominantError, tcp80!!.dominantError)
        if (errors == setOf("refused")) {
            return Verdict(
                VerdictCodes.SERVER_DOWN,
                "The host is reachable but refuses connections on ports 443 " +
                    "and 80. The server is most likely down or not running a web service.",
                "medium"
            )
        }
        if ("unreachable" in errors) {
            return Verdict(
                VerdictCodes.NETWORK_UNREACHABLE,
                "The network reports the host as unreachable. There is no " +
                    "working route to it from here.",
                "high"
            )
        }
        if (errors == setOf("reset")) {
            return Verdict(
                VerdictCodes.TCP_BLOCKED,
                "Connections are actively reset on both web ports. Something " +
                    "on the path is tearing connections down.",
                "high"
            )
        }
        if (errors == setOf("timeout")) {
            return Verdict(
                VerdictCodes.TCP_BLOCKED,
                "Connections to both web ports time out without an answer. " +
                    "Packets are most likely being dropped on the path.",
                "medium"
            )
        }
        return Verdict(
            VerdictCodes.TCP_BLOCKED,
            "Connections fail on both web ports with mixed errors " +
                "(${errors.filterNotNull().sorted().joinToString(", ")}).",
            "low"
        )
    }

    if (dead443 && tcp80 != null && tcp80.successes > 0) {
        val kind = tcp443!!.dominantError
        if (kind == "reset") {
            return Verdict(
                VerdictCodes.TCP_BLOCKED,
                "Port 443 connections are reset while port 80 works. " +
                    "HTTPS traffic to this host appears to be blocked specifically.",
                "high"
            )
        }
        return Verdict(
            VerdictCodes.TCP_BLOCKED,
            "Port 443 is unreachable while port 80 works, so the secure " +
                "version of the site cannot be used from this network.",
            "medium"
        )
    }

    // ---- TLS layer -------------------------------------------------------
    if (tls != null && !tls.ok && tcp443 != null && tcp443.successes > 0) {
        if (tls.failedPhase == "handshake") {
            when (tls.errorKind) {
                "reset" -> return Verdict(
                    VerdictCodes.TLS_SNI_BLOCKED,
                    "The TCP connection opens, but the TLS handshake is reset " +
                        "as soon as the site name (SNI) is sent. This is the " +
                        "signature of SNI-based filtering.",
                    "high"
                )
                "timeout" -> return Verdict(
                    VerdictCodes.TLS_SNI_BLOCKED,
                    "The TCP connection opens, but the TLS handshake never " +
                        "completes. The site name (SNI) is the only new " +
                        "information at that point, so name-based filtering is likely.",
                    "medium"
                )
                "certificate" -> return Verdict(
                    VerdictCodes.UNKNOWN,
                    "The TLS handshake fails certificate validation " +
                        "(${tls.error}). The certificate may be expired or " +
                        "misconfigured, or the connection may be intercepted.",
                    "medium"
                )
                else -> return Verdict(
                    VerdictCodes.UNKNOWN,
                    "The TLS handshake fails (${tls.errorKind}: ${tls.error}).",
                    "low"
                )
            }
        }
    }

    // ---- HTTP layer ------------------------------------------------------
    val https = http["https"]
    val plain = http["http"]

    if (https != null && https.ok) {
        if (https.markers.isNotEmpty()) {
            return Verdict(
                VerdictCodes.HTTP_FILTERED,
                "The page that comes back is a block page, not the site: it " +
                    "contains filtering markers (${https.markers.joinToString(", ")}).",
                "high"
            )
        }
        if (https.status == 451) {
            return Verdict(
                VerdictCodes.HTTP_FILTERED,
                "The server answers with HTTP 451 (Unavailable For Legal " +
                    "Reasons): the content is being withheld on this network or " +
                    "for this region.",
                "medium"
            )
        }
        // The site answers over HTTPS. Remaining question: how well?
        if (tcp443 != null && tcp443.lossPct >= 50.0) {
            return Verdict(
                VerdictCodes.SLOW_UNSTABLE,
                "The site loads, but ${fmt0(tcp443.lossPct)}% of connection " +
                    "attempts failed. The connection is unstable.",
                "medium"
            )
        }
        if (tcp443 != null && (tcp443.lossPct >= 25.0 || (tcp443.avgLatencyMs ?: 0.0) > 400.0)) {
            return Verdict(
                VerdictCodes.SLOW_UNSTABLE,
                "The site loads, but connections are slow or intermittently " +
                    "failing (loss ${fmt0(tcp443.lossPct)}%, average connect " +
                    "${fmt0(tcp443.avgLatencyMs ?: 0.0)} ms).",
                "low"
            )
        }
        return Verdict(VerdictCodes.OK, "The site loads normally from this network.", "high")
    }

    if (plain != null && plain.ok && plain.markers.isNotEmpty()) {
        return Verdict(
            VerdictCodes.HTTP_FILTERED,
            "The plain-HTTP page that comes back is a block page: it " +
                "contains filtering markers (${plain.markers.joinToString(", ")}).",
            "medium"
        )
    }
    if (plain != null && plain.status == 451) {
        return Verdict(
            VerdictCodes.HTTP_FILTERED,
            "The server answers with HTTP 451 (Unavailable For Legal " +
                "Reasons) over plain HTTP.",
            "medium"
        )
    }

    if (https != null && !https.ok && https.errorKind == "reset" && tls != null && tls.ok) {
        return Verdict(
            VerdictCodes.HTTP_FILTERED,
            "TLS connects, but the connection is reset while the page is " +
                "being fetched — filtering that inspects the request itself.",
            "medium"
        )
    }

    if (https != null && !https.ok &&
        plain != null && !plain.ok &&
        tcp443 != null && tcp443.successes > 0
    ) {
        return Verdict(
            VerdictCodes.SERVER_DOWN,
            "The host accepts TCP connections but never answers HTTP or " +
                "HTTPS requests. The web service itself looks down.",
            "medium"
        )
    }

    return Verdict(
        VerdictCodes.UNKNOWN,
        "The probes did not produce a consistent explanation. The " +
            "detailed results above are the evidence to work from.",
        "low"
    )
}
