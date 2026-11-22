"""Overview, Live Monitor, Diagnostics and DNS Analyzer pages."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from netscope_core.dnsprobe import lookup
from netscope_core.engine import run_host_check
from netscope_core.interfaces import list_interfaces
from netscope_core.models import HostReport

from .. import exports
from ..chart import LatencyChart
from ..sampler import Connector, LatencySampler
from ..theme import theme_colors
from ..workers import FunctionWorker, MonitorWorker
from .common import Page, fill_table, fmt_ms, fmt_value, make_table, muted_label, subtitle_label, title_label

RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR", "SRV", "CAA"]

_VERDICT_STATUS = {"OK": "ok", "SLOW_UNSTABLE": "degraded", "UNKNOWN": "degraded"}


def verdict_status(code: str) -> str:
    return _VERDICT_STATUS.get(code, "failed")


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class OverviewPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("Overview"))

        inventory_box = QGroupBox("This machine")
        form = QFormLayout(inventory_box)
        self.hostname_label = QLabel("—")
        self.addresses_label = QLabel("—")
        self.addresses_label.setWordWrap(True)
        self.outbound_label = QLabel("—")
        self.gateway_label = QLabel("—")
        form.addRow("Hostname", self.hostname_label)
        form.addRow("Local addresses", self.addresses_label)
        form.addRow("Outbound IPv4", self.outbound_label)
        form.addRow("Default gateway", self.gateway_label)
        layout.addWidget(inventory_box)

        self.interfaces_table = make_table(["Interface", "Index", "Loopback"])
        layout.addWidget(self.interfaces_table)

        quick_box = QGroupBox("Quick diagnose")
        quick_layout = QHBoxLayout(quick_box)
        self.host_edit = QLineEdit("example.com")
        self.host_edit.setPlaceholderText("Host or domain, e.g. example.com")
        self.run_button = QPushButton("Run diagnostics")
        self.run_button.setProperty("primary", True)
        self.run_button.clicked.connect(self.run_quick)
        quick_layout.addWidget(self.host_edit, 1)
        quick_layout.addWidget(self.run_button)
        layout.addWidget(quick_box)

        self.verdict_label = QLabel("")
        self.verdict_label.setWordWrap(True)
        self.metrics_label = QLabel("")
        self.metrics_label.setWordWrap(True)
        layout.addWidget(self.verdict_label)
        layout.addWidget(self.metrics_label)

        layout.addWidget(subtitle_label("Recent diagnostics"))
        self.recent_table = make_table(["Time", "Host", "Verdict"])
        layout.addWidget(self.recent_table)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.refresh_inventory()
        self.refresh_recent()

    def refresh(self) -> None:
        self.refresh_recent()

    def refresh_inventory(self) -> None:
        def on_done(inventory) -> None:
            self.hostname_label.setText(inventory.hostname)
            self.addresses_label.setText(", ".join(inventory.local_addresses) or "—")
            self.outbound_label.setText(fmt_value(inventory.outbound_ipv4))
            self.gateway_label.setText(fmt_value(inventory.default_gateway))
            fill_table(
                self.interfaces_table,
                [
                    [i.name, i.index, "yes" if i.is_loopback else "no"]
                    for i in inventory.interfaces
                ],
            )

        self.run_worker(FunctionWorker(list_interfaces), on_done)

    def refresh_recent(self) -> None:
        rows = self.store.list_reports(limit=5)
        fill_table(
            self.recent_table,
            [[r.created_at, r.host, r.verdict] for r in rows],
        )

    def run_quick(self) -> None:
        host = self.host_edit.text().strip()
        if not host:
            self.set_status("Enter a host first.", error=True)
            return
        self.run_button.setEnabled(False)
        self.set_status(f"Diagnosing {host}…")

        def work() -> HostReport:
            return run_host_check(
                host, resolvers=self.settings.resolvers, app_surface="desktop"
            )

        def on_done(report: HostReport) -> None:
            self.run_button.setEnabled(True)
            self.store.add_report(report)
            self.mw.session_reports.append(report)
            self.verdict_label.setText(
                f"Verdict: {report.verdict.code} — {report.verdict.explanation}"
            )
            self.verdict_label.setProperty("status", verdict_status(report.verdict.code))
            self.verdict_label.style().unpolish(self.verdict_label)
            self.verdict_label.style().polish(self.verdict_label)
            tcp443 = report.tcp.get(443)
            https = report.http.get("https")
            self.metrics_label.setText(
                "DNS (system) "
                + fmt_ms(report.dns.system_latency_ms)
                + " · TCP 443 avg "
                + fmt_ms(tcp443.avg_latency_ms if tcp443 else None)
                + " · HTTPS "
                + (str(https.status) if https and https.status else "failed")
            )
            self.set_status(f"Diagnosed {host}: {report.verdict.code}")
            self.refresh_recent()
            self.mw.refresh_history_pages()

        def on_failed(message: str) -> None:
            self.run_button.setEnabled(True)
            self.set_status(f"Error: {message}", error=True)

        self.run_worker(FunctionWorker(work), on_done, on_failed)


# ---------------------------------------------------------------------------
# Live Monitor
# ---------------------------------------------------------------------------


class MonitorPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("Live Monitor"))

        controls = QHBoxLayout()
        self.host_edit = QLineEdit("example.com")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(443)
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.5, 60.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setValue(2.0)
        self.interval_spin.setSuffix(" s")
        self.start_button = QPushButton("Start")
        self.start_button.setProperty("primary", True)
        self.start_button.clicked.connect(self.start_monitor)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_monitor)
        controls.addWidget(QLabel("Host"))
        controls.addWidget(self.host_edit, 1)
        controls.addWidget(QLabel("Port"))
        controls.addWidget(self.port_spin)
        controls.addWidget(QLabel("Interval"))
        controls.addWidget(self.interval_spin)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)

        self.chart = LatencyChart(theme_colors(self.settings.theme))
        layout.addWidget(self.chart)
        self.stats_label = QLabel("No samples yet.")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)
        layout.addWidget(muted_label(
            "Latency is TCP connect time to the chosen port. Failed connects "
            "break the line and count as loss."
        ))
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.sampler: LatencySampler | None = None
        self._monitor_worker: MonitorWorker | None = None

    def on_theme_changed(self, theme: str) -> None:
        self.chart.set_colors(theme_colors(theme))

    def sample_once_with_connector(self, connector: Connector) -> dict:
        """Take one sample through an injected connector (used by tests)."""
        if self.sampler is None:
            self.sampler = LatencySampler(
                self.host_edit.text().strip() or "example.com",
                self.port_spin.value(),
                connector=connector,
            )
        self.sampler.sample_once()
        stats = self.sampler.stats()
        self._update_stats(stats)
        return stats

    def _update_stats(self, stats: dict) -> None:
        if self.sampler is not None:
            self.chart.set_series(self.sampler.series)
        self.stats_label.setText(
            f"last {fmt_ms(stats['last'])} · avg {fmt_ms(stats['avg'])} · "
            f"min {fmt_ms(stats['min'])} · max {fmt_ms(stats['max'])} · "
            f"p95 {fmt_ms(stats['p95'])} · jitter {fmt_ms(stats['jitter_avg'])} · "
            f"loss {stats['loss_percent']:.1f}% ({stats['received']}/{stats['sent']})"
        )

    def start_monitor(self) -> None:
        host = self.host_edit.text().strip()
        if not host:
            self.set_status("Enter a host first.", error=True)
            return
        self.sampler = LatencySampler(host, self.port_spin.value())
        self.chart.set_series([])
        self._monitor_worker = MonitorWorker(self.sampler, self.interval_spin.value())
        self._monitor_worker.tick.connect(self._update_stats)
        self._monitor_worker.failed.connect(
            lambda message: self.set_status(f"Error: {message}", error=True)
        )
        self._monitor_worker.finished.connect(self._monitor_finished)
        self._monitor_worker.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.host_edit.setEnabled(False)
        self.set_status(f"Monitoring {host}:{self.port_spin.value()}…")

    def _monitor_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.host_edit.setEnabled(True)

    def stop_monitor(self) -> None:
        if self._monitor_worker is not None:
            self._monitor_worker.stop()
            self._monitor_worker.wait(3000)
            self._monitor_worker = None
        self._monitor_finished()
        self.set_status("Monitor stopped.")

    def shutdown(self) -> None:
        if self._monitor_worker is not None:
            self._monitor_worker.stop()
            self._monitor_worker.wait(3000)
            self._monitor_worker = None
        super().shutdown()


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


class DiagnosticsPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("Diagnostics"))

        controls = QHBoxLayout()
        self.host_edit = QLineEdit("example.com")
        self.resolvers_edit = QLineEdit(", ".join(self.settings.resolvers))
        self.resolvers_edit.setPlaceholderText("Resolvers, comma separated")
        self.run_button = QPushButton("Run full check")
        self.run_button.setProperty("primary", True)
        self.run_button.clicked.connect(self.run_check)
        controls.addWidget(QLabel("Host"))
        controls.addWidget(self.host_edit, 1)
        controls.addWidget(QLabel("Resolvers"))
        controls.addWidget(self.resolvers_edit, 1)
        controls.addWidget(self.run_button)
        layout.addLayout(controls)

        self.verdict_label = QLabel("")
        self.verdict_label.setWordWrap(True)
        layout.addWidget(self.verdict_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)

        dns_box = QGroupBox("DNS")
        dns_layout = QVBoxLayout(dns_box)
        self.dns_summary = QLabel("—")
        self.dns_summary.setWordWrap(True)
        self.dns_table = make_table(["Resolver", "Status", "Addresses", "Latency"])
        dns_layout.addWidget(self.dns_summary)
        dns_layout.addWidget(self.dns_table)
        self.content_layout.addWidget(dns_box)

        tcp_box = QGroupBox("TCP")
        tcp_layout = QVBoxLayout(tcp_box)
        self.tcp_table = make_table(["Port", "Connected", "Avg", "Loss", "Main error"])
        tcp_layout.addWidget(self.tcp_table)
        self.content_layout.addWidget(tcp_box)

        tls_box = QGroupBox("TLS")
        tls_layout = QVBoxLayout(tls_box)
        self.tls_summary = QLabel("—")
        self.tls_summary.setWordWrap(True)
        tls_layout.addWidget(self.tls_summary)
        self.content_layout.addWidget(tls_box)

        http_box = QGroupBox("HTTP")
        http_layout = QVBoxLayout(http_box)
        self.http_table = make_table(
            ["Scheme", "Status", "Redirects", "Bytes", "Block markers", "Error"]
        )
        http_layout.addWidget(self.http_table)
        self.content_layout.addWidget(http_box)

        findings_box = QGroupBox("Troubleshooting")
        findings_layout = QVBoxLayout(findings_box)
        findings_layout.addWidget(subtitle_label("Measured facts"))
        self.facts_text = QPlainTextEdit()
        self.facts_text.setReadOnly(True)
        findings_layout.addWidget(self.facts_text)
        findings_layout.addWidget(subtitle_label("Possible causes"))
        self.causes_text = QPlainTextEdit()
        self.causes_text.setReadOnly(True)
        findings_layout.addWidget(self.causes_text)
        findings_layout.addWidget(subtitle_label("Recommendations"))
        self.recommendations_text = QPlainTextEdit()
        self.recommendations_text.setReadOnly(True)
        findings_layout.addWidget(self.recommendations_text)
        self.content_layout.addWidget(findings_box)
        self.content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        export_row = QHBoxLayout()
        export_row.addWidget(QLabel("Export this result:"))
        for fmt in exports.FORMATS:
            button = QPushButton(fmt.upper())
            button.clicked.connect(lambda _checked=False, f=fmt: self.export(f))
            export_row.addWidget(button)
        export_row.addStretch(1)
        layout.addLayout(export_row)
        layout.addWidget(self.status_label)

        self.current_report: HostReport | None = None

    def run_check(self) -> None:
        host = self.host_edit.text().strip()
        if not host:
            self.set_status("Enter a host first.", error=True)
            return
        resolvers = [r.strip() for r in self.resolvers_edit.text().split(",") if r.strip()]
        self.run_button.setEnabled(False)
        self.set_status(f"Running full check for {host}…")

        def work() -> HostReport:
            return run_host_check(
                host,
                resolvers=resolvers or None,
                app_surface="desktop",
            )

        def on_done(report: HostReport) -> None:
            self.run_button.setEnabled(True)
            self.store.add_report(report)
            self.mw.session_reports.append(report)
            self.show_report(report)
            self.set_status(f"Checked {host}: {report.verdict.code}")
            self.mw.refresh_history_pages()

        def on_failed(message: str) -> None:
            self.run_button.setEnabled(True)
            self.set_status(f"Error: {message}", error=True)

        self.run_worker(FunctionWorker(work), on_done, on_failed)

    def show_report(self, report: HostReport) -> None:
        """Render a completed report into the layered sections."""
        self.current_report = report
        self.verdict_label.setText(
            f"Verdict: {report.verdict.code} (confidence: {report.verdict.confidence})"
            f" — {report.verdict.explanation}"
        )
        self.verdict_label.setProperty("status", verdict_status(report.verdict.code))
        self.verdict_label.style().unpolish(self.verdict_label)
        self.verdict_label.style().polish(self.verdict_label)

        dns = report.dns
        flags = []
        if dns.suspect_poisoning:
            flags.append("Resolver answers disagree with the system resolver (possible poisoning).")
        if dns.partial_nxdomain:
            flags.append("Some resolvers return NXDOMAIN while others answer.")
        self.dns_summary.setText(
            "System: "
            + (", ".join(dns.system_addresses) or "no addresses")
            + f" ({fmt_ms(dns.system_latency_ms)})"
            + ((" · " + " ".join(flags)) if flags else "")
            + (f" · Error: {dns.system_error}" if dns.system_error else "")
        )
        fill_table(
            self.dns_table,
            [
                [r.resolver, r.status, ", ".join(r.addresses), fmt_ms(r.latency_ms)]
                for r in dns.resolvers
            ],
        )
        fill_table(
            self.tcp_table,
            [
                [
                    port,
                    f"{result.successes}/{len(result.attempts)}",
                    fmt_ms(result.avg_latency_ms),
                    f"{result.loss_pct:.0f}%",
                    result.dominant_error or "—",
                ]
                for port, result in sorted(report.tcp.items())
            ],
        )
        tls = report.tls
        if tls is None:
            self.tls_summary.setText("Not attempted (no address resolved).")
        elif tls.ok:
            self.tls_summary.setText(
                f"Handshake OK · {tls.protocol or 'TLS'} · connect {fmt_ms(tls.connect_ms)}"
                f" · handshake {fmt_ms(tls.handshake_ms)}\n"
                f"Certificate subject: {tls.cert_subject or '—'}\n"
                f"Issuer: {tls.cert_issuer or '—'}\n"
                f"Expires: {tls.cert_not_after_iso or tls.cert_not_after or '—'}"
                f" ({tls.cert_days_remaining} days remaining)"
            )
        else:
            self.tls_summary.setText(
                f"Handshake failed in the {tls.failed_phase or 'unknown'} phase"
                f" ({tls.error_kind or 'error'}): {tls.error or '—'}"
            )
        fill_table(
            self.http_table,
            [
                [
                    scheme,
                    result.status if result.status is not None else "failed",
                    result.redirects,
                    result.size_bytes,
                    ", ".join(result.markers) or "—",
                    result.error or "—",
                ]
                for scheme, result in report.http.items()
            ],
        )
        facts: list[str] = []
        causes: list[str] = []
        recommendations: list[str] = []
        for finding in report.findings:
            facts.append(f"- [{finding.topic}] {finding.fact}")
            for cause in finding.possible_causes:
                if cause not in causes:
                    causes.append(cause)
            for rec in finding.recommendations:
                if rec not in recommendations:
                    recommendations.append(rec)
        self.facts_text.setPlainText("\n".join(facts) or "No findings.")
        self.causes_text.setPlainText(
            "\n".join(f"- {c}" for c in causes) or "None identified."
        )
        self.recommendations_text.setPlainText(
            "\n".join(f"- {r}" for r in recommendations) or "None."
        )

    def export(self, fmt: str) -> None:
        if self.current_report is None:
            self.set_status("Run a check first.", error=True)
            return
        start = str(Path.home() / exports.default_filename(self.current_report.host, fmt))
        path, _selected = QFileDialog.getSaveFileName(self, "Export report", start)
        if not path:
            return
        try:
            exports.export_report(self.current_report, fmt, Path(path))
        except Exception as exc:
            self.set_status(f"Export failed: {exc}", error=True)
            return
        self.set_status(f"Exported {fmt.upper()} to {path}")


# ---------------------------------------------------------------------------
# DNS Analyzer
# ---------------------------------------------------------------------------


class DNSPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("DNS Analyzer"))

        controls = QHBoxLayout()
        self.name_edit = QLineEdit("example.com")
        self.qtype_combo = QComboBox()
        self.qtype_combo.addItems(RECORD_TYPES)
        self.run_button = QPushButton("Look up")
        self.run_button.setProperty("primary", True)
        self.run_button.clicked.connect(self.run_lookup)
        controls.addWidget(QLabel("Name"))
        controls.addWidget(self.name_edit, 1)
        controls.addWidget(QLabel("Record type"))
        controls.addWidget(self.qtype_combo)
        controls.addWidget(self.run_button)
        layout.addLayout(controls)
        layout.addWidget(muted_label(
            "Each configured resolver is queried directly over UDP/53; the "
            "system resolver cannot answer arbitrary record types."
        ))
        self.results_table = make_table(["Resolver", "Status", "Latency", "Records"])
        layout.addWidget(self.results_table, 1)
        layout.addWidget(self.status_label)

    def run_lookup(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.set_status("Enter a name first.", error=True)
            return
        qtype = self.qtype_combo.currentText()
        resolvers = list(self.settings.resolvers)
        self.run_button.setEnabled(False)
        self.set_status(f"Querying {qtype} for {name}…")

        def work():
            return [lookup(name, qtype, resolver=r) for r in resolvers]

        def on_done(results) -> None:
            self.run_button.setEnabled(True)
            fill_table(
                self.results_table,
                [
                    [
                        r.resolver,
                        r.status + (f" ({r.error})" if r.error else ""),
                        fmt_ms(r.latency_ms),
                        "\n".join(
                            f"{rec.type} {rec.value} (TTL {rec.ttl})" for rec in r.records
                        )
                        or "—",
                    ]
                    for r in results
                ],
            )
            self.set_status(f"{qtype} lookup for {name} complete.")

        def on_failed(message: str) -> None:
            self.run_button.setEnabled(True)
            self.set_status(f"Error: {message}", error=True)

        self.run_worker(FunctionWorker(work), on_done, on_failed)
