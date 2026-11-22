package com.netscope.app

import java.net.URI
import java.util.Locale

/**
 * Check orchestration and text formatting.
 *
 * The report layout matches the CLI's text output for the same
 * host, extended with the troubleshooting findings (spec Part 17:
 * facts, possible causes and recommendations kept separate). The
 * Share action sends exactly this text.
 */

/** Extract a bare hostname from a host or URL argument. */
fun parseTarget(raw: String): String {
    val text = raw.trim()
    val host = if ("://" in text) {
        try {
            URI(text).host ?: ""
        } catch (exc: Exception) {
            ""
        }
    } else {
        text.split("/")[0].split(":")[0]
    }
    val cleaned = host.trim().trim('.').lowercase()
    require(cleaned.isNotEmpty() && ' ' !in cleaned && '/' !in cleaned) {
        "could not read a hostname from '$raw'"
    }
    return cleaned
}

/** Run all probe layers for one host and classify the outcome. */
fun runChecks(host: String, resolvers: List<String> = DEFAULT_RESOLVERS): HostReport {
    val dns = probeDns(host, resolvers)
    val target = dns.resolvedAddresses.firstOrNull { ":" !in it }
    val connectTarget = target ?: host
    val tcp = mapOf(
        443 to probeTcp(connectTarget, 443),
        80 to probeTcp(connectTarget, 80)
    )
    val tls = probeTls(host, target)
    val http = mapOf(
        "https" to probeHttp(host, "https"),
        "http" to probeHttp(host, "http")
    )
    val verdict = classify(dns, tcp, tls, http)
    return HostReport(host, dns, tcp, tls, http, verdict)
}

// ---------------------------------------------------------------------------
// Text output (same layout as the CLI, plus the findings section)
// ---------------------------------------------------------------------------

private fun ms(value: Double?): String =
    if (value != null) String.format(Locale.US, "%.0f ms", value) else "n/a"

private fun line(label: String, value: String): String = "  " + label.padEnd(16) + value

fun formatReport(report: HostReport): String {
    val out = StringBuilder()
    out.appendLine("Target: ${report.host}")
    out.appendLine()
    out.appendLine("DNS")
    val dns = report.dns
    val systemValue = if (dns.systemAddresses.isNotEmpty()) {
        dns.systemAddresses.joinToString(", ") + " (${ms(dns.systemLatencyMs)})"
    } else {
        "failed (${dns.systemError ?: "no answer"})"
    }
    out.appendLine(line("system", systemValue))
    for (resolver in dns.resolvers) {
        val value = when {
            resolver.status == "ok" -> {
                val addresses =
                    if (resolver.addresses.isNotEmpty()) resolver.addresses.joinToString(", ")
                    else "no addresses returned"
                "$addresses (${ms(resolver.latencyMs)})"
            }
            resolver.status == "nxdomain" -> "NXDOMAIN"
            resolver.status == "timeout" -> "timeout"
            else -> resolver.error ?: resolver.status
        }
        out.appendLine(line(resolver.resolver, value))
    }
    if (dns.suspectPoisoning) {
        out.appendLine(line("", "note: system answer disagrees with every public resolver"))
    }
    out.appendLine()
    out.appendLine("TCP")
    for (port in listOf(443, 80)) {
        val result = report.tcp.getValue(port)
        val total = result.attempts.size
        val value = if (result.successes > 0) {
            var text = "${result.successes}/$total connected, avg ${ms(result.avgLatencyMs)}"
            if (result.lossPct != 0.0) {
                text += String.format(Locale.US, ", %.0f%% loss", result.lossPct)
            }
            text
        } else {
            "0/$total connected (${result.dominantError ?: "error"})"
        }
        out.appendLine(line("port $port", value))
    }
    out.appendLine()
    out.appendLine("TLS")
    val tls = report.tls
    if (tls == null) {
        out.appendLine(line("handshake", "not attempted"))
    } else if (tls.ok) {
        out.appendLine(line("handshake", "OK (${tls.protocol}, ${ms(tls.handshakeMs)})"))
        out.appendLine(line("certificate", "subject: ${tls.certSubject}"))
        out.appendLine(line("", "issuer: ${tls.certIssuer}"))
        out.appendLine(line("", "expires: ${tls.certNotAfter}"))
    } else {
        out.appendLine(line("handshake", "failed in ${tls.failedPhase} phase (${tls.errorKind})"))
    }
    out.appendLine()
    out.appendLine("HTTP")
    for (scheme in listOf("https", "http")) {
        val result = report.http.getValue(scheme)
        val value = if (result.ok) {
            var text = String.format(
                Locale.US, "%d %s, %,d bytes, %d redirects",
                result.status, result.reason ?: "", result.sizeBytes, result.redirects
            )
            if (result.markers.isNotEmpty()) {
                text += "; block-page markers: ${result.markers.joinToString(", ")}"
            }
            text
        } else {
            "failed (${result.errorKind ?: "error"})"
        }
        out.appendLine(line(scheme, value))
    }
    out.appendLine()
    out.appendLine("Verdict")
    out.appendLine(
        line(report.verdict.code, "${report.verdict.explanation} (confidence: ${report.verdict.confidence})")
    )

    val findings = analyze(report)
    if (findings.isNotEmpty()) {
        out.appendLine()
        out.appendLine("Findings")
        for (finding in findings) {
            out.appendLine()
            out.appendLine("  [${finding.topic}] (confidence: ${finding.confidence})")
            out.appendLine("  Fact: ${finding.fact}")
            if (finding.possibleCauses.isNotEmpty()) {
                out.appendLine("  Possible causes:")
                for (cause in finding.possibleCauses) out.appendLine("    - $cause")
            }
            if (finding.recommendations.isNotEmpty()) {
                out.appendLine("  Recommendations:")
                for (step in finding.recommendations) out.appendLine("    - $step")
            }
        }
    }
    return out.toString().trimEnd()
}
