"""CLI tests: parsing, formatting, exit codes, JSON output.

Every core entry point the CLI calls is monkeypatched, so no test
touches the network.
"""

from __future__ import annotations

import json

import pytest

from netscope_cli import main
from netscope_core.dnsprobe import DNSRecord, DNSReport, LookupResult, ResolverResult
from netscope_core.httpprobe import HTTPResult
from netscope_core.interfaces import InterfaceInfo, NetworkInventory
from netscope_core.models import HostReport
from netscope_core.routeprobe import Hop, RouteResult
from netscope_core.rules import Finding
from netscope_core.speedtest import SpeedResult
from netscope_core.tcpprobe import Attempt, TCPResult
from netscope_core.verdict import Verdict


# ---------------------------------------------------------------------------
# Fixtures built from real core objects
# ---------------------------------------------------------------------------

def make_report(verdict_code: str = "OK") -> HostReport:
    dns = DNSReport(
        hostname="example.com",
        system_addresses=["93.184.216.34"],
        system_latency_ms=8.0,
        resolvers=[
            ResolverResult(
                resolver="1.1.1.1", status="ok",
                addresses=["93.184.216.34"], latency_ms=11.0,
            )
        ],
    )
    tcp = {
        443: TCPResult(target="93.184.216.34", port=443,
                       attempts=[Attempt(ok=True, latency_ms=20.0)]),
        80: TCPResult(target="93.184.216.34", port=80,
                      attempts=[Attempt(ok=True, latency_ms=21.0)]),
    }
    http = {
        "https": HTTPResult(scheme="https", url="https://example.com",
                            ok=True, status=200, size_bytes=1234),
        "http": HTTPResult(scheme="http", url="http://example.com",
                           ok=True, status=200, size_bytes=1234),
    }
    verdict = Verdict(code=verdict_code, explanation="All layers answered.",
                      confidence="high")
    return HostReport(
        host="example.com", dns=dns, tcp=tcp, tls=None, http=http,
        results=[], verdict=verdict,
        findings=[Finding(topic="dns-consistency", fact="Answers agree.",
                          possible_causes=["none observed"],
                          recommendations=["No action needed."])],
    )


def fake_inventory() -> NetworkInventory:
    return NetworkInventory(
        hostname="testhost",
        interfaces=[InterfaceInfo(name="lo", index=1, is_loopback=True,
                                  addresses=["127.0.0.1"])],
        local_addresses=["127.0.0.1"],
        outbound_ipv4="10.0.0.5",
        default_gateway="10.0.0.1",
        notes=[],
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_parse_defaults():
    args = main.build_parser().parse_args(["diagnose", "example.com"])
    assert args.command == "diagnose"
    assert args.json is False
    args = main.build_parser().parse_args(["latency", "example.com"])
    assert args.count == 10 and args.port == 443


def test_parse_dns_type_and_resolver():
    args = main.build_parser().parse_args(
        ["dns", "example.com", "--type", "MX", "--resolver", "8.8.8.8"])
    assert args.type == "MX" and args.resolver == "8.8.8.8"


def test_parse_rejects_bad_dns_type():
    with pytest.raises(SystemExit) as excinfo:
        main.build_parser().parse_args(["dns", "example.com", "--type", "BOGUS"])
    assert excinfo.value.code == 2


def test_no_command_returns_2(capsys):
    assert main.main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()


def test_parse_host_strips_url_and_port():
    assert main.parse_host("https://example.com/path?q=1") == "example.com"
    assert main.parse_host("example.com:8443/x") == "example.com"
    assert main.parse_host("example.com.") == "example.com"


# ---------------------------------------------------------------------------
# diagnose
# ---------------------------------------------------------------------------

def test_diagnose_ok_exit_0(monkeypatch, capsys):
    monkeypatch.setattr(main.engine, "run_host_check",
                        lambda host, app_surface=None: make_report("OK"))
    assert main.main(["diagnose", "example.com"]) == 0
    out = capsys.readouterr().out
    assert "Verdict" in out and "OK" in out
    assert "Troubleshooting" in out


def test_diagnose_failure_exit_1(monkeypatch, capsys):
    monkeypatch.setattr(main.engine, "run_host_check",
                        lambda host, app_surface=None: make_report("TCP_BLOCKED"))
    assert main.main(["diagnose", "example.com"]) == 1
    assert "TCP_BLOCKED" in capsys.readouterr().out


def test_diagnose_json_is_valid(monkeypatch, capsys):
    monkeypatch.setattr(main.engine, "run_host_check",
                        lambda host, app_surface=None: make_report("OK"))
    assert main.main(["diagnose", "example.com", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["verdict"] == "OK"
    assert data["tool"]["name"] == "NetScope"


def test_diagnose_report_files(monkeypatch, tmp_path):
    monkeypatch.setattr(main.engine, "run_host_check",
                        lambda host, app_surface=None: make_report("OK"))
    md = tmp_path / "r.md"
    assert main.main(["diagnose", "example.com", "--report", str(md)]) == 0
    assert md.read_text(encoding="utf-8").startswith("# NetScope report")

    js = tmp_path / "r.json"
    assert main.main(["diagnose", "example.com", "--report", str(js)]) == 0
    json.loads(js.read_text(encoding="utf-8"))

    csv_path = tmp_path / "r.csv"
    assert main.main(["diagnose", "example.com", "--report", str(csv_path)]) == 0
    assert csv_path.read_text(encoding="utf-8").startswith("timestamp,check")

    html_path = tmp_path / "r.html"
    assert main.main(["diagnose", "example.com", "--report", str(html_path)]) == 0
    assert "<!DOCTYPE html>" in html_path.read_text(encoding="utf-8")


def test_diagnose_report_bad_extension(monkeypatch, tmp_path):
    monkeypatch.setattr(main.engine, "run_host_check",
                        lambda host, app_surface=None: make_report("OK"))
    target = tmp_path / "r.txt"
    assert main.main(["diagnose", "example.com", "--report", str(target)]) == 2
    assert not target.exists()


# ---------------------------------------------------------------------------
# dns
# ---------------------------------------------------------------------------

def _fake_lookup_ok(name, qtype, resolver="1.1.1.1"):
    return LookupResult(
        name=name, qtype=qtype, resolver=resolver, status="ok",
        records=[DNSRecord(name, qtype, "10 mail.example.com", 300)],
        latency_ms=9.0,
    )


def test_dns_mx_records(monkeypatch, capsys):
    monkeypatch.setattr(main, "lookup", _fake_lookup_ok)
    assert main.main(["dns", "example.com", "--type", "MX"]) == 0
    out = capsys.readouterr().out
    assert "mail.example.com" in out
    assert "Resolver comparison" not in out  # comparison is address types only


def test_dns_a_includes_resolver_comparison(monkeypatch, capsys):
    def fake_lookup(name, qtype, resolver="1.1.1.1"):
        return LookupResult(
            name=name, qtype=qtype, resolver=resolver, status="ok",
            records=[DNSRecord(name, "A", "93.184.216.34", 300)], latency_ms=9.0)

    def fake_probe_dns(host, timeout=4.0):
        return DNSReport(
            hostname=host, system_addresses=["93.184.216.34"],
            resolvers=[ResolverResult("1.1.1.1", "ok", ["93.184.216.34"])])

    monkeypatch.setattr(main, "lookup", fake_lookup)
    monkeypatch.setattr(main, "probe_dns", fake_probe_dns)
    assert main.main(["dns", "example.com"]) == 0
    out = capsys.readouterr().out
    assert "Resolver comparison" in out
    assert "agrees with at least one public resolver" in out


def test_dns_timeout_exit_1(monkeypatch, capsys):
    monkeypatch.setattr(
        main, "lookup",
        lambda name, qtype, resolver="1.1.1.1": LookupResult(
            name=name, qtype=qtype, resolver=resolver, status="timeout"))
    assert main.main(["dns", "example.com", "--type", "TXT"]) == 1
    assert "timeout" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# latency
# ---------------------------------------------------------------------------

def _fake_tcp_mixed(target, port, attempts=4, timeout=4.0):
    return TCPResult(target=target, port=port, attempts=[
        Attempt(ok=True, latency_ms=10.0),
        Attempt(ok=True, latency_ms=20.0),
        Attempt(ok=False, error_kind="timeout", error="timed out"),
    ])


def test_latency_text_stats(monkeypatch, capsys):
    monkeypatch.setattr(main, "probe_tcp", _fake_tcp_mixed)
    assert main.main(["latency", "example.com", "--count", "3"]) == 0
    out = capsys.readouterr().out
    assert "median" in out and "p95" in out and "jitter" in out
    assert "33.3%" in out  # one of three attempts lost


def test_latency_json(monkeypatch, capsys):
    monkeypatch.setattr(main, "probe_tcp", _fake_tcp_mixed)
    assert main.main(["latency", "example.com", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["sent"] == 3 and data["received"] == 2
    assert data["latency"]["count"] == 2


def test_latency_all_failed_exit_1(monkeypatch):
    monkeypatch.setattr(
        main, "probe_tcp",
        lambda target, port, attempts=4, timeout=4.0: TCPResult(
            target=target, port=port,
            attempts=[Attempt(ok=False, error_kind="refused", error="refused")]))
    assert main.main(["latency", "example.com"]) == 1


# ---------------------------------------------------------------------------
# route / interfaces / status / speed / monitor / version
# ---------------------------------------------------------------------------

def test_route_reached(monkeypatch, capsys):
    def fake_route(host, max_hops=30):
        return RouteResult(
            host=host, destination_ip="93.184.216.34", method="tcp",
            hops=[Hop(ttl=1, ip="93.184.216.34", rtt_ms=[1.2], probes_sent=1)],
            reached=True, stop_point="destination",
            note="The destination answered at hop 1; the full path responded.")

    monkeypatch.setattr(main, "probe_route", fake_route)
    assert main.main(["route", "example.com"]) == 0
    out = capsys.readouterr().out
    assert "Route to example.com (93.184.216.34)" in out
    assert "destination" in out


def test_route_not_reached_exit_1(monkeypatch):
    def fake_route(host, max_hops=30):
        return RouteResult(host=host, destination_ip="93.184.216.34",
                           method="tcp", hops=[], reached=False,
                           stop_point="no-response", note="No probe answered.")

    monkeypatch.setattr(main, "probe_route", fake_route)
    assert main.main(["route", "example.com"]) == 1


def test_interfaces_table_and_json(monkeypatch, capsys):
    monkeypatch.setattr(main, "list_interfaces", fake_inventory)
    assert main.main(["interfaces"]) == 0
    out = capsys.readouterr().out
    assert "testhost" in out and "10.0.0.1" in out
    assert main.main(["interfaces", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["hostname"] == "testhost"
    assert data["interfaces"][0]["name"] == "lo"


def test_status_ok(monkeypatch, capsys):
    monkeypatch.setattr(main, "list_interfaces", fake_inventory)
    monkeypatch.setattr(
        main, "probe_dns",
        lambda host, timeout=3.0: DNSReport(
            hostname=host, system_addresses=["93.184.216.34"],
            system_latency_ms=5.0))
    monkeypatch.setattr(
        main, "probe_tcp",
        lambda target, port, attempts=4, timeout=3.0: TCPResult(
            target=target, port=port,
            attempts=[Attempt(ok=True, latency_ms=15.0)]))
    assert main.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "93.184.216.34" in out and "TCP 443" in out


def test_speed_prints_throughput(monkeypatch, capsys):
    monkeypatch.setattr(
        main, "run_speed_test",
        lambda config: SpeedResult(
            download_mbps=50.0, upload_mbps=10.0,
            bytes_downloaded=1000, bytes_uploaded=500,
            download_endpoint="https://example.test/down",
            upload_endpoint="https://example.test/up"))
    assert main.main(["speed"]) == 0
    out = capsys.readouterr().out
    assert "50.00 Mbps" in out and "10.00 Mbps" in out


def test_speed_nothing_measured_exit_1(monkeypatch):
    monkeypatch.setattr(main, "run_speed_test", lambda config: SpeedResult())
    assert main.main(["speed"]) == 1


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


def test_monitor_loop_with_fake_sampler():
    samples = iter([10.0, None, 12.0, 11.0])
    clock = FakeClock()
    lines: list[str] = []
    sent, received = main.monitor_loop(
        "example.com", interval=1.0, duration=3.0,
        sampler=lambda: next(samples), emit=lines.append,
        sleep=clock.sleep, now=clock.now)
    assert (sent, received) == (4, 3)
    assert "timeout" in lines[1]
    assert "50%" in lines[1]  # one of two samples lost at that point
    assert "25%" in lines[3]  # one of four lost by the end


def test_version(capsys):
    assert main.main(["version"]) == 0
    out = capsys.readouterr().out
    assert "NetScope CLI 0.1.0" in out
    assert "netscope-core" in out
