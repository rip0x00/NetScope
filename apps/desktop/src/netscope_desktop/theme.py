"""Stylesheet generation from the shared design tokens.

The single source of truth is ``assets/branding/tokens.json`` (see
``docs/design/DESIGN_SYSTEM.md``). The stylesheet for both themes is
generated from those values; nothing is hard-coded per widget. When the
tokens file is not reachable (an installed copy outside a repository
checkout), the embedded copy below — identical to tokens.json — is
used.
"""

from __future__ import annotations

import json
from pathlib import Path

# Embedded fallback, kept identical to assets/branding/tokens.json.
_FALLBACK_TOKENS: dict = {
    "color": {
        "dark": {
            "accent": "#3987D8", "accentSecondary": "#36A7B8",
            "background": "#101419", "backgroundSecondary": "#151B22",
            "border": "#303B47", "error": "#D65B61", "success": "#36A879",
            "surface": "#1B232C", "surfaceElevated": "#222C37",
            "text": "#EDF2F7", "textMuted": "#687787",
            "textSecondary": "#9AA8B7", "warning": "#D69A42",
        },
        "light": {
            "accent": "#2F6FB3", "accentSecondary": "#22707E",
            "background": "#F7F9FB", "backgroundSecondary": "#EDF1F5",
            "border": "#D5DEE7", "error": "#B23A42", "success": "#1F7A54",
            "surface": "#FFFFFF", "surfaceElevated": "#FFFFFF",
            "text": "#14202B", "textMuted": "#66788C",
            "textSecondary": "#43556A", "warning": "#9A6414",
        },
    },
    "typography": {
        "fontFamilyUi": "Inter, -apple-system, 'Segoe UI', sans-serif",
        "fontFamilyMono": "'JetBrains Mono', ui-monospace, monospace",
    },
    "spacing": {"base": 4, "scale": [4, 8, 12, 16, 24, 32, 48]},
}

THEMES = ("dark", "light")


def load_tokens() -> dict:
    """Load tokens.json from the repository checkout, or the embedded copy."""
    candidate = Path(__file__).resolve().parents[4] / "assets" / "branding" / "tokens.json"
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
        if "color" in data and "typography" in data:
            return data
    except (OSError, ValueError):
        pass
    return _FALLBACK_TOKENS


def spacing_scale(tokens: dict | None = None) -> list[int]:
    """The design system's spacing scale (4 px base) from the tokens."""
    tokens = tokens if tokens is not None else load_tokens()
    scale = tokens.get("spacing", {}).get("scale")
    if not scale:
        scale = _FALLBACK_TOKENS["spacing"]["scale"]
    return [int(value) for value in scale]


def design_spacing(tokens: dict | None = None) -> dict[str, int]:
    """Semantic layout spacing, each value a member of the token scale.

    This is the single place the desktop's layout rhythm is decided
    (finding F-01): pages and the stylesheet take every margin,
    spacing and padding from here instead of Qt defaults or scattered
    literals.

    - ``page_margin``: inset of a page's top-level layout (16).
    - ``content_margin``: inset of nested layouts — group-box
      contents and control rows (8; the Qt default was 9, off-scale).
    - ``item_spacing``: gap between sibling widgets (8; the Qt
      default was 6, off-scale).
    - ``control_padding_vertical`` / ``control_padding_horizontal``:
      stylesheet padding inside buttons and inputs (4 / 12; the
      stylesheet previously used 5–6 px vertical and 14 px
      horizontal, all off-scale).
    """
    scale = spacing_scale(tokens)

    def pick(value: int) -> int:
        if value in scale:
            return value
        return min(scale, key=lambda candidate: abs(candidate - value))

    return {
        "page_margin": pick(16),
        "content_margin": pick(8),
        "item_spacing": pick(8),
        "control_padding_vertical": pick(4),
        "control_padding_horizontal": pick(12),
    }


def theme_colors(theme: str, tokens: dict | None = None) -> dict[str, str]:
    """The colour map for one theme (``dark`` or ``light``)."""
    if theme not in THEMES:
        raise ValueError(f"unknown theme: {theme}")
    tokens = tokens if tokens is not None else load_tokens()
    return dict(tokens["color"][theme])


def build_stylesheet(theme: str, tokens: dict | None = None) -> str:
    """Generate the Qt stylesheet for ``theme`` from the design tokens."""
    tokens = tokens if tokens is not None else load_tokens()
    c = theme_colors(theme, tokens)
    sp = design_spacing(tokens)
    ui_font = tokens["typography"]["fontFamilyUi"]
    mono_font = tokens["typography"]["fontFamilyMono"]
    return f"""
QWidget {{
    background: {c['background']};
    color: {c['text']};
    font-family: {ui_font};
    font-size: 14px;
}}
QMainWindow, QDialog {{ background: {c['background']}; }}
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: 20px; font-weight: 600; }}
QLabel[role="subtitle"] {{ font-size: 16px; font-weight: 600; }}
QLabel[role="secondary"] {{ color: {c['textSecondary']}; }}
QLabel[role="muted"] {{ color: {c['textMuted']}; font-size: 12px; }}
QLabel[status="ok"] {{ color: {c['success']}; font-weight: 600; }}
QLabel[status="degraded"] {{ color: {c['warning']}; font-weight: 600; }}
QLabel[status="failed"] {{ color: {c['error']}; font-weight: 600; }}
QFrame[role="panel"], QGroupBox {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 6px;
}}
QGroupBox {{ margin-top: 16px; padding-top: 8px; }}
QGroupBox::title {{
    subcontrol-origin: margin; left: 8px; padding: 0 4px;
    color: {c['textSecondary']}; font-weight: 600; background: transparent;
}}
QListWidget#nav {{
    background: {c['backgroundSecondary']};
    border: none; border-right: 1px solid {c['border']};
    outline: none; padding: 8px 0;
}}
QListWidget#nav::item {{ padding: 8px 16px; min-height: 24px; }}
QListWidget#nav::item:selected {{ background: {c['accent']}; color: #FFFFFF; }}
QListWidget#nav::item:hover:!selected {{ background: {c['surface']}; }}
QPushButton {{
    background: {c['surfaceElevated']};
    border: 1px solid {c['border']};
    border-radius: 4px; padding: {sp['control_padding_vertical']}px {sp['control_padding_horizontal']}px; min-height: 20px;
}}
QPushButton:hover {{ border-color: {c['accent']}; }}
QPushButton:disabled {{ color: {c['textMuted']}; }}
QPushButton[primary="true"] {{
    background: {c['accent']}; color: #FFFFFF; border: 1px solid {c['accent']};
    font-weight: 600;
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 4px; padding: {sp['control_padding_vertical']}px {sp['item_spacing']}px;
    selection-background-color: {c['accent']}; selection-color: #FFFFFF;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {c['accent']}; }}
QPlainTextEdit, QTextEdit, QTableWidget {{ font-family: {mono_font}; font-size: 13px; }}
QTableWidget {{
    background: {c['surface']}; gridline-color: {c['border']};
    border: 1px solid {c['border']}; border-radius: 6px;
    selection-background-color: {c['accentSecondary']}; selection-color: #FFFFFF;
}}
QHeaderView::section {{
    background: {c['backgroundSecondary']}; color: {c['textSecondary']};
    border: none; border-bottom: 1px solid {c['border']};
    padding: {sp['control_padding_vertical']}px {sp['item_spacing']}px; font-weight: 600; font-family: {ui_font};
}}
QProgressBar {{
    background: {c['surface']}; border: 1px solid {c['border']};
    border-radius: 4px; text-align: center; min-height: 16px;
}}
QProgressBar::chunk {{ background: {c['accent']}; }}
QScrollBar:vertical {{ background: {c['backgroundSecondary']}; width: 12px; border: none; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 6px; min-height: 24px; }}
QScrollBar:horizontal {{ background: {c['backgroundSecondary']}; height: 12px; border: none; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 6px; min-width: 24px; }}
QStatusBar {{ background: {c['backgroundSecondary']}; color: {c['textSecondary']}; }}
QToolTip {{ background: {c['surfaceElevated']}; color: {c['text']}; border: 1px solid {c['border']}; }}
"""
