"""Speed Test, Route Analyzer and Interfaces pages."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from netscope_core.interfaces import list_interfaces
from netscope_core.routeprobe import probe_route
from netscope_core.speedtest import SpeedConfig, SpeedResult

from ..workers import FunctionWorker, SpeedWorker
from .common import Page, fill_table, fmt_ms, fmt_value, make_table, muted_label, title_label

_SIZE_OPTIONS = [
    ("1 MB", 1_000_000),
    ("5 MB", 5_000_000),
    ("10 MB", 10_000_000),
    ("25 MB", 25_000_000),
]


def _fmt_mbps(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f} Mbps"


def _fmt_bytes(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.2f} MB"
    if count >= 1_000:
        return f"{count / 1_000:.1f} KB"
    return f"{count} B"


# ---------------------------------------------------------------------------
# Speed Test
# ---------------------------------------------------------------------------


class SpeedPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("Speed Test"))

        form = QHBoxLayout()
        self.download_edit = QLineEdit(self.settings.speed_download_url)
        self.upload_edit = QLineEdit(self.settings.speed_upload_url)
        self.size_combo = QComboBox()
        for label, _size in _SIZE_OPTIONS:
            self.size_combo.addItem(label)
        self.size_combo.setCurrentIndex(2)
        form.addWidget(QLabel("Download URL"))
        form.addWidget(self.download_edit, 1)
        form.addWidget(QLabel("Upload URL"))
        form.addWidget(self.upload_edit, 1)
        form.addWidget(QLabel("Test size"))
        form.addWidget(self.size_combo)
        layout.addLayout(form)

        layout.addWidget(muted_label(
            "A speed test transfers real data: up to the selected size for the "
            "download and half of it for the upload. Do not run it on a metered "
            "connection unless you accept that usage."
        ))

        controls = QHBoxLayout()
        self.run_button = QPushButton("Run speed test")
        self.run_button.setProperty("primary", True)
        self.run_button.clicked.connect(self.run_test)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_test)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        controls.addWidget(self.run_button)
        controls.addWidget(self.cancel_button)
        controls.addWidget(self.progress, 1)
        layout.addLayout(controls)

        self.result_label = QLabel("No test run yet.")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self._speed_worker: SpeedWorker | None = None

    def run_test(self) -> None:
        download_url = self.download_edit.text().strip()
        upload_url = self.upload_edit.text().strip()
        if not download_url and not upload_url:
            self.set_status("Enter at least one endpoint URL.", error=True)
            return
        size = _SIZE_OPTIONS[self.size_combo.currentIndex()][1]
        config = SpeedConfig(
            download_urls=[download_url] if download_url else [],
            upload_url=upload_url or None,
            max_download_bytes=size,
            max_upload_bytes=size // 2,
            max_duration_s=30.0,
        )
        self._speed_worker = SpeedWorker(config)
        self._speed_worker.done.connect(self._on_done)
        self._speed_worker.failed.connect(
            lambda message: self._finish(f"Error: {message}", error=True)
        )
        self._speed_worker.start()
        self.progress.setRange(0, 0)  # indeterminate while measuring
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.set_status("Speed test running…")

    def cancel_test(self) -> None:
        if self._speed_worker is not None:
            self._speed_worker.cancel()
            self.set_status("Cancelling…")

    def _on_done(self, result: SpeedResult) -> None:
        lines = [
            f"Download: {_fmt_mbps(result.download_mbps)} ({_fmt_bytes(result.bytes_downloaded)})",
            f"Upload: {_fmt_mbps(result.upload_mbps)} ({_fmt_bytes(result.bytes_uploaded)})",
            f"Idle latency (avg): {fmt_ms(result.idle_latency.avg if result.idle_latency else None)}",
            f"Latency under load (avg): {fmt_ms(result.loaded_latency.avg if result.loaded_latency else None)}",
        ]
        if result.download_endpoint:
            lines.append(f"Download endpoint: {result.download_endpoint}")
        if result.upload_endpoint:
            lines.append(f"Upload endpoint: {result.upload_endpoint}")
        if result.errors:
            lines.append("Errors: " + "; ".join(result.errors))
        self.result_label.setText("\n".join(lines))
        self._finish("Speed test cancelled." if result.cancelled else "Speed test complete.")

    def _finish(self, message: str, error: bool = False) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._speed_worker = None
        self.set_status(message, error=error)

    def shutdown(self) -> None:
        if self._speed_worker is not None:
            self._speed_worker.cancel()
            self._speed_worker.wait(3000)
            self._speed_worker = None
        super().shutdown()


# ---------------------------------------------------------------------------
# Route Analyzer
# ---------------------------------------------------------------------------


class RoutePage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("Route Analyzer"))

        controls = QHBoxLayout()
        self.host_edit = QLineEdit("example.com")
        self.hops_spin = QSpinBox()
        self.hops_spin.setRange(1, 64)
        self.hops_spin.setValue(30)
        self.run_button = QPushButton("Trace route")
        self.run_button.setProperty("primary", True)
        self.run_button.clicked.connect(self.run_trace)
        controls.addWidget(QLabel("Host"))
        controls.addWidget(self.host_edit, 1)
        controls.addWidget(QLabel("Max hops"))
        controls.addWidget(self.hops_spin)
        controls.addWidget(self.run_button)
        layout.addLayout(controls)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.hops_table = make_table(["Hop", "Address", "Avg RTT", "Probes answered"])
        layout.addWidget(self.hops_table, 1)
        layout.addWidget(self.status_label)

    def run_trace(self) -> None:
        host = self.host_edit.text().strip()
        if not host:
            self.set_status("Enter a host first.", error=True)
            return
        max_hops = self.hops_spin.value()
        self.run_button.setEnabled(False)
        self.set_status(f"Tracing route to {host}…")

        def work():
            return probe_route(host, max_hops=max_hops)

        def on_done(result) -> None:
            self.run_button.setEnabled(True)
            method_label = (
                "ICMP echo probes"
                if result.method == "icmp"
                else "TCP connect probes (ICMP replies need raw-socket permission)"
            )
            self.summary_label.setText(
                f"Method: {method_label} · Destination: {fmt_value(result.destination_ip)}"
                f" · Reached: {'yes' if result.reached else 'no'}"
                f" · Stops: {result.stop_point}\n{result.note}"
                + (f"\nError: {result.error}" if result.error else "")
            )
            fill_table(
                self.hops_table,
                [
                    [
                        hop.ttl,
                        hop.ip or "—",
                        fmt_ms(hop.avg_rtt_ms),
                        f"{len(hop.rtt_ms)}/{hop.probes_sent}",
                    ]
                    for hop in result.hops
                ],
            )
            self.set_status(f"Route to {host} traced ({result.stop_point}).")

        def on_failed(message: str) -> None:
            self.run_button.setEnabled(True)
            self.set_status(f"Error: {message}", error=True)

        self.run_worker(FunctionWorker(work), on_done, on_failed)


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


class InterfacesPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("Network Interfaces"))

        controls = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("primary", True)
        self.refresh_button.clicked.connect(self.refresh_inventory)
        controls.addWidget(self.refresh_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.interfaces_table = make_table(["Interface", "Index", "Loopback"])
        layout.addWidget(self.interfaces_table, 1)
        layout.addWidget(muted_label("Notes and platform limitations"))
        self.notes_text = QPlainTextEdit()
        self.notes_text.setReadOnly(True)
        layout.addWidget(self.notes_text)
        layout.addWidget(self.status_label)

        self.refresh_inventory()

    def refresh_inventory(self) -> None:
        self.refresh_button.setEnabled(False)

        def on_done(inventory) -> None:
            self.refresh_button.setEnabled(True)
            self.summary_label.setText(
                f"Hostname: {inventory.hostname} · Local addresses: "
                f"{', '.join(inventory.local_addresses) or '—'} · Outbound IPv4: "
                f"{fmt_value(inventory.outbound_ipv4)} · Default gateway: "
                f"{fmt_value(inventory.default_gateway)}"
            )
            fill_table(
                self.interfaces_table,
                [
                    [i.name, i.index, "yes" if i.is_loopback else "no"]
                    for i in inventory.interfaces
                ],
            )
            self.notes_text.setPlainText("\n".join(f"- {n}" for n in inventory.notes))
            self.set_status("Interface inventory updated.")

        def on_failed(message: str) -> None:
            self.refresh_button.setEnabled(True)
            self.set_status(f"Error: {message}", error=True)

        self.run_worker(FunctionWorker(list_interfaces), on_done, on_failed)
