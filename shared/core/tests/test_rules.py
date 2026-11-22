"""Troubleshooting rules: facts must stay facts (measured values only),
causes must stay hypotheses, and a captive portal is only a suspicion."""

from netscope_core.dnsprobe import DNSReport, ResolverResult
from netscope_core.httpprobe import HTTPResult
from netscope_core.models import HostReport
from netscope_core.rules import analyze
from netscope_core.tcpprobe import Attempt, TCPResult
from netscope_core.tlsprobe import TLSResult
from netscope_core.verdict import Verdict

HOST = "example.com"


def make_report(dns=None, tcp=None, tls=None, http=None):
    report = HostReport(
        host=HOST,
        dns=dns or DNSReport(hostname=HOST, system_addresses=["93.184.216.34"]),
        tcp=tcp or {},
        tls=tls,
        http=http or {},
        results=[],
        verdict=Verdict("UNKNOWN", "test", "low"),
    )
    report.findings = analyze(report)
    return report


def topics(report):
    return [f.topic for f in report.findings]


def tcp_with(port, attempts):
    return {port: TCPResult(target="93.184.216.34", port=port, attempts=attempts)}


def test_clean_report_has_no_findings():
    tcp = tcp_with(443, [Attempt(ok=True, latency_ms=12.0) for _ in range(4)])
    http = {
        "https": HTTPResult(scheme="https", url=f"https://{HOST}/", ok=True, status=200,
                            final_url=f"https://{HOST}/"),
        "http": HTTPResult(scheme="http", url=f"http://{HOST}/", ok=True, status=200,
                           final_url=f"http://{HOST}/"),
    }
    report = make_report(tcp=tcp, tls=TLSResult(hostname=HOST, target="x", ok=True), http=http)
    assert report.findings == []


def test_poisoning_finding_separates_fact_from_causes():
    dns = DNSReport(
        hostname=HOST,
        system_addresses=["203.0.113.9"],
        resolvers=[ResolverResult(resolver="1.1.1.1", status="ok", addresses=["93.184.216.34"])],
        suspect_poisoning=True,
    )
    report = make_report(dns=dns)
    finding = next(f for f in report.findings if f.topic == "dns-poisoning")
    # The fact carries the measured addresses, and only those.
    assert "203.0.113.9" in finding.fact
    assert "93.184.216.34" in finding.fact
    assert "compromised" not in finding.fact
    # Causes live in their own field and are phrased as possibilities.
    assert finding.possible_causes
    assert finding.recommendations
    assert finding.confidence == "high"


def test_dns_blocked_finding():
    dns = DNSReport(
        hostname=HOST,
        system_addresses=[],
        system_error="Name or service not known",
        resolvers=[ResolverResult(resolver="8.8.8.8", status="ok", addresses=["93.184.216.34"])],
    )
    report = make_report(dns=dns)
    assert "dns-blocked" in topics(report)


def test_high_latency_finding_uses_measured_numbers():
    attempts = [Attempt(ok=True, latency_ms=600.0) for _ in range(4)]
    report = make_report(tcp=tcp_with(443, attempts))
    finding = next(f for f in report.findings if f.topic == "high-latency")
    assert "600 ms" in finding.fact


def test_instability_finding():
    attempts = [Attempt(ok=True, latency_ms=10.0), Attempt(ok=True, latency_ms=10.0),
                Attempt(ok=False, error_kind="timeout"), Attempt(ok=False, error_kind="timeout")]
    report = make_report(tcp=tcp_with(443, attempts))
    finding = next(f for f in report.findings if f.topic == "instability")
    assert "50% loss" in finding.fact


def test_tls_blocking_finding():
    tcp = tcp_with(443, [Attempt(ok=True, latency_ms=10.0) for _ in range(4)])
    tls = TLSResult(hostname=HOST, target="x", ok=False, failed_phase="handshake",
                    error_kind="reset", error="reset")
    report = make_report(tcp=tcp, tls=tls)
    finding = next(f for f in report.findings if f.topic == "tls-blocking")
    assert finding.confidence == "high"
    assert "SNI" in finding.fact


def test_captive_portal_is_only_a_suspicion():
    http = {
        "http": HTTPResult(scheme="http", url=f"http://{HOST}/", ok=True, status=200,
                           final_url="http://portal.example.net/login", redirects=1),
    }
    report = make_report(http=http)
    finding = next(f for f in report.findings if f.topic == "captive-portal-suspected")
    assert finding.confidence == "low"
    assert "portal.example.net" in finding.fact
    assert any("suspicion" in cause for cause in finding.possible_causes)


def test_block_page_finding():
    http = {
        "https": HTTPResult(scheme="https", url=f"https://{HOST}/", ok=True, status=200,
                            markers=["access denied"], final_url=f"https://{HOST}/"),
    }
    report = make_report(http=http)
    finding = next(f for f in report.findings if f.topic == "http-filtered")
    assert "access denied" in finding.fact
