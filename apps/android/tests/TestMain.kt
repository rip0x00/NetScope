package com.netscope.app

import java.net.ConnectException
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import kotlin.math.abs
import kotlin.system.exitProcess

/**
 * JVM unit tests for the Android app's pure logic: statistics
 * (Stats.kt), the DNS wire parser (DnsWire.kt), the verdict
 * classifier (Verdict.kt), the troubleshooting rules (Rules.kt),
 * the route classification (RouteProbe.kt), the block-marker scan
 * (HttpProbe.kt) and the socket-error classifier (NetErrors.kt).
 *
 * The statistics cases use the worked definitions from the Python
 * core's stats module; the DNS and verdict cases mirror the core's
 * test suites. All packets are built by hand here and nothing
 * touches a network. Run with test.sh.
 */

private var passedCount = 0
private var failedCount = 0

private fun test(name: String, block: () -> Unit) {
    try {
        block()
        passedCount += 1
        println("PASS $name")
    } catch (exc: Throwable) {
        failedCount += 1
        println("FAIL $name: ${exc.message}")
    }
}

private fun assertEq(expected: Any?, actual: Any?) {
    if (expected != actual) throw AssertionError("expected <$expected> but was <$actual>")
}

private fun assertTrue(condition: Boolean, message: String = "") {
    if (!condition) throw AssertionError("expected true $message")
}

private fun assertClose(expected: Double, actual: Double?, tolerance: Double = 1e-9) {
    if (actual == null || abs(expected - actual) > tolerance) {
        throw AssertionError("expected <$expected> but was <$actual>")
    }
}

private fun assertThrows(block: () -> Unit) {
    try {
        block()
    } catch (exc: IllegalArgumentException) {
        return
    }
    throw AssertionError("expected IllegalArgumentException")
}

// ---------------------------------------------------------------------------
// Packet builders
// ---------------------------------------------------------------------------

private fun u16Bytes(value: Int): ByteArray =
    byteArrayOf((value shr 8).toByte(), value.toByte())

private fun u32Bytes(value: Int): ByteArray = byteArrayOf(
    (value shr 24).toByte(), (value shr 16).toByte(), (value shr 8).toByte(), value.toByte()
)

private fun rrHeader(type: Int, ttl: Int, rdlen: Int): ByteArray =
    u16Bytes(type) + u16Bytes(1) + u32Bytes(ttl) + u16Bytes(rdlen)

private fun makePacket(
    answers: List<ByteArray>,
    rcode: Int = 0,
    qname: String = "example.com",
    qtype: Int = 1,
    txid: Int = 0x1234
): ByteArray {
    val flags = 0x8180 or rcode
    var packet = u16Bytes(txid) + u16Bytes(flags) + u16Bytes(1) +
        u16Bytes(answers.size) + u16Bytes(0) + u16Bytes(0)
    packet += encodeName(qname) + u16Bytes(qtype) + u16Bytes(1)
    for (answer in answers) packet += answer
    return packet
}

private fun aRecord(ip: String, ttl: Int = 300): ByteArray =
    // Name is a compression pointer to the question name at offset 12.
    byteArrayOf(0xC0.toByte(), 0x0C) + rrHeader(1, ttl, 4) + InetAddress.getByName(ip).address

private fun aaaaRecord(ip: String, ttl: Int = 300): ByteArray =
    byteArrayOf(0xC0.toByte(), 0x0C) + rrHeader(28, ttl, 16) + InetAddress.getByName(ip).address

private fun nameRecord(type: Int, target: String, ttl: Int = 300): ByteArray {
    val encoded = encodeName(target)
    return byteArrayOf(0xC0.toByte(), 0x0C) + rrHeader(type, ttl, encoded.size) + encoded
}

// ---------------------------------------------------------------------------
// Verdict builders
// ---------------------------------------------------------------------------

private fun dnsOk(): DnsReport = DnsReport("example.com").apply {
    systemAddresses = listOf("93.184.216.34")
    resolvers = listOf(ResolverResult("1.1.1.1", "ok", listOf("93.184.216.34"), 12.0))
}

private fun tcpOk(port: Int): TcpResult =
    TcpResult("93.184.216.34", port, List(4) { TcpAttempt(ok = true, latencyMs = 20.0) })

private fun tcpFail(port: Int, kind: String): TcpResult =
    TcpResult("93.184.216.34", port, List(4) { TcpAttempt(ok = false, errorKind = kind, error = "boom") })

private fun tlsOk(): TlsResult =
    TlsResult(hostname = "example.com", target = "93.184.216.34", ok = true, protocol = "TLSv1.3")

private fun tlsFail(phase: String, kind: String): TlsResult =
    TlsResult(
        hostname = "example.com", target = "93.184.216.34",
        ok = false, failedPhase = phase, errorKind = kind, error = "boom"
    )

private fun httpOk(
    scheme: String = "https",
    status: Int = 200,
    reason: String? = "OK",
    markers: List<String> = emptyList(),
    finalUrl: String? = null
): HttpResult = HttpResult(
    scheme = scheme, url = "$scheme://example.com/", ok = true,
    status = status, reason = reason, finalUrl = finalUrl ?: "$scheme://example.com/",
    sizeBytes = 1256, bodySha256 = "0".repeat(64), markers = markers
)

private fun httpFail(scheme: String = "https", kind: String = "timeout"): HttpResult =
    HttpResult(scheme = scheme, url = "$scheme://example.com/", ok = false, errorKind = kind, error = "boom")

private fun bothHttpOk(): Map<String, HttpResult> =
    mapOf("https" to httpOk("https"), "http" to httpOk("http"))

private fun okReport(): HostReport = HostReport(
    "example.com",
    dnsOk(),
    mapOf(443 to tcpOk(443), 80 to tcpOk(80)),
    tlsOk(),
    bothHttpOk(),
    Verdict(VerdictCodes.OK, "ok", "high")
)

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

fun main() {
    // ---- Statistics ------------------------------------------------------

    test("stats_percentiles_use_linear_interpolation") {
        val stats = latencyStats(listOf(10.0, 20.0, 30.0, 40.0))
        assertEq(4, stats.count)
        assertClose(10.0, stats.min)
        assertClose(40.0, stats.max)
        assertClose(25.0, stats.avg)
        assertClose(25.0, stats.median) // rank 1.5 -> halfway between 20 and 30
        assertClose(38.5, stats.p95) // rank 2.85 -> 30 + 0.85 * 10
        assertClose(37.0, stats.p90) // rank 2.7 -> 30 + 0.7 * 10
    }

    test("stats_population_stddev") {
        val stats = latencyStats(listOf(10.0, 20.0, 30.0, 40.0))
        // mean 25, variance (225+25+25+225)/4 = 125
        assertClose(11.180339887498949, stats.stddev, 1e-12)
    }

    test("stats_single_sample") {
        val stats = latencyStats(listOf(42.0))
        assertClose(42.0, stats.median)
        assertClose(42.0, stats.p99)
        assertClose(0.0, stats.stddev)
        assertEq(null, stats.jitterAvg)
        assertEq(null, stats.jitterMax)
    }

    test("stats_empty_series") {
        val stats = latencyStats(emptyList())
        assertEq(0, stats.count)
        assertEq(null, stats.avg)
        assertEq(null, stats.min)
    }

    test("stats_jitter_is_mean_absolute_successive_difference") {
        val (avg, max) = jitterOf(listOf(10.0, 14.0, 11.0, 11.0))
        assertClose(7.0 / 3.0, avg) // diffs 4, 3, 0
        assertClose(4.0, max)
        val stats = latencyStats(listOf(10.0, 14.0, 11.0, 11.0))
        assertClose(7.0 / 3.0, stats.jitterAvg)
    }

    test("stats_packet_loss_accounting") {
        assertClose(25.0, packetLoss(4, 3).lossPercent)
        assertClose(0.0, packetLoss(0, 0).lossPercent)
        assertEq(2, packetLoss(2, 5).received) // received clamped to sent
        assertClose(100.0, packetLoss(4, 0, 4).lossPercent)
    }

    // ---- DNS wire format ---------------------------------------------------

    test("dns_parse_single_a_record") {
        val message = parseResponse(makePacket(listOf(aRecord("93.184.216.34"))))
        assertEq(0, message.rcode)
        assertEq(1, message.answers.size)
        val record = message.answers[0]
        assertEq("A", record.type)
        assertEq("example.com", record.name)
        assertEq("93.184.216.34", record.value)
        assertEq(300L, record.ttl)
    }

    test("dns_parse_multiple_a_records") {
        val packet = makePacket(listOf(aRecord("93.184.216.34"), aRecord("93.184.216.35")))
        val message = parseResponse(packet)
        assertEq(listOf("93.184.216.34", "93.184.216.35"), message.addressesFor("example.com"))
    }

    test("dns_parse_aaaa_record") {
        val message = parseResponse(makePacket(listOf(aaaaRecord("2001:db8::1"))))
        assertEq("AAAA", message.answers[0].type)
        assertEq(listOf("2001:db8::1"), message.addressesFor("example.com"))
    }

    test("dns_cname_chain_is_followed") {
        val target = encodeName("example.com")
        val cname = byteArrayOf(0xC0.toByte(), 0x0C) + rrHeader(5, 300, target.size) + target
        val a = encodeName("example.com") + rrHeader(1, 300, 4) +
            InetAddress.getByName("93.184.216.34").address
        val packet = makePacket(listOf(cname, a), qname = "www.example.com")
        val message = parseResponse(packet)
        assertEq(listOf("93.184.216.34"), message.addressesFor("www.example.com"))
    }

    test("dns_mx_record") {
        val exchange = encodeName("mail.example.com")
        val mx = byteArrayOf(0xC0.toByte(), 0x0C) +
            rrHeader(15, 300, 2 + exchange.size) + u16Bytes(10) + exchange
        val message = parseResponse(makePacket(listOf(mx), qtype = 15))
        assertEq("MX", message.answers[0].type)
        assertEq("10 mail.example.com", message.answers[0].value)
    }

    test("dns_ns_and_ptr_records") {
        val message = parseResponse(
            makePacket(listOf(nameRecord(2, "ns1.example.com"), nameRecord(12, "host.example.com")))
        )
        assertEq("NS", message.answers[0].type)
        assertEq("ns1.example.com", message.answers[0].value)
        assertEq("PTR", message.answers[1].type)
        assertEq("host.example.com", message.answers[1].value)
    }

    test("dns_txt_record_joins_character_strings") {
        val rdata = byteArrayOf(5) + "hello".toByteArray() + byteArrayOf(5) + "world".toByteArray()
        val txt = byteArrayOf(0xC0.toByte(), 0x0C) + rrHeader(16, 300, rdata.size) + rdata
        val message = parseResponse(makePacket(listOf(txt), qtype = 16))
        assertEq("TXT", message.answers[0].type)
        assertEq("helloworld", message.answers[0].value)
    }

    test("dns_soa_record") {
        val rdata = encodeName("ns1.example.com") + encodeName("hostmaster.example.com") +
            u32Bytes(2024010101) + u32Bytes(7200) + u32Bytes(3600) +
            u32Bytes(1209600) + u32Bytes(300)
        val soa = byteArrayOf(0xC0.toByte(), 0x0C) + rrHeader(6, 300, rdata.size) + rdata
        val message = parseResponse(makePacket(listOf(soa), qtype = 6))
        assertEq("SOA", message.answers[0].type)
        assertEq(
            "ns1.example.com hostmaster.example.com 2024010101 7200 3600 1209600 300",
            message.answers[0].value
        )
    }

    test("dns_srv_record") {
        val target = encodeName("sip.example.com")
        val rdata = u16Bytes(10) + u16Bytes(60) + u16Bytes(5060) + target
        val srv = byteArrayOf(0xC0.toByte(), 0x0C) + rrHeader(33, 300, rdata.size) + rdata
        val message = parseResponse(makePacket(listOf(srv), qtype = 33))
        assertEq("SRV", message.answers[0].type)
        assertEq("10 60 5060 sip.example.com", message.answers[0].value)
    }

    test("dns_caa_record") {
        val rdata = byteArrayOf(0, 5) + "issue".toByteArray() + "letsencrypt.org".toByteArray()
        val caa = byteArrayOf(0xC0.toByte(), 0x0C) + rrHeader(257, 300, rdata.size) + rdata
        val message = parseResponse(makePacket(listOf(caa), qtype = 257))
        assertEq("CAA", message.answers[0].type)
        assertEq("0 issue \"letsencrypt.org\"", message.answers[0].value)
    }

    test("dns_unknown_record_type_is_carried_as_hex") {
        val unknown = byteArrayOf(0xC0.toByte(), 0x0C) +
            rrHeader(99, 300, 2) + byteArrayOf(0xDE.toByte(), 0xAD.toByte())
        val message = parseResponse(makePacket(listOf(unknown, aRecord("93.184.216.34"))))
        assertEq("TYPE99", message.answers[0].type)
        assertEq("dead", message.answers[0].value)
        assertEq("A", message.answers[1].type)
    }

    test("dns_nxdomain_response") {
        val message = parseResponse(makePacket(emptyList(), rcode = 3))
        assertEq(3, message.rcode)
        assertEq("NXDOMAIN", message.rcodeName)
        assertEq(0, message.answers.size)
        assertEq(emptyList<String>(), message.addressesFor("example.com"))
    }

    test("dns_truncated_header_raises") {
        assertThrows { parseResponse(ByteArray(5)) }
    }

    test("dns_truncated_answer_raises") {
        val packet = makePacket(listOf(aRecord("93.184.216.34")))
        assertThrows { parseResponse(packet.copyOf(packet.size - 2)) }
    }

    test("dns_compression_pointer_loop_raises") {
        // The question name is a pointer to itself.
        var packet = u16Bytes(0x1) + u16Bytes(0x8180) + u16Bytes(1) +
            u16Bytes(0) + u16Bytes(0) + u16Bytes(0)
        packet += byteArrayOf(0xC0.toByte(), 0x0C) + u16Bytes(1) + u16Bytes(1)
        assertThrows { parseResponse(packet) }
    }

    test("dns_build_query_layout") {
        val packet = buildQuery("example.com", QTYPE_A, 0x00AA)
        assertEq(0x00AA, ((packet[0].toInt() and 0xFF) shl 8) or (packet[1].toInt() and 0xFF))
        assertEq(0x0100, ((packet[2].toInt() and 0xFF) shl 8) or (packet[3].toInt() and 0xFF))
        assertEq(1, ((packet[4].toInt() and 0xFF) shl 8) or (packet[5].toInt() and 0xFF))
        assertEq(0, ((packet[6].toInt() and 0xFF) shl 8) or (packet[7].toInt() and 0xFF))
        val expectedName = byteArrayOf(7) + "example".toByteArray() + byteArrayOf(3) + "com".toByteArray() + byteArrayOf(0)
        assertTrue(packet.copyOfRange(12, 25).contentEquals(expectedName), "question name bytes")
        assertEq(QTYPE_A, ((packet[25].toInt() and 0xFF) shl 8) or (packet[26].toInt() and 0xFF))
        assertEq(1, ((packet[27].toInt() and 0xFF) shl 8) or (packet[28].toInt() and 0xFF))
    }

    test("dns_reverse_name_for_ipv4") {
        assertEq("4.3.2.1.in-addr.arpa", reverseNameForIpv4("1.2.3.4"))
        assertEq(null, reverseNameForIpv4("example.com"))
        assertEq(null, reverseNameForIpv4("1.2.3.999"))
    }

    // ---- Verdict classifier ------------------------------------------------

    test("verdict_ok") {
        val verdict = classify(dnsOk(), mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), bothHttpOk())
        assertEq(VerdictCodes.OK, verdict.code)
        assertEq("high", verdict.confidence)
    }

    test("verdict_dns_poisoned") {
        val dns = dnsOk()
        dns.suspectPoisoning = true
        val verdict = classify(dns, mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), bothHttpOk())
        assertEq(VerdictCodes.DNS_POISONED, verdict.code)
    }

    test("verdict_dns_blocked_when_system_fails_but_public_answers") {
        val dns = DnsReport("example.com").apply {
            systemAddresses = emptyList()
            systemError = "gaierror"
            resolvers = listOf(ResolverResult("1.1.1.1", "ok", listOf("93.184.216.34"), 12.0))
        }
        val verdict = classify(dns, mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), bothHttpOk())
        assertEq(VerdictCodes.DNS_BLOCKED, verdict.code)
        assertEq("high", verdict.confidence)
    }

    test("verdict_dns_blocked_when_everyone_says_nxdomain") {
        val dns = DnsReport("nope.example").apply {
            systemAddresses = emptyList()
            resolvers = listOf(
                ResolverResult("1.1.1.1", "nxdomain"),
                ResolverResult("8.8.8.8", "nxdomain")
            )
        }
        val verdict = classify(
            dns, mapOf(443 to tcpFail(443, "timeout"), 80 to tcpFail(80, "timeout")), null, emptyMap()
        )
        assertEq(VerdictCodes.DNS_BLOCKED, verdict.code)
    }

    test("verdict_network_unreachable_when_dns_is_silent") {
        val dns = DnsReport("example.com").apply {
            systemAddresses = emptyList()
            resolvers = listOf(
                ResolverResult("1.1.1.1", "timeout"),
                ResolverResult("8.8.8.8", "timeout")
            )
        }
        val verdict = classify(
            dns, mapOf(443 to tcpFail(443, "timeout"), 80 to tcpFail(80, "timeout")), null, emptyMap()
        )
        assertEq(VerdictCodes.NETWORK_UNREACHABLE, verdict.code)
    }

    test("verdict_tcp_blocked_on_resets") {
        val verdict = classify(
            dnsOk(), mapOf(443 to tcpFail(443, "reset"), 80 to tcpFail(80, "reset")), null, emptyMap()
        )
        assertEq(VerdictCodes.TCP_BLOCKED, verdict.code)
        assertEq("high", verdict.confidence)
    }

    test("verdict_tcp_blocked_on_timeouts") {
        val verdict = classify(
            dnsOk(), mapOf(443 to tcpFail(443, "timeout"), 80 to tcpFail(80, "timeout")), null, emptyMap()
        )
        assertEq(VerdictCodes.TCP_BLOCKED, verdict.code)
    }

    test("verdict_server_down_on_refused") {
        val verdict = classify(
            dnsOk(), mapOf(443 to tcpFail(443, "refused"), 80 to tcpFail(80, "refused")), null, emptyMap()
        )
        assertEq(VerdictCodes.SERVER_DOWN, verdict.code)
    }

    test("verdict_network_unreachable_on_tcp_unreachable") {
        val verdict = classify(
            dnsOk(),
            mapOf(443 to tcpFail(443, "unreachable"), 80 to tcpFail(80, "unreachable")),
            null, emptyMap()
        )
        assertEq(VerdictCodes.NETWORK_UNREACHABLE, verdict.code)
    }

    test("verdict_https_port_blocked_while_http_works") {
        val verdict = classify(
            dnsOk(),
            mapOf(443 to tcpFail(443, "reset"), 80 to tcpOk(80)),
            tlsFail("connect", "reset"),
            mapOf("https" to httpFail("https", "reset"), "http" to httpOk("http"))
        )
        assertEq(VerdictCodes.TCP_BLOCKED, verdict.code)
    }

    test("verdict_tls_sni_blocked_on_handshake_reset") {
        val verdict = classify(
            dnsOk(), mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsFail("handshake", "reset"), emptyMap()
        )
        assertEq(VerdictCodes.TLS_SNI_BLOCKED, verdict.code)
        assertEq("high", verdict.confidence)
    }

    test("verdict_tls_sni_blocked_on_handshake_timeout") {
        val verdict = classify(
            dnsOk(), mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsFail("handshake", "timeout"), emptyMap()
        )
        assertEq(VerdictCodes.TLS_SNI_BLOCKED, verdict.code)
        assertEq("medium", verdict.confidence)
    }

    test("verdict_certificate_problem_is_unknown_not_filtering") {
        val verdict = classify(
            dnsOk(), mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsFail("handshake", "certificate"), emptyMap()
        )
        assertEq(VerdictCodes.UNKNOWN, verdict.code)
    }

    test("verdict_http_filtered_by_block_page_markers") {
        val http = mapOf(
            "https" to httpOk("https", markers = listOf("فیلترینگ")),
            "http" to httpOk("http")
        )
        val verdict = classify(dnsOk(), mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), http)
        assertEq(VerdictCodes.HTTP_FILTERED, verdict.code)
    }

    test("verdict_http_filtered_by_451") {
        val http = mapOf(
            "https" to httpOk("https", status = 451, reason = "Unavailable For Legal Reasons"),
            "http" to httpOk("http")
        )
        val verdict = classify(dnsOk(), mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), http)
        assertEq(VerdictCodes.HTTP_FILTERED, verdict.code)
    }

    test("verdict_http_filtered_on_plain_http_block_page") {
        val http = mapOf(
            "https" to httpFail("https", "error"),
            "http" to httpOk("http", markers = listOf("access denied"))
        )
        val verdict = classify(dnsOk(), mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), http)
        assertEq(VerdictCodes.HTTP_FILTERED, verdict.code)
    }

    test("verdict_server_down_when_http_never_answers") {
        val http = mapOf(
            "https" to httpFail("https", "timeout"),
            "http" to httpFail("http", "timeout")
        )
        val verdict = classify(dnsOk(), mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), http)
        assertEq(VerdictCodes.SERVER_DOWN, verdict.code)
    }

    test("verdict_slow_unstable_on_high_loss") {
        val lossy = TcpResult(
            "93.184.216.34", 443,
            listOf(
                TcpAttempt(ok = true, latencyMs = 20.0),
                TcpAttempt(ok = false, errorKind = "timeout"),
                TcpAttempt(ok = true, latencyMs = 22.0),
                TcpAttempt(ok = false, errorKind = "timeout")
            )
        )
        val verdict = classify(dnsOk(), mapOf(443 to lossy, 80 to tcpOk(80)), tlsOk(), bothHttpOk())
        assertEq(VerdictCodes.SLOW_UNSTABLE, verdict.code)
    }

    test("verdict_slow_unstable_on_high_latency") {
        val slow = TcpResult(
            "93.184.216.34", 443,
            List(4) { TcpAttempt(ok = true, latencyMs = 650.0) }
        )
        val verdict = classify(dnsOk(), mapOf(443 to slow, 80 to tcpOk(80)), tlsOk(), bothHttpOk())
        assertEq(VerdictCodes.SLOW_UNSTABLE, verdict.code)
    }

    // ---- Troubleshooting rules ----------------------------------------------

    test("rules_clean_report_has_no_findings") {
        assertEq(emptyList<Finding>(), analyze(okReport()))
    }

    test("rules_dns_poisoning_finding_separates_fact_and_causes") {
        val dns = dnsOk()
        dns.suspectPoisoning = true
        val report = HostReport(
            "example.com", dns,
            mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), bothHttpOk(),
            Verdict(VerdictCodes.DNS_POISONED, "x", "high")
        )
        val findings = analyze(report)
        val finding = findings.first { it.topic == "dns-poisoning" }
        assertTrue(finding.fact.contains("93.184.216.34"), "fact carries the measured addresses")
        assertTrue(finding.possibleCauses.isNotEmpty(), "causes are hypotheses, listed separately")
        assertTrue(finding.recommendations.isNotEmpty())
        assertEq("high", finding.confidence)
    }

    test("rules_tls_blocking_finding") {
        val report = HostReport(
            "example.com", dnsOk(),
            mapOf(443 to tcpOk(443), 80 to tcpOk(80)),
            tlsFail("handshake", "reset"), bothHttpOk(),
            Verdict(VerdictCodes.TLS_SNI_BLOCKED, "x", "high")
        )
        val finding = analyze(report).first { it.topic == "tls-blocking" }
        assertTrue(finding.fact.contains("was reset"), "fact states the measurement")
        assertEq("high", finding.confidence)
    }

    test("rules_high_latency_finding_uses_shared_stats") {
        val slow = TcpResult(
            "93.184.216.34", 443,
            List(4) { TcpAttempt(ok = true, latencyMs = 650.0) }
        )
        val report = HostReport(
            "example.com", dnsOk(),
            mapOf(443 to slow, 80 to tcpOk(80)), tlsOk(), bothHttpOk(),
            Verdict(VerdictCodes.SLOW_UNSTABLE, "x", "low")
        )
        val finding = analyze(report).first { it.topic == "high-latency" }
        assertTrue(finding.fact.contains("650 ms"), "fact carries the measured average")
    }

    test("rules_captive_portal_is_only_a_suspicion") {
        val http = mapOf(
            "https" to httpOk("https"),
            "http" to httpOk("http", finalUrl = "http://portal.example.net/login")
        )
        val report = HostReport(
            "example.com", dnsOk(),
            mapOf(443 to tcpOk(443), 80 to tcpOk(80)), tlsOk(), http,
            Verdict(VerdictCodes.OK, "x", "high")
        )
        val finding = analyze(report).first { it.topic == "captive-portal-suspected" }
        assertEq("low", finding.confidence)
    }

    // ---- Route classification -------------------------------------------------

    test("route_reached_destination") {
        val hops = listOf(RouteHop(1), RouteHop(2), RouteHop(3, "93.184.216.34", 12.0))
        val (stop, _) = classifyRoute(hops, reached = true, method = "tcp")
        assertEq("destination", stop)
    }

    test("route_no_response_with_tcp_fallback_note") {
        val hops = listOf(RouteHop(1), RouteHop(2), RouteHop(3))
        val (stop, note) = classifyRoute(hops, reached = false, method = "tcp")
        assertEq("no-response", stop)
        assertTrue(note.contains("TCP fallback"), "note names the method honestly")
    }

    test("route_local_stop") {
        val hops = listOf(RouteHop(1, "192.168.1.1", 1.0), RouteHop(2, "10.0.0.1", 3.0))
        val (stop, _) = classifyRoute(hops, reached = false, method = "icmp")
        assertEq("local", stop)
    }

    test("route_mid_path_stop") {
        val hops = (1..9).map { RouteHop(it, "10.0.0.$it", 5.0) }
        val (stop, _) = classifyRoute(hops, reached = false, method = "icmp")
        assertEq("mid-path", stop)
    }

    test("route_trace_stops_when_destination_answers") {
        val probe = TtlConnectProbe { _, _, ttl, _ ->
            if (ttl >= 3) Pair(true, 12.0) else Pair(false, null)
        }
        val (hops, reached) = traceTcp("93.184.216.34", 443, 30, 1500, probe)
        assertTrue(reached)
        assertEq(3, hops.size)
        assertEq("93.184.216.34", hops.last().ip)
        assertClose(12.0, hops.last().rttMs)
    }

    test("route_trace_stops_after_five_silent_ttls") {
        val probe = TtlConnectProbe { _, _, _, _ -> Pair(false, null) }
        val (hops, reached) = traceTcp("93.184.216.34", 443, 30, 1500, probe)
        assertTrue(!reached)
        assertEq(5, hops.size) // the core's consecutive-silence cutoff
    }

    // ---- Block-page markers ----------------------------------------------

    test("markers_english_case_insensitive") {
        assertEq(listOf("access denied"), findBlockMarkers("<h1>Access Denied</h1>"))
    }

    test("markers_persian_block_page") {
        val markers = findBlockMarkers("دسترسی به این سایت مسدود شده است")
        assertTrue("مسدود شده است" in markers, "expected the Persian blocked marker, got $markers")
        assertTrue("دسترسی به این سایت" in markers, "expected the Persian access marker, got $markers")
    }

    test("markers_none_on_ordinary_page") {
        assertEq(emptyList<String>(), findBlockMarkers("<h1>Welcome to example.com</h1>"))
    }

    // ---- Socket error classifier ------------------------------------------

    test("errors_timeout") {
        assertEq("timeout", classifySocketError(SocketTimeoutException("connect timed out")))
    }

    test("errors_dns") {
        assertEq("dns", classifySocketError(UnknownHostException("example.com")))
    }

    test("errors_refused") {
        assertEq("refused", classifySocketError(ConnectException("Connection refused")))
    }

    println()
    println("JVM tests: $passedCount passed, $failedCount failed, ${passedCount + failedCount} total")
    if (failedCount > 0) exitProcess(1)
}
