# NetScope Desktop

PySide6 desktop application over the shared `netscope_core` diagnostic
engine. The desktop package is a front end only: DNS, TCP, TLS, HTTP,
route and speed measurements, verdicts and report rendering all come
from `shared/core/`.

## Current status

Verified on Linux on 2026-11-22 (all GUI verification offscreen; the
application has never run on a physical display).

The first verification round found two startup blockers — a
`HistoryStore.clear()` / `prune()` deadlock (both called `count()`
while holding the store's non-reentrant lock, hanging the entry point
before any window appeared) and `AboutPage` reading
`netscope_core.VERSION`, which the core does not expose (it provides
`__version__`). Both were fixed the same day (the count moved to a
`_count_unlocked()` helper under the existing strict lock; the About
page uses `__version__`) and re-verified: the desktop suite passes
(20 tests, including regression tests for both defects), the real
entry point launches and exits cleanly, all eleven pages navigate,
theme switching, SQLite history (including Clear-all) and PDF export
all work, and a fresh-venv install of the built wheel renders the
window icon and the About-page icon. See `DEVELOPMENT_LOG.md` and
`PROJECT_STATUS.md` at the repository root for the full record.

## Install

From the repository root, in the project virtual environment:

```sh
.venv/bin/pip install -e shared/core
.venv/bin/pip install -e apps/desktop
```

The desktop package depends on `netscope-core` and `PySide6>=6.6`.
There is no separate `[gui]` extra in the current package metadata.

Headless Linux systems need the Qt runtime libraries (notably EGL/GL)
provided by the operating system. In this repository's development VM,
Qt is run with the offscreen platform for tests:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/netscope-desktop
```

That is a test configuration, not a claim that the application has
been verified on a physical display.

## Run

```sh
.venv/bin/netscope-desktop
```

## Pages

The main window has eleven pages:

1. Overview — local interface summary, quick diagnose, recent runs.
2. Live Monitor — repeated TCP latency samples with a live chart.
3. Diagnostics — full layered check with exports (Markdown, HTML,
   JSON, CSV, PDF).
4. DNS Analyzer — record lookups across the configured resolvers.
5. Speed Test — configurable download/upload endpoints.
6. Route Analyzer — hop table and stop-point summary.
7. Interfaces — local network inventory and its stated limitations.
8. History — stored diagnostic runs in SQLite.
9. Reports — session and stored reports with export.
10. Settings — theme, resolvers, speed endpoints, history retention.
11. About — version, platform and data-location information.

## Data locations

Following `netscope_desktop.paths`:

- History database: `$XDG_DATA_HOME/netscope/history.db`, or
  `~/.local/share/netscope/history.db` when `XDG_DATA_HOME` is unset.
- Settings: `$XDG_CONFIG_HOME/netscope/settings.json`, or
  `~/.config/netscope/settings.json` when `XDG_CONFIG_HOME` is unset.
- `NETSCOPE_DATA_DIR` and `NETSCOPE_CONFIG_DIR` override both
  locations (used by tests and portable installs).

No telemetry is sent. Network traffic is limited to the diagnostics
the user runs, to the targets the user specifies.
