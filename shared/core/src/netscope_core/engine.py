"""Session orchestration: run every probe layer for one host and
assemble the :class:`~netscope_core.models.HostReport`.

This is the single entry point the CLI and the desktop application
use. It times each probe call, converts layer data into schema-shaped
:class:`~netscope_core.models.ProbeResult` objects, runs the verdict
classifier, and then the troubleshooting rules.
"""

from __future__ import annotations

import time

from . import rules, verdict as verdict_module
from .dnsprobe import DNSReport, probe_dns
from .errors import schema_error_kind
from .httpprobe import HTTPResult, probe_http
from .models import (
    CertificateInfo,
    HostReport,
    Measurement,
    PacketStats,
    ProbeError,
    ProbeResult,
    Target,
)
from .routeprobe import RouteResult, probe_route
from .stats import latency_stats
from .tcpprobe import TCPResult, probe_tcp
from .tlsprobe import TLSResult, probe_tls


def _error(kind: str | None, message: str | None, check: str) -> ProbeError | None:
    if kind is None and message is None:
        return None
    return ProbeError(kind=schema_error_kind(kind, check), message=message or "")


def _dns_result(report: DNSReport, duration_ms: float) -> ProbeResult:
    target = Target(host=report.hostname)
    resolved = report.resolved_addresses
    if report.suspect_poisoning:
        status, confidence = "blocked", "high"
        explanation = (
            "The system resolver's addresses share no address with any public "
            "resolver's answer; the DNS answer appears to be forged."
        )
        result_verdict: str | None = "DNS_POISONED"
    elif resolved:
        status, confidence = "ok", "high"
        explanation = f"Resolved to {', '.join(resolved)}."
        result_verdict = None
    elif report.resolvers and all(r.status == "nxdomain" for r in report.resolvers):
        status, confidence = "failed", "medium"
        explanation = "Every resolver answered NXDOMAIN: the name is reported as not existing."
        result_verdict = None
    elif report.resolvers and all(r.status in ("timeout", "error") for r in report.resolvers):
        status, confidence = "timeout", "medium"
        explanation = "No resolver answered: the system resolver failed and public resolver queries timed out or errored."
        result_verdict = None
    else:
        status, confidence = "failed", "low"
        explanation = "Resolution failed in inconsistent ways across resolvers."
        result_verdict = None

    measurement = None
    if resolved:
        resolver_name = "system" if report.system_addresses else next(
            (r.resolver for r in report.resolvers if r.status == "ok" and r.addresses), None
        )
        latency_value = report.system_latency_ms
        if latency_value is None:
            latency_value = next(
                (r.latency_ms for r in report.resolvers if r.latency_ms is not None), None
            )
        measurement = Measurement(
            addresses=resolved,
            resolver=resolver_name,
            latency=latency_stats([latency_value]) if latency_value is not None else None,
        )
    error = None
    if not resolved:
        error = ProbeError(
            kind="dns_failure",
            message=report.system_error or "no resolver returned addresses",
        )
    return ProbeResult(
        check="dns",
        status=status,
        target=target,
        protocol="dns",
        duration_ms=duration_ms,
        confidence=confidence,
        explanation=explanation,
        measurement=measurement,
        error=error,
        verdict=result_verdict,
    )


def _tcp_result(result: TCPResult, duration_ms: float) -> ProbeResult:
    target = Target(host=result.target, port=result.port)
    total = len(result.attempts)
    if result.successes == total and total > 0:
        status, confidence = "ok", "high"
        explanation = f"All {total} connection attempts to port {result.port} succeeded."
    elif result.successes > 0:
        status, confidence = "degraded", "medium"
        explanation = (
            f"{result.successes} of {total} connection attempts to port {result.port} "
            f"succeeded ({result.loss_pct:.0f}% loss, dominant error: {result.dominant_error})."
        )
    else:
        status, confidence = "failed", "high"
        explanation = (
            f"No connection to port {result.port} succeeded in {total} attempts "
            f"(dominant error: {result.dominant_error})."
        )
    measurement = Measurement(
        latency=result.latency,
        packets=PacketStats(sent=total, received=result.successes),
    )
    error = None
    if result.successes == 0 and result.dominant_error:
        message = next((a.error for a in result.attempts if a.error), None)
        error = _error(result.dominant_error, message, "tcp")
    return ProbeResult(
        check="tcp",
        status=status,
        target=target,
        protocol="tcp",
        duration_ms=duration_ms,
        confidence=confidence,
        explanation=explanation,
        measurement=measurement,
        error=error,
    )


def _tls_result(result: TLSResult, tcp443: TCPResult | None, duration_ms: float) -> ProbeResult:
    target = Target(host=result.hostname, port=result.port)
    if result.ok:
        total = (result.connect_ms or 0.0) + (result.handshake_ms or 0.0)
        measurement = Measurement(
            latency=latency_stats([total]),
            tls_version=result.protocol,
            certificate=CertificateInfo(
                subject=result.cert_subject,
                issuer=result.cert_issuer,
                not_after=result.cert_not_after_iso,
                days_remaining=result.cert_days_remaining,
            ),
        )
        return ProbeResult(
            check="tls",
            status="ok",
            target=target,
            protocol="tls",
            duration_ms=duration_ms,
            confidence="high",
            explanation=(
                f"TLS {result.protocol} handshake completed in "
                f"{result.handshake_ms:.0f} ms; certificate issued by "
                f"{result.cert_issuer or 'unknown issuer'}."
            ),
            measurement=measurement,
        )

    tcp_open = tcp443 is not None and tcp443.successes > 0
    if result.failed_phase == "handshake" and tcp_open and result.error_kind == "reset":
        status, confidence, result_verdict = "blocked", "high", "TLS_SNI_BLOCKED"
        explanation = (
            "The TCP connection opened, but the TLS handshake was reset once the "
            "site name (SNI) was sent — the signature of SNI-based filtering."
        )
    elif result.failed_phase == "handshake" and tcp_open and result.error_kind == "timeout":
        status, confidence, result_verdict = "timeout", "medium", "TLS_SNI_BLOCKED"
        explanation = (
            "The TCP connection opened, but the TLS handshake never completed; "
            "the site name (SNI) is the only new information at that point."
        )
    elif result.failed_phase == "handshake":
        status, confidence, result_verdict = "failed", "medium", None
        explanation = f"The TLS handshake failed ({result.error_kind}): {result.error}."
    else:
        status, confidence, result_verdict = "failed", "medium", None
        explanation = f"The TCP connection for the TLS handshake failed ({result.error_kind}): {result.error}."
    return ProbeResult(
        check="tls",
        status=status,
        target=target,
        protocol="tls",
        duration_ms=duration_ms,
        confidence=confidence,
        explanation=explanation,
        error=_error(result.error_kind, result.error, "tls"),
        verdict=result_verdict,
    )


def _http_result(result: HTTPResult, duration_ms: float) -> ProbeResult:
    from urllib.parse import urlsplit

    requested_host = urlsplit(result.url).hostname or ""
    target = Target(host=requested_host, url=result.url)
    protocol = "https" if result.scheme == "https" else "http"
    if result.ok:
        measurement = Measurement(
            latency=latency_stats([result.latency_ms]) if result.latency_ms is not None else None,
            bytes_received=result.size_bytes,
            http_status=result.status,
            redirects=result.redirects,
        )
        if result.markers:
            return ProbeResult(
                check="http",
                status="blocked",
                target=target,
                protocol=protocol,
                duration_ms=duration_ms,
                confidence="high" if result.scheme == "https" else "medium",
                explanation=(
                    f"The {result.scheme.upper()} response is a block page: it contains "
                    f"the filtering markers {', '.join(result.markers)}."
                ),
                measurement=measurement,
                verdict="HTTP_FILTERED",
            )
        return ProbeResult(
            check="http",
            status="ok",
            target=target,
            protocol=protocol,
            duration_ms=duration_ms,
            confidence="high",
            explanation=(
                f"{result.scheme.upper()} answered HTTP {result.status} "
                f"({result.size_bytes} bytes, {result.redirects} redirect(s))."
            ),
            measurement=measurement,
        )
    status = "timeout" if result.error_kind == "timeout" else "failed"
    return ProbeResult(
        check="http",
        status=status,
        target=target,
        protocol=protocol,
        duration_ms=duration_ms,
        confidence="medium",
        explanation=f"The {result.scheme.upper()} request failed ({result.error_kind}): {result.error}.",
        error=_error(result.error_kind, result.error, "http"),
    )


def _route_result(result: RouteResult, duration_ms: float) -> ProbeResult:
    all_rtts = [rtt for hop in result.hops for rtt in hop.rtt_ms]
    status = {"destination": "ok", "local": "degraded", "mid-path": "degraded"}.get(
        result.stop_point, "failed"
    )
    return ProbeResult(
        check="route",
        status=status,
        target=Target(host=result.host),
        protocol="icmp" if result.method == "icmp" else "tcp",
        duration_ms=duration_ms,
        confidence="medium" if result.method == "icmp" else "low",
        explanation=result.note,
        measurement=Measurement(latency=latency_stats(all_rtts)) if all_rtts else None,
        error=ProbeError(kind="unknown", message=result.error) if result.error else None,
    )


def _timed(fn, *args, **kwargs):
    start = time.perf_counter()
    value = fn(*args, **kwargs)
    return value, (time.perf_counter() - start) * 1000.0


def run_host_check(
    host: str,
    *,
    resolvers: list[str] | None = None,
    dns_timeout: float = 4.0,
    tcp_attempts: int = 4,
    tcp_timeout: float = 4.0,
    tls_timeout: float = 6.0,
    http_timeout: float = 10.0,
    include_route: bool = False,
    app_surface: str | None = None,
) -> HostReport:
    """Run the full layered check for ``host`` and assemble the report."""
    dns, dns_ms = _timed(probe_dns, host, resolvers=resolvers, timeout=dns_timeout)
    target = dns.resolved_addresses[0] if dns.resolved_addresses else host

    tcp: dict[int, TCPResult] = {}
    tcp_ms: dict[int, float] = {}
    for port in (443, 80):
        tcp[port], tcp_ms[port] = _timed(
            probe_tcp, target, port, attempts=tcp_attempts, timeout=tcp_timeout
        )

    tls: TLSResult | None = None
    tls_ms = 0.0
    if dns.resolved_addresses:
        tls, tls_ms = _timed(probe_tls, host, target=target, timeout=tls_timeout)

    http: dict[str, HTTPResult] = {}
    http_ms: dict[str, float] = {}
    for scheme in ("https", "http"):
        http[scheme], http_ms[scheme] = _timed(
            probe_http, host, scheme=scheme, timeout=http_timeout
        )

    route: RouteResult | None = None
    route_ms = 0.0
    if include_route:
        route, route_ms = _timed(probe_route, host)

    results: list[ProbeResult] = [_dns_result(dns, dns_ms)]
    for port in (443, 80):
        results.append(_tcp_result(tcp[port], tcp_ms[port]))
    if tls is not None:
        results.append(_tls_result(tls, tcp.get(443), tls_ms))
    for scheme in ("https", "http"):
        results.append(_http_result(http[scheme], http_ms[scheme]))
    if route is not None:
        results.append(_route_result(route, route_ms))

    session_verdict = verdict_module.classify(dns, tcp, tls, http)
    report = HostReport(
        host=host,
        dns=dns,
        tcp=tcp,
        tls=tls,
        http=http,
        route=route,
        results=results,
        verdict=session_verdict,
        app_surface=app_surface,
    )
    report.findings = rules.analyze(report)
    return report
