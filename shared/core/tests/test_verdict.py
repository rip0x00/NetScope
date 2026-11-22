"""Verdict classifier cases. Layer results are constructed directly;
no network is involved."""

from netscope_core.dnsprobe import DNSReport, ResolverResult
from netscope_core.httpprobe import HTTPResult
from netscope_core.tcpprobe import Attempt, TCPResult
from netscope_core.tlsprobe import TLSResult
from netscope_core.verdict import classify

HOST = "example.com"
ADDR = "93.184.216.34"


def dns(system=(ADDR,), resolvers=None, poisoning=False):
    if resolvers is None:
        resolvers = [ResolverResult(resolver="1.1.1.1", status="ok", addresses=[ADDR])]
    return DNSReport(
        hostname=HOST,
        system_addresses=list(system),
        resolvers=list(resolvers),
        suspect_poisoning=poisoning,
    )


def resolver(status, addresses=()):
    return ResolverResult(resolver="1.1.1.1", status=status, addresses=list(addresses))


def tcp(port, outcomes):
    attempts = []
    for outcome in outcomes:
        if outcome == "ok":
            attempts.append(Attempt(ok=True, latency_ms=10.0))
        elif isinstance(outcome, (int, float)):
            attempts.append(Attempt(ok=True, latency_ms=float(outcome)))
        else:
            attempts.append(Attempt(ok=False, error_kind=outcome, error=outcome))
    return TCPResult(target=ADDR, port=port, attempts=attempts)


def good_tcp():
    return {443: tcp(443, ["ok"] * 4), 80: tcp(80, ["ok"] * 4)}


def tls(**kwargs):
    base = {"hostname": HOST, "target": ADDR}
    base.update(kwargs)
    return TLSResult(**base)


def http(scheme, **kwargs):
    base = {"scheme": scheme, "url": f"{scheme}://{HOST}/"}
    base.update(kwargs)
    return HTTPResult(**base)


def good_http():
    return {
        "https": http("https", ok=True, status=200),
        "http": http("http", ok=True, status=200),
    }


def test_ok():
    verdict = classify(dns(), good_tcp(), tls(ok=True), good_http())
    assert verdict.code == "OK"
    assert verdict.confidence == "high"


def test_dns_poisoned():
    verdict = classify(dns(poisoning=True), good_tcp(), tls(ok=True), good_http())
    assert verdict.code == "DNS_POISONED"
    assert verdict.confidence == "high"


def test_dns_blocked_system_fails_public_ok():
    verdict = classify(dns(system=()), good_tcp(), tls(ok=True), good_http())
    assert verdict.code == "DNS_BLOCKED"


def test_dns_blocked_all_nxdomain():
    report = dns(system=(), resolvers=[resolver("nxdomain")])
    verdict = classify(report, good_tcp(), tls(ok=True), good_http())
    assert verdict.code == "DNS_BLOCKED"
    assert verdict.confidence == "medium"


def test_network_unreachable_when_dns_silent():
    report = dns(system=(), resolvers=[resolver("timeout"), resolver("error")])
    verdict = classify(report, good_tcp(), tls(ok=True), good_http())
    assert verdict.code == "NETWORK_UNREACHABLE"


def test_dns_inconsistent_is_unknown():
    report = dns(system=(), resolvers=[resolver("servfail")])
    verdict = classify(report, good_tcp(), tls(ok=True), good_http())
    assert verdict.code == "UNKNOWN"
    assert verdict.confidence == "low"


def test_server_down_refused_both_ports():
    dead = {443: tcp(443, ["refused"] * 4), 80: tcp(80, ["refused"] * 4)}
    verdict = classify(dns(), dead, tls(ok=False), {})
    assert verdict.code == "SERVER_DOWN"


def test_network_unreachable_tcp():
    dead = {443: tcp(443, ["unreachable"] * 4), 80: tcp(80, ["timeout"] * 4)}
    verdict = classify(dns(), dead, None, {})
    assert verdict.code == "NETWORK_UNREACHABLE"


def test_tcp_blocked_resets():
    dead = {443: tcp(443, ["reset"] * 4), 80: tcp(80, ["reset"] * 4)}
    verdict = classify(dns(), dead, None, {})
    assert verdict.code == "TCP_BLOCKED"
    assert verdict.confidence == "high"


def test_tcp_blocked_timeouts():
    dead = {443: tcp(443, ["timeout"] * 4), 80: tcp(80, ["timeout"] * 4)}
    verdict = classify(dns(), dead, None, {})
    assert verdict.code == "TCP_BLOCKED"
    assert verdict.confidence == "medium"


def test_tcp_blocked_443_only_reset():
    mixed = {443: tcp(443, ["reset"] * 4), 80: tcp(80, ["ok"] * 4)}
    verdict = classify(dns(), mixed, tls(ok=False), good_http())
    assert verdict.code == "TCP_BLOCKED"


def test_tls_sni_blocked_reset():
    broken = tls(ok=False, failed_phase="handshake", error_kind="reset", error="reset by peer")
    verdict = classify(dns(), good_tcp(), broken, {})
    assert verdict.code == "TLS_SNI_BLOCKED"
    assert verdict.confidence == "high"


def test_tls_sni_blocked_timeout():
    broken = tls(ok=False, failed_phase="handshake", error_kind="timeout", error="timed out")
    verdict = classify(dns(), good_tcp(), broken, {})
    assert verdict.code == "TLS_SNI_BLOCKED"
    assert verdict.confidence == "medium"


def test_tls_certificate_problem_is_unknown():
    broken = tls(ok=False, failed_phase="handshake", error_kind="certificate", error="expired")
    verdict = classify(dns(), good_tcp(), broken, {})
    assert verdict.code == "UNKNOWN"


def test_http_filtered_https_block_page():
    pages = good_http()
    pages["https"] = http("https", ok=True, status=200, markers=["access denied"])
    verdict = classify(dns(), good_tcp(), tls(ok=True), pages)
    assert verdict.code == "HTTP_FILTERED"
    assert verdict.confidence == "high"


def test_http_filtered_451():
    pages = good_http()
    pages["https"] = http("https", ok=True, status=451)
    verdict = classify(dns(), good_tcp(), tls(ok=True), pages)
    assert verdict.code == "HTTP_FILTERED"


def test_http_filtered_plain_http_block_page():
    pages = {
        "https": http("https", ok=False, error_kind="timeout", error="timed out"),
        "http": http("http", ok=True, status=200, markers=["site blocked"]),
    }
    verdict = classify(dns(), good_tcp(), tls(ok=True), pages)
    assert verdict.code == "HTTP_FILTERED"


def test_http_filtered_reset_after_tls():
    pages = {
        "https": http("https", ok=False, error_kind="reset", error="reset"),
        "http": http("http", ok=False, error_kind="timeout", error="timed out"),
    }
    verdict = classify(dns(), good_tcp(), tls(ok=True), pages)
    assert verdict.code == "HTTP_FILTERED"


def test_slow_unstable_high_loss():
    lossy = {443: tcp(443, ["ok", "ok", "timeout", "timeout"]), 80: tcp(80, ["ok"] * 4)}
    verdict = classify(dns(), lossy, tls(ok=True), good_http())
    assert verdict.code == "SLOW_UNSTABLE"


def test_slow_unstable_high_latency():
    slow = {443: tcp(443, [500.0] * 4), 80: tcp(80, ["ok"] * 4)}
    verdict = classify(dns(), slow, tls(ok=True), good_http())
    assert verdict.code == "SLOW_UNSTABLE"


def test_server_down_http_dead_but_tcp_open():
    pages = {
        "https": http("https", ok=False, error_kind="timeout", error="timed out"),
        "http": http("http", ok=False, error_kind="timeout", error="timed out"),
    }
    verdict = classify(dns(), good_tcp(), tls(ok=True), pages)
    assert verdict.code == "SERVER_DOWN"


def test_everything_broken_falls_to_unknown():
    pages = {
        "https": http("https", ok=False, error_kind="error", error="?"),
        "http": http("http", ok=True, status=200),
    }
    verdict = classify(dns(), good_tcp(), tls(ok=True), pages)
    assert verdict.code == "UNKNOWN"
