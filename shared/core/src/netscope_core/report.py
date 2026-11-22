"""Report renderers: JSON, Markdown, HTML and CSV from a HostReport.

The JSON form is the report schema itself (``HostReport.to_dict()``).
Markdown and HTML are for people; CSV flattens the schema results for
spreadsheets and scripts. The HTML is a single standalone file with
inline CSS taken from the design tokens in
``assets/branding/tokens.json`` (dark theme, restrained, no
gradients); if the tokens file cannot be found — for example when the
package is installed on its own — the same values are used from the
embedded copy below.
"""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path

from .models import HostReport

# Embedded copy of the dark design tokens (assets/branding/tokens.json).
_FALLBACK_TOKENS = {
    "background": "#101419",
    "backgroundSecondary": "#151B22",
    "surface": "#1B232C",
    "surfaceElevated": "#222C37",
    "text": "#EDF2F7",
    "textSecondary": "#9AA8B7",
    "textMuted": "#687787",
    "accent": "#3987D8",
    "accentSecondary": "#36A7B8",
    "success": "#36A879",
    "warning": "#D69A42",
    "error": "#D65B61",
    "border": "#303B47",
}

_STATUS_COLOR_KEY = {
    "ok": "success",
    "degraded": "warning",
    "timeout": "warning",
    "failed": "error",
    "blocked": "error",
    "error": "error",
    "skipped": "textMuted",
}


def _load_tokens() -> dict[str, str]:
    tokens_path = (
        Path(__file__).resolve().parents[4] / "assets" / "branding" / "tokens.json"
    )
    try:
        data = json.loads(tokens_path.read_text(encoding="utf-8"))
        dark = data["color"]["dark"]
        return {**_FALLBACK_TOKENS, **dark}
    except (OSError, ValueError, KeyError):
        return dict(_FALLBACK_TOKENS)


def render_json(report: HostReport) -> str:
    """The report in its schema form, as JSON text."""
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: HostReport) -> str:
    """A human-readable Markdown report."""
    lines: list[str] = []
    lines.append(f"# NetScope report — {report.host}")
    lines.append("")
    lines.append(f"Generated {report.generated_at} by NetScope {report.to_dict()['tool']['version']} "
                 f"on {report.platform_os}.")
    lines.append("")
    lines.append(f"**Verdict: {report.verdict.code}** (confidence: {report.verdict.confidence})")
    lines.append("")
    lines.append(report.verdict.explanation)
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Check | Protocol | Status | Duration | Summary |")
    lines.append("| --- | --- | --- | --- | --- |")
    for result in report.results:
        lines.append(
            f"| {_cell(result.check)} | {_cell(result.protocol)} | {_cell(result.status)} "
            f"| {result.duration_ms:.0f} ms | {_cell(result.explanation)} |"
        )
    lines.append("")

    dns = report.dns
    lines.append("## DNS detail")
    lines.append("")
    system = ", ".join(dns.system_addresses) if dns.system_addresses else f"failed ({dns.system_error})"
    lines.append(f"- System resolver: {system}")
    for resolver in dns.resolvers:
        addresses = ", ".join(resolver.addresses) if resolver.addresses else resolver.status
        lines.append(f"- {resolver.resolver}: {addresses}")
    if dns.suspect_poisoning:
        lines.append("- The system resolver's answer shares no address with any public resolver's answer.")
    lines.append("")

    if report.route is not None:
        route = report.route
        lines.append("## Route")
        lines.append("")
        lines.append(f"Method: {route.method}. {route.note}")
        lines.append("")
        lines.append("| Hop | Address | Average RTT |")
        lines.append("| --- | --- | --- |")
        for hop in route.hops:
            avg = f"{hop.avg_rtt_ms:.1f} ms" if hop.avg_rtt_ms is not None else "—"
            lines.append(f"| {hop.ttl} | {hop.ip or 'no answer'} | {avg} |")
        lines.append("")

    if report.findings:
        lines.append("## Troubleshooting")
        lines.append("")
        for index, finding in enumerate(report.findings, start=1):
            lines.append(f"### {index}. {finding.topic} (confidence: {finding.confidence})")
            lines.append("")
            lines.append(f"Measured: {finding.fact}")
            lines.append("")
            if finding.possible_causes:
                lines.append("Possible causes:")
                for cause in finding.possible_causes:
                    lines.append(f"- {cause}")
                lines.append("")
            if finding.recommendations:
                lines.append("Suggested verification steps:")
                for rec in finding.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Method: DNS is compared between the system resolver and public resolvers over "
        "UDP/53. Latency is TCP connect time unless a check states otherwise. A verdict "
        "names the first layer that explains the failure; the checks above are the evidence."
    )
    lines.append("")
    return "\n".join(lines)


_CSV_COLUMNS = [
    "timestamp", "check", "protocol", "host", "port", "status", "duration_ms",
    "confidence", "verdict", "error_kind", "addresses", "latency_avg_ms",
    "loss_percent", "http_status", "bytes_received", "tls_version",
]


def render_csv(report: HostReport) -> str:
    """One flat row per check result, for spreadsheets and scripts."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_COLUMNS)
    writer.writeheader()
    for result in report.results:
        data = result.to_dict()
        measurement = data.get("measurement") or {}
        latency = measurement.get("latency") or {}
        packets = measurement.get("packets") or {}
        writer.writerow({
            "timestamp": data["timestamp"],
            "check": data["check"],
            "protocol": data["protocol"],
            "host": data["target"]["host"],
            "port": data["target"].get("port", ""),
            "status": data["status"],
            "duration_ms": data["durationMs"],
            "confidence": data["confidence"],
            "verdict": data.get("verdict") or "",
            "error_kind": (data.get("error") or {}).get("kind", ""),
            "addresses": ";".join(measurement.get("addresses", [])),
            "latency_avg_ms": latency.get("avg", ""),
            "loss_percent": packets.get("lossPercent", ""),
            "http_status": measurement.get("httpStatus", ""),
            "bytes_received": measurement.get("bytesReceived", ""),
            "tls_version": measurement.get("tlsVersion", ""),
        })
    return buffer.getvalue()


def render_html(report: HostReport) -> str:
    """A standalone HTML report using the design tokens (dark theme)."""
    tokens = _load_tokens()
    esc = html.escape
    verdict = report.verdict
    verdict_color = tokens["success"] if verdict.code == "OK" else tokens["error"]

    rows = []
    for result in report.results:
        color = tokens[_STATUS_COLOR_KEY.get(result.status, "textMuted")]
        rows.append(
            "<tr>"
            f"<td>{esc(result.check)}</td>"
            f"<td>{esc(result.protocol)}</td>"
            f'<td style="color:{color}">{esc(result.status)}</td>'
            f"<td class=\"num\">{result.duration_ms:.0f} ms</td>"
            f"<td>{esc(result.explanation)}</td>"
            "</tr>"
        )

    findings_html = ""
    if report.findings:
        items = []
        for finding in report.findings:
            causes = "".join(f"<li>{esc(c)}</li>" for c in finding.possible_causes)
            recs = "".join(f"<li>{esc(r)}</li>" for r in finding.recommendations)
            items.append(
                f"<section class=\"finding\"><h3>{esc(finding.topic)} "
                f"<span class=\"muted\">(confidence: {esc(finding.confidence)})</span></h3>"
                f"<p><strong>Measured:</strong> {esc(finding.fact)}</p>"
                f"<p class=\"muted\">Possible causes</p><ul>{causes}</ul>"
                f"<p class=\"muted\">Suggested verification steps</p><ul>{recs}</ul></section>"
            )
        findings_html = "<h2>Troubleshooting</h2>" + "".join(items)

    css = f"""
    body {{ background: {tokens['background']}; color: {tokens['text']};
           font-family: Inter, -apple-system, 'Segoe UI', sans-serif; margin: 0; }}
    main {{ max-width: 880px; margin: 0 auto; padding: 32px 24px 48px; }}
    h1 {{ font-size: 28px; font-weight: 600; margin: 0 0 4px; }}
    h2 {{ font-size: 20px; font-weight: 600; margin: 32px 0 12px; }}
    h3 {{ font-size: 16px; font-weight: 600; margin: 0 0 8px; }}
    .muted {{ color: {tokens['textMuted']}; }}
    .secondary {{ color: {tokens['textSecondary']}; }}
    .verdict {{ background: {tokens['surface']}; border: 1px solid {tokens['border']};
                border-left: 4px solid {verdict_color}; padding: 16px; margin: 24px 0; }}
    .verdict .code {{ font-size: 20px; font-weight: 600; color: {verdict_color}; }}
    table {{ width: 100%; border-collapse: collapse; background: {tokens['surface']};
             border: 1px solid {tokens['border']}; }}
    th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid {tokens['border']};
              font-size: 14px; vertical-align: top; }}
    th {{ color: {tokens['textSecondary']}; font-weight: 600; }}
    td.num {{ font-family: 'JetBrains Mono', ui-monospace, monospace; white-space: nowrap; }}
    .finding {{ background: {tokens['surface']}; border: 1px solid {tokens['border']};
                padding: 16px; margin: 12px 0; }}
    ul {{ margin: 4px 0 12px; padding-left: 20px; }}
    footer {{ color: {tokens['textMuted']}; font-size: 12px; margin-top: 40px; }}
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NetScope report — {esc(report.host)}</title>
<style>{css}</style>
</head>
<body>
<main>
<h1>NetScope report</h1>
<p class="secondary">{esc(report.host)} · generated {esc(report.generated_at)} · {esc(report.platform_os)}</p>
<div class="verdict">
<div class="code">{esc(verdict.code)}</div>
<p>{esc(verdict.explanation)}</p>
<p class="muted">Confidence: {esc(verdict.confidence)}</p>
</div>
<h2>Checks</h2>
<table>
<tr><th>Check</th><th>Protocol</th><th>Status</th><th>Duration</th><th>Summary</th></tr>
{''.join(rows)}
</table>
{findings_html}
<footer>DNS is compared between the system resolver and public resolvers over UDP/53.
Latency is TCP connect time unless a check states otherwise. A verdict names the first
layer that explains the failure; the checks above are the evidence.</footer>
</main>
</body>
</html>
"""
