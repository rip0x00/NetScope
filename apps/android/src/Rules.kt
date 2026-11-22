package com.netscope.app

import java.util.Locale

/**
 * Rule-based troubleshooting, a port of the Python core's rules
 * module. The engine reads a finished [HostReport] and emits
 * findings. Every finding keeps three things separate:
 *
 * - `fact` — what was measured, with the numbers. Facts never
 *   contain a cause.
 * - `possibleCauses` — hypotheses that would explain the fact,
 *   labelled as possibilities, never merged into the fact.
 * - `recommendations` — verification steps the user can take.
 *   Advice only; nothing here changes a system setting.
 *
 * Confidence follows the strength of the underlying measurement. A
 * captive portal, in particular, can only ever be reported as a
 * suspicion: the observable evidence (a redirect to a different
 * host on plain HTTP) has innocent explanations.
 *
 * Pure JVM — no Android APIs — so it is covered by the JVM unit
 * tests in tests/.
 */

data class Finding(
    val topic: String,
    val fact: String,
    val possibleCauses: List<String> = emptyList(),
    val recommendations: List<String> = emptyList(),
    val confidence: String = "low" // high | medium | low
)

private fun fmt0(value: Double): String = String.format(Locale.US, "%.0f", value)

/** Derive troubleshooting findings from a completed host report. */
fun analyze(report: HostReport): List<Finding> {
    val findings = ArrayList<Finding>()
    findings.addAll(dnsFindings(report))
    findings.addAll(tcpFindings(report))
    findings.addAll(tlsFindings(report))
    findings.addAll(httpFindings(report))
    return findings
}

private fun dnsFindings(report: HostReport): List<Finding> {
    val dns = report.dns
    val out = ArrayList<Finding>()

    if (dns.suspectPoisoning) {
        val publicAddresses = sortedSetOf<String>()
        for (resolver in dns.resolvers) {
            if (resolver.status == "ok") publicAddresses.addAll(resolver.addresses)
        }
        out.add(
            Finding(
                topic = "dns-poisoning",
                fact = "The system resolver returned ${dns.systemAddresses.joinToString(", ")} for " +
                    "${dns.hostname}; public resolvers returned " +
                    "${if (publicAddresses.isEmpty()) "no addresses" else publicAddresses.joinToString(", ")}. " +
                    "The two sets share no address.",
                possibleCauses = listOf(
                    "The network's resolver is intercepting or rewriting DNS answers.",
                    "The router's DNS settings have been changed or compromised.",
                    "A captive or filtered network is substituting its own answers."
                ),
                recommendations = listOf(
                    "Repeat the check on a different network (for example a phone hotspot) and compare the addresses.",
                    "Check which DNS servers the router and this device are configured to use.",
                    "Compare with an encrypted DNS lookup (DoH) for the same name."
                ),
                confidence = "high"
            )
        )
    }

    val systemOk = dns.systemAddresses.isNotEmpty()
    val publicOk = dns.resolvers.any { it.status == "ok" && it.addresses.isNotEmpty() }
    if (!systemOk && publicOk) {
        out.add(
            Finding(
                topic = "dns-blocked",
                fact = "The system resolver returned no addresses for ${dns.hostname} " +
                    "(${dns.systemError ?: "empty answer"}), while at least one public " +
                    "resolver answered with addresses.",
                possibleCauses = listOf(
                    "The configured resolver is filtering this name.",
                    "The configured resolver is misconfigured or unreachable for this query.",
                    "Local DNS software (security tools, router filters) is intercepting the query."
                ),
                recommendations = listOf(
                    "Note which resolver the system is configured to use and test it directly.",
                    "Try the same lookup from another device on the same network."
                ),
                confidence = "high"
            )
        )
    } else if (!systemOk && dns.resolvers.isNotEmpty() &&
        dns.resolvers.all { it.status == "nxdomain" }
    ) {
        out.add(
            Finding(
                topic = "dns-nxdomain",
                fact = "Every resolver answered NXDOMAIN for ${dns.hostname}: " +
                    "the name is reported as not existing.",
                possibleCauses = listOf(
                    "The domain name really does not exist (check the spelling).",
                    "Resolvers are forging NXDOMAIN answers for a name that exists."
                ),
                recommendations = listOf(
                    "Verify the exact spelling of the name.",
                    "Look the name up from a different network and compare."
                ),
                confidence = "medium"
            )
        )
    } else if (!systemOk && dns.resolvers.isNotEmpty() &&
        dns.resolvers.all { it.status == "timeout" || it.status == "error" }
    ) {
        out.add(
            Finding(
                topic = "dns-unreachable",
                fact = "No resolver answered for ${dns.hostname}: the system resolver failed " +
                    "and every public resolver query timed out or errored.",
                possibleCauses = listOf(
                    "The network path to DNS servers is broken or blocked (UDP/53 filtered).",
                    "The device has no working internet connection at all."
                ),
                recommendations = listOf(
                    "Check whether any other name resolves on this device.",
                    "Check the device's basic connectivity (gateway, link state)."
                ),
                confidence = "medium"
            )
        )
    }

    if (dns.partialNxdomain) {
        out.add(
            Finding(
                topic = "dns-inconsistent",
                fact = "Resolvers disagree about ${dns.hostname}: at least one answered " +
                    "NXDOMAIN while at least one returned addresses.",
                possibleCauses = listOf(
                    "One resolver (or the path to it) is forging NXDOMAIN answers.",
                    "The resolvers hold different cached data during a DNS change."
                ),
                recommendations = listOf(
                    "Repeat the check after a few minutes to rule out a DNS change in progress.",
                    "Identify which resolver returns NXDOMAIN and test it with a known-good name."
                ),
                confidence = "medium"
            )
        )
    }
    return out
}

private fun tcpFindings(report: HostReport): List<Finding> {
    val out = ArrayList<Finding>()
    for (port in listOf(443, 80)) {
        val result = report.tcp[port] ?: continue
        if (result.attempts.isEmpty()) continue
        val stats = result.latency
        if (result.successes > 0 && result.lossPct >= 25.0) {
            out.add(
                Finding(
                    topic = "instability",
                    fact = "${result.successes} of ${result.attempts.size} TCP connections to " +
                        "port $port succeeded (${fmt0(result.lossPct)}% loss).",
                    possibleCauses = listOf(
                        "An unstable link (weak Wi-Fi signal, failing cable, overloaded router).",
                        "Congestion or rate limiting on the path.",
                        "The destination shedding load."
                    ),
                    recommendations = listOf(
                        "Repeat the test; intermittent loss that persists is a link problem, not a fluke.",
                        "Compare on a wired connection or a different network if available."
                    ),
                    confidence = "medium"
                )
            )
        }
        val avg = stats.avg
        if (avg != null && avg > 400.0) {
            out.add(
                Finding(
                    topic = "high-latency",
                    fact = "TCP connections to port $port took ${fmt0(avg)} ms on average " +
                        "(median ${fmt0(stats.median ?: 0.0)} ms, p95 ${fmt0(stats.p95 ?: 0.0)} ms " +
                        "over ${stats.count} connections).",
                    possibleCauses = listOf(
                        "Network congestion between this device and the destination.",
                        "Wireless interference or a weak signal adding retransmissions.",
                        "A distant or overloaded destination.",
                        "Router load (other traffic, weak hardware)."
                    ),
                    recommendations = listOf(
                        "Compare with a nearer, known-fast host to separate local from path latency.",
                        "Repeat at a different time of day to check for congestion patterns."
                    ),
                    confidence = "medium"
                )
            )
        }
        if (result.successes == 0 && result.dominantError == "refused") {
            out.add(
                Finding(
                    topic = "connection-refused",
                    fact = "Every connection to port $port was actively refused.",
                    possibleCauses = listOf(
                        "No service is listening on that port (the service is down).",
                        "A firewall at the destination is configured to reject connections."
                    ),
                    recommendations = listOf(
                        "If you operate the service, check that it is running and listening on this port."
                    ),
                    confidence = "medium"
                )
            )
        }
    }
    return out
}

private fun tlsFindings(report: HostReport): List<Finding> {
    val tls = report.tls ?: return emptyList()
    if (tls.ok) return emptyList()
    val out = ArrayList<Finding>()
    val tcp443 = report.tcp[443]
    if (tls.failedPhase == "handshake" && tcp443 != null && tcp443.successes > 0 &&
        (tls.errorKind == "reset" || tls.errorKind == "timeout")
    ) {
        val detail = if (tls.errorKind == "reset") "was reset" else "never completed"
        out.add(
            Finding(
                topic = "tls-blocking",
                fact = "TCP connections to port 443 open normally, but the TLS handshake " +
                    "$detail once the site name (SNI) was sent in the ClientHello.",
                possibleCauses = listOf(
                    "Name-based (SNI) filtering on the network path is interrupting the handshake.",
                    "A middlebox or security appliance is resetting connections it cannot inspect."
                ),
                recommendations = listOf(
                    "Repeat the check from a different network; if the handshake completes there, the block is on this path.",
                    "Compare with a host whose name is unlikely to be filtered, to confirm the failure follows the name."
                ),
                confidence = if (tls.errorKind == "reset") "high" else "medium"
            )
        )
    }
    if (tls.errorKind == "certificate") {
        out.add(
            Finding(
                topic = "tls-certificate",
                fact = "Certificate validation failed during the TLS handshake: ${tls.error}.",
                possibleCauses = listOf(
                    "The server's certificate is expired or misconfigured.",
                    "The connection is being intercepted by a proxy presenting its own certificate."
                ),
                recommendations = listOf(
                    "Check the device's date and time; a wrong clock fails validation.",
                    "Compare the certificate from a different network."
                ),
                confidence = "medium"
            )
        )
    }
    return out
}

private fun httpFindings(report: HostReport): List<Finding> {
    val out = ArrayList<Finding>()
    val https = report.http["https"]
    val plain = report.http["http"]

    for ((scheme, result) in listOf("https" to https, "http" to plain)) {
        if (result != null && result.ok && result.markers.isNotEmpty()) {
            out.add(
                Finding(
                    topic = "http-filtered",
                    fact = "The ${scheme.uppercase()} response for ${report.host} is a block page: " +
                        "it contains the filtering markers ${result.markers.joinToString(", ")}.",
                    possibleCauses = listOf(
                        "An ISP or network filtering service is substituting its own page for the site.",
                        "A local security product is blocking the page."
                    ),
                    recommendations = listOf(
                        "Repeat the check from a different network to identify which network serves the block page."
                    ),
                    confidence = if (scheme == "https") "high" else "medium"
                )
            )
        }
    }

    val finalHost = plain?.finalHost
    if (plain != null && plain.ok && finalHost != null && finalHost != report.host) {
        out.add(
            Finding(
                topic = "captive-portal-suspected",
                fact = "The plain-HTTP request for ${report.host} was redirected to a " +
                    "different host ($finalHost) after ${plain.redirects} redirect(s).",
                possibleCauses = listOf(
                    "A captive portal is intercepting web requests until the user signs in (a suspicion, not a certainty).",
                    "The site itself redirects its plain-HTTP traffic to another host."
                ),
                recommendations = listOf(
                    "Open a plain-HTTP page in a browser and see whether a sign-in or notice page appears.",
                    "If a portal sign-in exists, complete it and run the check again."
                ),
                confidence = "low"
            )
        )
    }
    return out
}
