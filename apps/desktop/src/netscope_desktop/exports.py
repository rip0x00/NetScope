"""Report export in Markdown, HTML, JSON, CSV and PDF.

Fresh results are :class:`~netscope_core.models.HostReport` objects
and use the core renderers. Stored history results are schema dicts
(the JSON form); the dict renderers below produce the same sections
from that form, so a report exports identically whether it was just
measured or loaded from history.

PDF is produced by printing the HTML report through Qt's
``QPdfWriter``; that function is the only Qt-dependent part and it
imports Qt lazily, so the text formats stay usable (and testable)
without a GUI.
"""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path

from netscope_core.models import HostReport
from netscope_core.report import render_csv, render_html, render_json, render_markdown

FORMATS = ("md", "html", "json", "csv", "pdf")

_SUFFIX = {"md": ".md", "html": ".html", "json": ".json", "csv": ".csv", "pdf": ".pdf"}


def default_filename(report_host: str, fmt: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ".-" else "_" for ch in report_host)
    return f"netscope-{safe}{_SUFFIX[fmt]}"


# -- schema-dict renderers ---------------------------------------------------


def _summary_lines(data: dict) -> list[str]:
    summary = data.get("summary", {})
    return [
        f"Verdict: {summary.get('verdict', 'UNKNOWN')} "
        f"(confidence: {summary.get('confidence', '—')})",
        str(summary.get("explanation", "")),
    ]


def render_markdown_from_dict(data: dict) -> str:
    host = data.get("target", {}).get("host", "unknown")
    lines = [f"# NetScope report — {host}", ""]
    lines.append(
        f"Generated {data.get('generatedAt', '')} by NetScope "
        f"{data.get('tool', {}).get('version', '')} on "
        f"{data.get('platform', {}).get('os', '')}."
    )
    lines.append("")
    for line in _summary_lines(data):
        lines.append(f"**{line}**" if line.startswith("Verdict") else line)
    lines.append("")
    lines.append("| Check | Status | Target | Duration (ms) | Explanation |")
    lines.append("|---|---|---|---|---|")
    for result in data.get("results", []):
        target = result.get("target", {}).get("host", "")
        if result.get("target", {}).get("port"):
            target += f":{result['target']['port']}"
        lines.append(
            f"| {result.get('check', '')} | {result.get('status', '')} | {target} "
            f"| {result.get('durationMs', '')} | {result.get('explanation', '')} |"
        )
    recommendations = data.get("summary", {}).get("recommendations", [])
    if recommendations:
        lines += ["", "## Recommendations", ""]
        lines += [f"- {rec}" for rec in recommendations]
    return "\n".join(lines) + "\n"


def render_html_from_dict(data: dict) -> str:
    host = html.escape(str(data.get("target", {}).get("host", "unknown")))
    rows = []
    for result in data.get("results", []):
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(result.get('check', '')))}</td>"
            f"<td>{html.escape(str(result.get('status', '')))}</td>"
            f"<td>{html.escape(str(result.get('durationMs', '')))}</td>"
            f"<td>{html.escape(str(result.get('explanation', '')))}</td>"
            "</tr>"
        )
    verdict, explanation = _summary_lines(data)
    return (
        "<!DOCTYPE html>\n<html><head><meta charset='utf-8'>"
        f"<title>NetScope report — {host}</title></head><body>"
        f"<h1>NetScope report — {host}</h1>"
        f"<p><strong>{html.escape(verdict)}</strong><br>{html.escape(explanation)}</p>"
        "<table border='1' cellspacing='0' cellpadding='4'>"
        "<tr><th>Check</th><th>Status</th><th>Duration (ms)</th><th>Explanation</th></tr>"
        + "".join(rows)
        + "</table></body></html>\n"
    )


def render_csv_from_dict(data: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["check", "status", "target", "port", "duration_ms", "explanation"])
    for result in data.get("results", []):
        target = result.get("target", {})
        writer.writerow(
            [
                result.get("check", ""),
                result.get("status", ""),
                target.get("host", ""),
                target.get("port", ""),
                result.get("durationMs", ""),
                result.get("explanation", ""),
            ]
        )
    return buffer.getvalue()


def render_text(source: HostReport | dict, fmt: str) -> str:
    """Render a text format (md/html/json/csv) from a report or schema dict."""
    if fmt == "pdf":
        raise ValueError("PDF is binary; use export_report")
    if isinstance(source, HostReport):
        if fmt == "md":
            return render_markdown(source)
        if fmt == "html":
            return render_html(source)
        if fmt == "json":
            return render_json(source)
        if fmt == "csv":
            return render_csv(source)
    else:
        if fmt == "md":
            return render_markdown_from_dict(source)
        if fmt == "html":
            return render_html_from_dict(source)
        if fmt == "json":
            return json.dumps(source, indent=2, ensure_ascii=False)
        if fmt == "csv":
            return render_csv_from_dict(source)
    raise ValueError(f"unknown format: {fmt}")


# -- PDF ---------------------------------------------------------------------


def _write_pdf(html_text: str, path: Path) -> None:
    from PySide6.QtCore import QMarginsF, QRectF, QSizeF
    from PySide6.QtGui import QPageSize, QPainter, QPdfWriter, QTextDocument

    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15))
    writer.setResolution(96)
    document = QTextDocument()
    document.setHtml(html_text)
    page_width = writer.width()
    page_height = writer.height()
    document.setPageSize(QSizeF(page_width, page_height))
    painter = QPainter(writer)
    try:
        offset = 0.0
        total = document.size().height()
        while offset < total:
            painter.save()
            painter.translate(0, -offset)
            document.drawContents(painter, QRectF(0, offset, page_width, page_height))
            painter.restore()
            offset += page_height
            if offset < total:
                writer.newPage()
    finally:
        painter.end()


# -- entry point ---------------------------------------------------------------


def export_report(source: HostReport | dict, fmt: str, path: Path) -> Path:
    """Export ``source`` in ``fmt`` to ``path``; returns the path written."""
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "pdf":
        html_text = (
            render_html(source) if isinstance(source, HostReport)
            else render_html_from_dict(source)
        )
        _write_pdf(html_text, path)
    else:
        path.write_text(render_text(source, fmt), encoding="utf-8")
    return path
