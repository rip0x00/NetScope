"""Plain-text formatting for core results.

Tables are aligned with spaces; there are no external formatting
dependencies. Colour, when enabled by the caller (a TTY and no
``--no-color``), is applied only to status words and the verdict code.
"""

from __future__ import annotations

from netscope_core.models import HostReport
from netscope_core.routeprobe import RouteResult
from netscope_core.stats import LatencyStats

_CODES = {"ok": "32", "degraded": "33", "timeout": "33", "warning": "33"}


def paint(text: str, status: str | None, enabled: bool) -> str:
    if not enabled:
        return text
    code = _CODES.get(status or "", "31")
    return f"\033[{code}m{text}\033[0m"


def fmt_ms(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f} ms"


def stats_lines(stats: LatencyStats, loss_pct: float | None = None) -> list[str]:
    """The full latency distribution as aligned label/value lines."""
    lines = [f"  samples   {stats.count}"]
    if loss_pct is not None:
        lines.append(f"  loss      {loss_pct:.1f}%")
    if stats.count:
        lines += [
            f"  min       {fmt_ms(stats.min)}",
            f"  average   {fmt_ms(stats.avg)}",
            f"  median    {fmt_ms(stats.median)}",
            f"  p95       {fmt_ms(stats.p95)}",
            f"  max       {fmt_ms(stats.max)}",
            f"  stddev    {fmt_ms(stats.stddev)}",
            f"  jitter    avg {fmt_ms(stats.jitter_avg)}, max {fmt_ms(stats.jitter_max)}",
        ]
    return lines


def format_host_report(report: HostReport, color: bool = False) -> str:
    """The full layered check for one host, as readable text."""
    lines: list[str] = []
    lines.append(f"NetScope diagnose — {report.host}")
    lines.append(f"Generated {report.generated_at} · platform {report.platform_os}")
    lines.append("")
    verdict = report.verdict
    lines.append(
        f"Verdict  {paint(verdict.code, 'ok' if verdict.code == 'OK' else 'failed', color)}"
        f" (confidence: {verdict.confidence})"
    )
    lines.append(verdict.explanation)
    lines.append("")

    lines.append("Checks")
    width = max((len(r.check) for r in report.results), default=5)
    for result in report.results:
        status = paint(f"{result.status:<8}", result.status, color)
        lines.append(
            f"  {result.check:<{width}}  {result.protocol:<5}  {status}  "
            f"{result.duration_ms:>7.0f} ms  {result.explanation}"
        )
    lines.append("")

    dns = report.dns
    lines.append("DNS")
    if dns.system_addresses:
        lines.append(
            f"  system      {', '.join(dns.system_addresses)} ({fmt_ms(dns.system_latency_ms, 0)})"
        )
    else:
        lines.append(f"  system      failed ({dns.system_error})")
    for resolver in dns.resolvers:
        if resolver.status == "ok" and resolver.addresses:
            detail = ", ".join(resolver.addresses)
        else:
            detail = resolver.status
        lines.append(f"  {resolver.resolver:<11} {detail}")
    if dns.suspect_poisoning:
        lines.append(
            "  note: the system answer shares no address with any public resolver's answer."
        )
    if dns.partial_nxdomain:
        lines.append(
            "  note: some resolvers answered NXDOMAIN while others returned addresses."
        )
    lines.append("")

    lines.append("TCP")
    for port in (443, 80):
        result = report.tcp.get(port)
        if result is None:
            continue
        total = len(result.attempts)
        if result.successes:
            lines.append(
                f"  port {port:<5} {result.successes}/{total} connected, "
                f"avg {fmt_ms(result.avg_latency_ms, 0)}, loss {result.loss_pct:.0f}%"
            )
        else:
            lines.append(
                f"  port {port:<5} 0/{total} connected "
                f"(dominant error: {result.dominant_error})"
            )
    lines.append("")

    lines.append("TLS")
    tls = report.tls
    if tls is None:
        lines.append("  not run (the name did not resolve)")
    elif tls.ok:
        lines.append(
            f"  handshake   TLS {tls.protocol}, completed in {fmt_ms(tls.handshake_ms, 0)}"
        )
        lines.append(f"  issuer      {tls.cert_issuer}")
        lines.append(
            f"  expires     {tls.cert_not_after} ({tls.cert_days_remaining} days remaining)"
        )
    else:
        lines.append(
            f"  handshake   failed in {tls.failed_phase} phase ({tls.error_kind}): {tls.error}"
        )
    lines.append("")

    lines.append("HTTP")
    for scheme in ("https", "http"):
        result = report.http.get(scheme)
        if result is None:
            continue
        if result.ok:
            line = (
                f"  {scheme:<11} HTTP {result.status}, {result.size_bytes} bytes, "
                f"{result.redirects} redirect(s)"
            )
            if result.markers:
                line += f" — block-page markers: {', '.join(result.markers)}"
            lines.append(line)
        else:
            lines.append(f"  {scheme:<11} failed ({result.error_kind}): {result.error}")
    lines.append("")

    if report.route is not None:
        lines.append(format_route(report.route))
        lines.append("")

    if report.findings:
        lines.append("Troubleshooting")
        for index, finding in enumerate(report.findings, start=1):
            lines.append(f"  {index}. {finding.topic} (confidence: {finding.confidence})")
            lines.append(f"     Measured: {finding.fact}")
            if finding.possible_causes:
                lines.append(f"     Possible causes: {'; '.join(finding.possible_causes)}")
            if finding.recommendations:
                lines.append("     Suggested verification steps:")
                for rec in finding.recommendations:
                    lines.append(f"       - {rec}")
        lines.append("")
    return "\n".join(lines)


def format_route(result: RouteResult) -> str:
    """A hop table plus the stop-point summary for one route trace."""
    lines: list[str] = []
    target = result.host
    if result.destination_ip:
        target += f" ({result.destination_ip})"
    lines.append(f"Route to {target}")
    if result.method == "icmp":
        lines.append("Method: ICMP echo probes with increasing TTL")
    else:
        lines.append(
            "Method: TCP connect probes with limited TTL "
            "(ICMP replies cannot be read without raw-socket permission)"
        )
    if result.error:
        lines.append(f"Error: {result.error}")
        return "\n".join(lines)
    lines.append("")
    lines.append("  Hop  Address           Round-trip times")
    for hop in result.hops:
        address = hop.ip if hop.ip else "*"
        if hop.rtt_ms:
            rtts = "  ".join(f"{rtt:.1f} ms" for rtt in hop.rtt_ms)
        else:
            rtts = "no answer"
        lines.append(f"  {hop.ttl:<4} {address:<17} {rtts}")
    lines.append("")
    lines.append(f"Stops: {result.stop_point} — {result.note}")
    return "\n".join(lines)
