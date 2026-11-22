"""Desktop settings: a small JSON document in the user config directory.

Settings cover presentation (theme), the defaults other pages start
from (resolvers, speed-test endpoints) and history retention. Loading
never fails: a missing or corrupt file yields the defaults, and
unknown keys are ignored so older files keep working.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from netscope_core.dnsprobe import DEFAULT_RESOLVERS
from netscope_core.speedtest import DEFAULT_DOWNLOAD_URL, DEFAULT_UPLOAD_URL

from . import paths


@dataclass
class Settings:
    theme: str = "dark"  # dark | light
    resolvers: list[str] = field(default_factory=lambda: list(DEFAULT_RESOLVERS))
    speed_download_url: str = DEFAULT_DOWNLOAD_URL
    speed_upload_url: str = DEFAULT_UPLOAD_URL or ""
    history_retention_days: int = 90
    history_max_rows: int = 500

    # -- persistence -----------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path if path is not None else paths.settings_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        settings = cls()
        for key, value in data.items():
            if not hasattr(settings, key):
                continue
            current = getattr(settings, key)
            if isinstance(current, list):
                if isinstance(value, list):
                    setattr(settings, key, [str(v) for v in value])
            elif isinstance(current, int):
                if isinstance(value, int):
                    setattr(settings, key, value)
            elif isinstance(value, str):
                setattr(settings, key, value)
        if settings.theme not in ("dark", "light"):
            settings.theme = "dark"
        if not settings.resolvers:
            settings.resolvers = list(DEFAULT_RESOLVERS)
        return settings

    def save(self, path: Path | None = None) -> Path:
        path = path if path is not None else paths.settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path
