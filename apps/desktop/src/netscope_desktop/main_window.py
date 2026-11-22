"""Main window: text-labelled navigation on the left, one page per area.

The layout follows the design system: a quiet navigation list, a
content area, no decorative dashboard elements. Pages are constructed
once and kept; data pages refresh when they become visible or when a
new diagnostic run completes.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from .history import HistoryStore
from .pages.common import apply_design_spacing
from .pages.core_pages import DNSPage, DiagnosticsPage, MonitorPage, OverviewPage
from .pages.data_pages import AboutPage, HistoryPage, ReportsPage, SettingsPage
from .pages.tool_pages import InterfacesPage, RoutePage, SpeedPage
from .settings import Settings
from .theme import build_stylesheet

PAGE_DEFS = [
    ("Overview", OverviewPage),
    ("Live Monitor", MonitorPage),
    ("Diagnostics", DiagnosticsPage),
    ("DNS Analyzer", DNSPage),
    ("Speed Test", SpeedPage),
    ("Route Analyzer", RoutePage),
    ("Interfaces", InterfacesPage),
    ("History", HistoryPage),
    ("Reports", ReportsPage),
    ("Settings", SettingsPage),
    ("About", AboutPage),
]


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, store: HistoryStore) -> None:
        super().__init__()
        self.settings = settings
        self.store = store
        self.session_reports: list = []
        self.setWindowTitle("NetScope")
        self.resize(1180, 760)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(196)
        self.stack = QStackedWidget()
        self.pages: list[QWidget] = []
        for label, page_class in PAGE_DEFS:
            self.nav.addItem(label)
            page = page_class(self)
            apply_design_spacing(page)
            self.pages.append(page)
            self.stack.addWidget(page)
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.nav.currentRowChanged.connect(self._page_changed)
        self.nav.setCurrentRow(0)
        self.statusBar().showMessage("Ready")

    # -- cross-page services ------------------------------------------------

    def status(self, message: str) -> None:
        self.statusBar().showMessage(message, 6000)

    def apply_theme(self, theme: str) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(theme))
        for page in self.pages:
            handler = getattr(page, "on_theme_changed", None)
            if callable(handler):
                handler(theme)

    def refresh_history_pages(self, except_page=None) -> None:
        for page in self.pages:
            if page is except_page:
                continue
            if isinstance(page, (HistoryPage, ReportsPage)):
                page.refresh()

    # -- internals ------------------------------------------------------------

    def _page_changed(self, index: int) -> None:
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        refresh = getattr(self.pages[index], "refresh", None)
        if callable(refresh):
            refresh()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        for page in self.pages:
            shutdown = getattr(page, "shutdown", None)
            if callable(shutdown):
                shutdown()
        super().closeEvent(event)
