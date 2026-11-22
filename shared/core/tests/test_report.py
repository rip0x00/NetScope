"""Model serialisation validated against the shared schemas, and the
four renderers exercised on a fabricated report."""

import csv
import io
import json

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from netscope_core.dnsprobe import DNSReport, ResolverResult
from netscope_core.models import (
    CertificateInfo,
    HostReport,
    Measurement,
    PacketStats,
    ProbeResult,
    Target,
)
from netscope_core.report import render_csv, render_html, render_json, render_markdown
from netscope_core.rules import Finding
from netscope_core.stats import latency_stats
from netscope_core.verdict import Verdict

HOST = "example.com"


def sample_results():
    dns = ProbeResult(
        check="dns", status="ok", target=Target(host=HOST), protocol="dns",
        duration_ms=12.0, confidence="high",
        explanation="Resolved to 93.184.216.34.",
        measurement=Measurement(
            addresses=["93.184.216.34"], resolver="system",
            latency=latency_stats([12.0]),
        ),
    )
    tcp = ProbeResult(
        check="tcp", status="degraded", target=Target(host="93.184.216.34", port=443),
        protocol="tcp", duration_ms=90.0, confidence="medium",
        explanation="3 of 4 attempts succeeded.",
        measurement=Measurement(
            latency=latency_stats([10.0, 11.0, 12.0]),
            packets=PacketStats(sent=4, received=3),
        ),
    )
    tls = ProbeResult(
        check="tls", status="ok", target=Target(host=HOST, port=443), protocol="tls",
        duration_ms=40.0, confidence="high", explanation="Handshake completed.",
        measurement=Measurement(
            tls_version="TLSv1.3",
            certificate=CertificateInfo(
                subject="CN=example.com", issuer="CN=Example CA",
                not_after="2027-01-01T00:00:00+00:00", days_remaining=400,
            ),
        ),
    )
    failed = ProbeResult(
        check="http", status="failed", target=Target(host=HOST, url=f"http://{HOST}/"),
        protocol="http", duration_ms=4000.0, confidence="medium",
        explanation="The HTTP request failed (timeout).",
    )
    from netscope_core.models import ProbeError

    failed.error = ProbeError(kind="timeout", message="timed out")
    return [dns, tcp, tls, failed]


def sample_report():
    report = HostReport(
        host=HOST,
        dns=DNSReport(
            hostname=HOST,
            system_addresses=["93.184.216.34"],
            resolvers=[ResolverResult(resolver="1.1.1.1", status="ok",
                                      addresses=["93.184.216.34"], latency_ms=9.0)],
        ),
        tcp={},
        tls=None,
        http={},
        results=sample_results(),
        verdict=Verdict("OK", "The site loads normally from this network.", "high"),
        findings=[Finding(
            topic="instability",
            fact="3 of 4 TCP connections to port 443 succeeded (25% loss).",
            possible_causes=["An unstable link."],
            recommendations=["Repeat the test."],
            confidence="medium",
        )],
        platform_os="linux",
    )
    return report


def test_report_dict_validates_against_schemas(report_schema, result_schema, schema_registry):
    report = sample_report()
    data = report.to_dict()
    validator = Draft202012Validator(
        report_schema, registry=schema_registry, format_checker=FormatChecker()
    )
    errors = list(validator.iter_errors(data))
    assert errors == []

    result_validator = Draft202012Validator(
        result_schema, registry=schema_registry, format_checker=FormatChecker()
    )
    for result in data["results"]:
        assert list(result_validator.iter_errors(result)) == []


def test_summary_carries_verdict_and_recommendations():
    data = sample_report().to_dict()
    assert data["summary"]["verdict"] == "OK"
    assert data["summary"]["recommendations"] == ["Repeat the test."]
    assert data["tool"] == {"name": "NetScope", "version": "0.1.0"}
    assert data["schemaVersion"] == "1.0"


def test_measurement_dict_drops_unset_fields():
    measurement = Measurement(addresses=["192.0.2.1"]).to_dict()
    assert measurement == {"addresses": ["192.0.2.1"]}


def test_render_json_round_trips():
    report = sample_report()
    assert json.loads(render_json(report)) == report.to_dict()


def test_render_markdown_contents():
    text = render_markdown(sample_report())
    assert f"# NetScope report — {HOST}" in text
    assert "**Verdict: OK**" in text
    assert "System resolver: 93.184.216.34" in text
    assert "## Troubleshooting" in text
    assert "Measured: 3 of 4 TCP connections" in text


def test_render_html_uses_tokens_without_gradients():
    page = render_html(sample_report())
    assert "#101419" in page  # dark background token
    assert "#3987D8" in page or "#36A879" in page  # accent / success tokens
    assert "linear-gradient" not in page
    assert HOST in page
    assert "OK" in page


def test_render_html_escapes_host():
    report = sample_report()
    report.host = "<script>alert(1)</script>"
    page = render_html(report)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_render_csv_rows():
    text = render_csv(sample_report())
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 4
    dns_row = rows[0]
    assert dns_row["check"] == "dns"
    assert dns_row["addresses"] == "93.184.216.34"
    tcp_row = rows[1]
    assert tcp_row["loss_percent"] == "25.0"
    assert tcp_row["latency_avg_ms"] == "11.0"
    http_row = rows[3]
    assert http_row["error_kind"] == "timeout"
