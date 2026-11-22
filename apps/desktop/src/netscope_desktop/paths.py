"""User data and configuration locations for the desktop application.

The desktop app follows the XDG base-directory convention on Linux and
uses the same layout everywhere for predictability:

- Data (history database): ``$XDG_DATA_HOME/netscope/`` or
  ``~/.local/share/netscope/`` — the history database is
  ``history.db`` inside it.
- Configuration (settings): ``$XDG_CONFIG_HOME/netscope/`` or
  ``~/.config/netscope/`` — the settings file is ``settings.json``
  inside it.

The environment variables ``NETSCOPE_DATA_DIR`` and
``NETSCOPE_CONFIG_DIR`` override both locations (used by tests and by
portable installs). Nothing is written anywhere else.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "netscope"


def data_dir() -> Path:
    override = os.environ.get("NETSCOPE_DATA_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_DIR_NAME


def config_dir() -> Path:
    override = os.environ.get("NETSCOPE_CONFIG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_DIR_NAME


def history_db_path() -> Path:
    return data_dir() / "history.db"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def branding_dir() -> Path | None:
    """The repository's ``assets/branding`` directory, when running from a checkout."""
    candidate = Path(__file__).resolve().parents[4] / "assets" / "branding"
    return candidate if candidate.is_dir() else None


def brand_asset_path(filename: str) -> Path | None:
    """Resolve a brand asset file the desktop loads (finding F-02).

    The copy packaged inside ``netscope_desktop.assets`` wins, so a
    wheel install resolves its icons with no repository checkout.
    When running from a checkout without the packaged copy, the
    shared ``assets/branding`` directory is the fallback. Returns
    ``None`` when neither location has the file.
    """
    try:
        from importlib.resources import files

        packaged = files("netscope_desktop.assets").joinpath(filename)
        if packaged.is_file():
            return Path(str(packaged))
    except (ImportError, ModuleNotFoundError):
        pass
    branding = branding_dir()
    if branding is not None:
        candidate = branding / filename
        if candidate.is_file():
            return candidate
    return None


def app_icon_path() -> Path | None:
    """The application icon (window icon and About-page logo)."""
    return brand_asset_path("app-icon.svg")
