"""Shared building blocks for the desktop pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLayout,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ..theme import design_spacing
from ..workers import FunctionWorker


def iter_layouts(root: QWidget) -> list[QLayout]:
    """Every layout in ``root``'s widget tree, the root layout first."""
    layouts: list[QLayout] = []
    top = root.layout()
    if top is not None:
        layouts.append(top)
    for layout in root.findChildren(QLayout):
        if layout not in layouts:
            layouts.append(layout)
    return layouts


def apply_design_spacing(root: QWidget) -> None:
    """Bring every layout under ``root`` onto the design spacing scale.

    Qt's default layout margins (9 px) and spacing (6 px) are not on
    the design system's 4 px-base scale (finding F-01). The widget's
    own layout gets the page margin; nested layouts — group-box
    contents, control rows — get the content margin; every sibling
    gap gets the item spacing. All values come from
    ``theme.design_spacing``, the single source for layout rhythm.
    """
    spacing = design_spacing()
    top = root.layout()
    for layout in iter_layouts(root):
        margin = spacing["page_margin"] if layout is top else spacing["content_margin"]
        layout.setContentsMargins(margin, margin, margin, margin)
        if isinstance(layout, QFormLayout):
            layout.setHorizontalSpacing(spacing["item_spacing"])
            layout.setVerticalSpacing(spacing["item_spacing"])
        else:
            layout.setSpacing(spacing["item_spacing"])


def title_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "title")
    return label


def subtitle_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "subtitle")
    return label


def muted_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "muted")
    label.setWordWrap(True)
    return label


def mono_font() -> QFont:
    font = QFont("JetBrains Mono")
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(10)
    return font


def fmt_ms(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f} ms"


def fmt_value(value: object) -> str:
    return "—" if value is None else str(value)


def make_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def fill_table(table: QTableWidget, rows: list[list[object]]) -> None:
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(fmt_value(value))
            item.setFont(mono_font())
            table.setItem(r, c, item)
    table.resizeColumnsToContents()


class Page(QWidget):
    """Base page: holds the main-window reference and background workers."""

    def __init__(self, mw) -> None:
        super().__init__()
        self.mw = mw
        self._workers: list[FunctionWorker] = []
        self.status_label = muted_label("")

    @property
    def settings(self):
        return self.mw.settings

    @property
    def store(self):
        return self.mw.store

    def set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("status", "failed" if error else "")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        if text:
            self.mw.status(text)

    def run_worker(self, worker: FunctionWorker, on_done, on_failed=None) -> FunctionWorker:
        """Start a worker, keeping a reference until it finishes."""
        self._workers.append(worker)

        def cleanup() -> None:
            if worker in self._workers:
                self._workers.remove(worker)

        worker.done.connect(on_done)
        worker.failed.connect(on_failed if on_failed is not None else self._default_failed)
        worker.finished.connect(cleanup)
        worker.start()
        return worker

    def _default_failed(self, message: str) -> None:
        self.set_status(f"Error: {message}", error=True)

    def refresh(self) -> None:
        """Called by the main window when the page becomes visible."""

    def shutdown(self) -> None:
        """Called by the main window before closing."""
        for worker in list(self._workers):
            worker.wait(2000)


def align_center(item: QTableWidgetItem) -> QTableWidgetItem:
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item
