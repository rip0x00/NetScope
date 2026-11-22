"""Test bootstrap for the desktop package.

The tests import the package from ``src`` so they exercise the working
tree even when an editable install is unavailable. Qt is configured
for the offscreen platform before any test module imports PySide6.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
