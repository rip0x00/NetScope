"""Offscreen GUI tests.

These tests construct real Qt widgets with the offscreen platform.
They do not claim coverage of a physical display.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from netscope_desktop.history import HistoryStore
from netscope_desktop.main_window import PAGE_DEFS, MainWindow
from netscope_desktop.pages.core_pages import MonitorPage
from netscope_desktop.settings import Settings


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


@pytest.fixture()
def window(qapp, tmp_path: Path):
    settings = Settings(theme="dark", resolvers=["1.1.1.1"])
    store = HistoryStore(tmp_path / "history.db")
    main_window = MainWindow(settings, store)
    main_window.show()
    qapp.processEvents()
    try:
        yield main_window
    finally:
        main_window.close()
        qapp.processEvents()
        store.close()


class StubMainWindow:
    def __init__(self, settings: Settings, store: HistoryStore) -> None:
        self.settings = settings
        self.store = store
        self.session_reports = []
        self.messages: list[str] = []

    def status(self, message: str) -> None:
        self.messages.append(message)

    def apply_theme(self, _theme: str) -> None:
        pass

    def refresh_history_pages(self, except_page=None) -> None:
        pass


def test_main_window_registers_and_navigates_all_pages(window, qapp) -> None:
    expected_labels = [label for label, _page_class in PAGE_DEFS]

    assert len(window.pages) == 11
    assert window.stack.count() == 11
    assert [window.nav.item(i).text() for i in range(window.nav.count())] == expected_labels

    for index, label in enumerate(expected_labels):
        window.nav.setCurrentRow(index)
        qapp.processEvents()
        assert window.stack.currentIndex() == index, label
        assert window.stack.currentWidget() is window.pages[index]


def test_about_page_shows_core_version(qapp, tmp_path: Path) -> None:
    """Regression: AboutPage must read ``netscope_core.__version__``.

    It previously formatted ``netscope_core.VERSION``, which the core
    package does not export, so constructing the page — and therefore
    ``MainWindow``, which builds every page — raised ``AttributeError``.
    """
    import netscope_core
    from PySide6.QtWidgets import QLabel

    from netscope_desktop.pages.data_pages import AboutPage

    settings = Settings(theme="dark", resolvers=["1.1.1.1"])
    store = HistoryStore(tmp_path / "history.db")
    stub = StubMainWindow(settings, store)
    try:
        page = AboutPage(stub)  # type: ignore[arg-type]
        texts = [label.text() for label in page.findChildren(QLabel)]
        assert any(f"Core {netscope_core.__version__}" in text for text in texts), texts
    finally:
        store.close()


def test_monitor_page_can_be_constructed_without_main_window(qapp, tmp_path: Path) -> None:
    settings = Settings(theme="dark", resolvers=["1.1.1.1"])
    store = HistoryStore(tmp_path / "history.db")
    stub = StubMainWindow(settings, store)
    try:
        page = MonitorPage(stub)  # type: ignore[arg-type]
        stats = page.sample_once_with_connector(lambda _host, _port: 7.5)
        qapp.processEvents()
        assert stats["last"] == 7.5
        page.shutdown()
    finally:
        store.close()
