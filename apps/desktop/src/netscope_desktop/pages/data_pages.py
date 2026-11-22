"""History, Reports, Settings and About pages."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QFileDialog,
)

import netscope_core

from .. import __version__, exports, paths
from ..settings import Settings
from .common import (
    Page,
    apply_design_spacing,
    fill_table,
    fmt_ms,
    make_table,
    muted_label,
    title_label,
)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class HistoryPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("History"))

        controls = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by host")
        filter_button = QPushButton("Filter")
        filter_button.clicked.connect(self.refresh)
        controls.addWidget(self.filter_edit, 1)
        controls.addWidget(filter_button)
        layout.addLayout(controls)

        self.table = make_table(["Time", "Host", "Verdict", "Confidence", "TCP 443 avg"])
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        open_button = QPushButton("Open selected")
        open_button.clicked.connect(self.open_selected)
        delete_button = QPushButton("Delete selected")
        delete_button.clicked.connect(self.delete_selected)
        clear_button = QPushButton("Clear all")
        clear_button.clicked.connect(self.clear_all)
        self.format_combo = QComboBox()
        self.format_combo.addItems([f.upper() for f in exports.FORMATS])
        export_button = QPushButton("Export selected")
        export_button.clicked.connect(self.export_selected)
        buttons.addWidget(open_button)
        buttons.addWidget(delete_button)
        buttons.addWidget(clear_button)
        buttons.addStretch(1)
        buttons.addWidget(QLabel("Format"))
        buttons.addWidget(self.format_combo)
        buttons.addWidget(export_button)
        layout.addLayout(buttons)
        layout.addWidget(muted_label(
            f"Stored locally in {paths.history_db_path()} — nothing leaves this machine."
        ))
        layout.addWidget(self.status_label)
        self.refresh()

    def refresh(self) -> None:
        host_filter = self.filter_edit.text().strip() or None
        rows = self.store.list_reports(host=host_filter)
        fill_table(
            self.table,
            [
                [r.created_at, r.host, r.verdict, r.confidence, fmt_ms(r.tcp443_avg_ms)]
                for r in rows
            ],
        )
        for index, row in enumerate(rows):
            item = self.table.item(index, 0)
            if item is not None:
                item.setData(Qt.ItemDataRole.UserRole, row.id)

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def open_selected(self) -> None:
        row_id = self._selected_id()
        if row_id is None:
            self.set_status("Select a stored run first.", error=True)
            return
        markdown = self.store.get_report_markdown(row_id)
        if markdown is None:
            self.set_status("That stored run no longer exists.", error=True)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Stored report (read-only)")
        dialog.resize(720, 560)
        dialog_layout = QVBoxLayout(dialog)
        apply_design_spacing(dialog)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(markdown)
        dialog_layout.addWidget(text)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        dialog_layout.addWidget(close_button)
        dialog.exec()

    def delete_selected(self) -> None:
        row_id = self._selected_id()
        if row_id is None:
            self.set_status("Select a stored run first.", error=True)
            return
        self.store.delete(row_id)
        self.refresh()
        self.mw.refresh_history_pages(except_page=self)
        self.set_status("Stored run deleted.")

    def clear_all(self) -> None:
        answer = QMessageBox.question(
            self, "Clear history", "Delete all stored diagnostic runs?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = self.store.clear()
        self.refresh()
        self.mw.refresh_history_pages(except_page=self)
        self.set_status(f"Cleared {removed} stored run(s).")

    def export_selected(self) -> None:
        row_id = self._selected_id()
        if row_id is None:
            self.set_status("Select a stored run first.", error=True)
            return
        data = self.store.get_report_json(row_id)
        if data is None:
            self.set_status("That stored run no longer exists.", error=True)
            return
        fmt = exports.FORMATS[self.format_combo.currentIndex()]
        host = data.get("target", {}).get("host", "report")
        start = str(Path.home() / exports.default_filename(host, fmt))
        path, _selected = QFileDialog.getSaveFileName(self, "Export report", start)
        if not path:
            return
        try:
            exports.export_report(data, fmt, Path(path))
        except Exception as exc:
            self.set_status(f"Export failed: {exc}", error=True)
            return
        self.set_status(f"Exported {fmt.upper()} to {path}")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class ReportsPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("Reports"))

        self.source_list = QListWidget()
        self.source_list.currentRowChanged.connect(self._show_preview)
        layout.addWidget(self.source_list, 1)
        layout.addWidget(muted_label("Preview (JSON)"))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 1)

        controls = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems([f.upper() for f in exports.FORMATS])
        export_button = QPushButton("Export selected report")
        export_button.setProperty("primary", True)
        export_button.clicked.connect(self.export_selected)
        controls.addWidget(QLabel("Format"))
        controls.addWidget(self.format_combo)
        controls.addWidget(export_button)
        controls.addStretch(1)
        layout.addLayout(controls)
        layout.addWidget(self.status_label)

        self._sources: list[tuple[str, object]] = []  # ("object", HostReport) | ("stored", row id)
        self.refresh()

    def refresh(self) -> None:
        self._sources = []
        self.source_list.clear()
        for report in reversed(self.mw.session_reports):
            self._sources.append(("object", report))
            self.source_list.addItem(
                f"Session — {report.host} — {report.generated_at} — {report.verdict.code}"
            )
        for row in self.store.list_reports(limit=50):
            self._sources.append(("stored", row.id))
            self.source_list.addItem(
                f"Stored — {row.host} — {row.created_at} — {row.verdict}"
            )
        if self._sources:
            self.source_list.setCurrentRow(0)

    def _selected_source(self):
        index = self.source_list.currentRow()
        if index < 0 or index >= len(self._sources):
            return None
        kind, value = self._sources[index]
        if kind == "object":
            return value
        return self.store.get_report_json(int(value))

    def _show_preview(self, _index: int) -> None:
        source = self._selected_source()
        if source is None:
            self.preview.setPlainText("")
            return
        self.preview.setPlainText(exports.render_text(source, "json"))

    def export_selected(self) -> None:
        source = self._selected_source()
        if source is None:
            self.set_status("Select a report first.", error=True)
            return
        fmt = exports.FORMATS[self.format_combo.currentIndex()]
        host = (
            source.host if not isinstance(source, dict)
            else source.get("target", {}).get("host", "report")
        )
        start = str(Path.home() / exports.default_filename(host, fmt))
        path, _selected = QFileDialog.getSaveFileName(self, "Export report", start)
        if not path:
            return
        try:
            exports.export_report(source, fmt, Path(path))
        except Exception as exc:
            self.set_status(f"Export failed: {exc}", error=True)
            return
        self.set_status(f"Exported {fmt.upper()} to {path}")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingsPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)
        layout.addWidget(title_label("Settings"))

        layout.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.settings.theme)
        self.theme_combo.currentTextChanged.connect(self._theme_changed)
        layout.addWidget(self.theme_combo)

        layout.addWidget(QLabel("Default resolvers (comma separated)"))
        self.resolvers_edit = QLineEdit(", ".join(self.settings.resolvers))
        layout.addWidget(self.resolvers_edit)

        layout.addWidget(QLabel("Speed test download URL"))
        self.download_edit = QLineEdit(self.settings.speed_download_url)
        layout.addWidget(self.download_edit)
        layout.addWidget(QLabel("Speed test upload URL"))
        self.upload_edit = QLineEdit(self.settings.speed_upload_url)
        layout.addWidget(self.upload_edit)

        retention_row = QHBoxLayout()
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 3650)
        self.retention_spin.setValue(self.settings.history_retention_days)
        self.max_rows_spin = QSpinBox()
        self.max_rows_spin.setRange(10, 100000)
        self.max_rows_spin.setValue(self.settings.history_max_rows)
        retention_row.addWidget(QLabel("History retention (days)"))
        retention_row.addWidget(self.retention_spin)
        retention_row.addWidget(QLabel("Max stored runs"))
        retention_row.addWidget(self.max_rows_spin)
        retention_row.addStretch(1)
        layout.addLayout(retention_row)

        save_button = QPushButton("Save settings")
        save_button.setProperty("primary", True)
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)
        layout.addWidget(muted_label(
            f"Settings file: {paths.settings_path()} · History database: "
            f"{paths.history_db_path()}"
        ))
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def _theme_changed(self, theme: str) -> None:
        self.settings.theme = theme
        self.mw.apply_theme(theme)

    def save_settings(self) -> None:
        settings: Settings = self.settings
        settings.theme = self.theme_combo.currentText()
        settings.resolvers = [
            r.strip() for r in self.resolvers_edit.text().split(",") if r.strip()
        ] or settings.resolvers
        settings.speed_download_url = self.download_edit.text().strip()
        settings.speed_upload_url = self.upload_edit.text().strip()
        settings.history_retention_days = self.retention_spin.value()
        settings.history_max_rows = self.max_rows_spin.value()
        try:
            settings.save()
        except OSError as exc:
            self.set_status(f"Could not save settings: {exc}", error=True)
            return
        removed = self.store.prune(
            settings.history_retention_days, settings.history_max_rows
        )
        self.mw.apply_theme(settings.theme)
        self.mw.refresh_history_pages()
        message = "Settings saved."
        if removed:
            message += f" Retention removed {removed} stored run(s)."
        self.set_status(message)


# ---------------------------------------------------------------------------
# About
# ---------------------------------------------------------------------------


class AboutPage(Page):
    def __init__(self, mw) -> None:
        super().__init__(mw)
        layout = QVBoxLayout(self)

        icon_label = QLabel()
        icon_path = paths.app_icon_path()
        if icon_path is not None:
            try:
                from PySide6.QtCore import QSize
                from PySide6.QtGui import QImage, QPainter, QPixmap
                from PySide6.QtSvg import QSvgRenderer

                renderer = QSvgRenderer(str(icon_path))
                image = QImage(QSize(72, 72), QImage.Format.Format_ARGB32)
                image.fill(0)
                painter = QPainter(image)
                renderer.render(painter)
                painter.end()
                icon_label.setPixmap(QPixmap.fromImage(image))
            except Exception:
                icon_label.setText("")
        layout.addWidget(icon_label)

        name_label = QLabel("NetScope")
        name_label.setProperty("role", "title")
        layout.addWidget(name_label)
        layout.addWidget(QLabel("Understand Your Network. Take Control."))
        layout.addWidget(QLabel(
            f"Desktop {__version__} · Core {netscope_core.__version__} · "
            f"Python {sys.version.split()[0]}"
        ))
        layout.addWidget(QLabel(f"Platform: {platform.platform()}"))
        layout.addWidget(QLabel("License: MIT"))
        layout.addWidget(muted_label(
            "NetScope sends no telemetry. The only network traffic it creates "
            "is the diagnostics you run, to the targets you specify."
        ))
        layout.addWidget(muted_label(
            f"Data: {paths.data_dir()} · Configuration: {paths.config_dir()}"
        ))
        layout.addStretch(1)
