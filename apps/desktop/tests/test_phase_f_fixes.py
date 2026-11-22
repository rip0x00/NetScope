"""Regression tests for Phase F findings F-01 and F-02.

F-01: page layout margins/spacing were Qt defaults (9 px / 6 px),
off the design system's 4 px-base scale. Layouts are now set from
``theme.design_spacing`` by ``pages.common.apply_design_spacing``.

F-02: the brand icon was not shipped in the desktop wheel, so an
installed copy had no window icon and a blank About-page icon.
``paths.brand_asset_path`` now resolves the copy packaged in
``netscope_desktop.assets`` first, with the repository checkout as
fallback.

All GUI evidence is offscreen (see ``test_gui.py``).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel

from netscope_desktop import paths
from netscope_desktop.history import HistoryStore
from netscope_desktop.main_window import PAGE_DEFS, MainWindow
from netscope_desktop.pages.common import iter_layouts
from netscope_desktop.settings import Settings
from netscope_desktop.theme import build_stylesheet, design_spacing, spacing_scale

DESKTOP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = DESKTOP_DIR.parents[1]


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


# ---------------------------------------------------------------------------
# F-01 — spacing
# ---------------------------------------------------------------------------


def test_all_page_layouts_use_design_spacing(window) -> None:
    scale = spacing_scale()
    spacing = design_spacing()
    assert len(window.pages) == len(PAGE_DEFS) == 11

    total_layouts = 0
    for (label, _page_class), page in zip(PAGE_DEFS, window.pages):
        layouts = iter_layouts(page)
        assert layouts, label
        total_layouts += len(layouts)
        top = page.layout()
        margins = top.contentsMargins()
        assert (
            margins.left(),
            margins.top(),
            margins.right(),
            margins.bottom(),
        ) == (spacing["page_margin"],) * 4, label
        for layout in layouts:
            m = layout.contentsMargins()
            for value in (m.left(), m.top(), m.right(), m.bottom()):
                assert value in scale, (label, "margin", value)
            if isinstance(layout, QFormLayout):
                assert layout.horizontalSpacing() in scale, label
                assert layout.verticalSpacing() in scale, label
            else:
                assert layout.spacing() in scale, (label, "spacing", layout.spacing())
    # Sanity: the walk really reaches nested layouts (group boxes,
    # control rows, scroll content), not just the 11 top layouts.
    assert total_layouts > 50


def test_stylesheet_paddings_are_on_the_spacing_scale() -> None:
    scale = set(spacing_scale()) | {0}
    for theme in ("dark", "light"):
        stylesheet = build_stylesheet(theme)
        for declaration in re.findall(r"padding:\s*([^;]+);", stylesheet):
            for value in re.findall(r"(\d+)px", declaration):
                assert int(value) in scale, (theme, declaration)


# ---------------------------------------------------------------------------
# F-02 — packaged brand assets
# ---------------------------------------------------------------------------


def test_brand_asset_resolves_from_the_package() -> None:
    icon = paths.app_icon_path()
    assert icon is not None
    assert icon.is_file()
    # The packaged copy wins over the repository checkout.
    assert "netscope_desktop" in icon.parts
    assert icon.name == "app-icon.svg"
    assert paths.brand_asset_path("does-not-exist.svg") is None


def test_brand_asset_is_a_valid_svg(qapp) -> None:
    from PySide6.QtSvg import QSvgRenderer

    icon = paths.app_icon_path()
    assert icon is not None
    renderer = QSvgRenderer(str(icon))
    assert renderer.isValid()


def test_about_page_icon_pixmap_is_rendered(window) -> None:
    about = window.pages[-1]
    assert type(about).__name__ == "AboutPage"
    pixmaps = [
        label.pixmap()
        for label in about.findChildren(QLabel)
        if label.pixmap() is not None and not label.pixmap().isNull()
    ]
    assert pixmaps, "About page shows no brand icon"
    assert (pixmaps[0].width(), pixmaps[0].height()) == (72, 72)


def test_desktop_wheel_contains_brand_assets(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["TMPDIR"] = str(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(tmp_path),
            str(DESKTOP_DIR),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = list(tmp_path.glob("netscope_desktop-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        assert "netscope_desktop/assets/app-icon.svg" in names
        packaged = archive.read("netscope_desktop/assets/app-icon.svg")
    canonical = (REPO_DIR / "assets" / "branding" / "app-icon.svg").read_bytes()
    assert packaged == canonical
