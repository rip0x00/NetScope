"""Application entry point: ``netscope-desktop``.

Loads settings, opens the history store (applying retention), builds
the main window with the saved theme, and runs the event loop. When
PySide6 is unavailable the program exits with code 2 and a plain
message explaining how to install it — the core engine and CLI keep
working without a GUI.
"""

from __future__ import annotations

import sys

from . import paths


def main() -> int:
    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "NetScope desktop needs PySide6. Install it with:\n"
            "  pip install \"netscope-desktop[gui]\"  or  pip install PySide6",
            file=sys.stderr,
        )
        return 2

    from .history import HistoryStore
    from .main_window import MainWindow
    from .settings import Settings

    app = QApplication(sys.argv)
    app.setApplicationName("NetScope")
    app.setOrganizationName("NetScope contributors")

    icon_path = paths.app_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    settings = Settings.load()
    store = HistoryStore()
    store.prune(settings.history_retention_days, settings.history_max_rows)

    window = MainWindow(settings, store)
    window.apply_theme(settings.theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
