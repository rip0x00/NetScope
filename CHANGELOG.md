# Changelog

All notable changes are recorded here. A version is listed when it
is released, not when it is planned.

## Versioning

Release versions (for example `v0.1.0`) are **ecosystem /
repository releases**: one version for the whole NetScope
repository, marking a published state of all components together.
They do **not** replace component versions. Each component is
versioned independently and keeps its own version wherever it is
installed or displayed:

| Component | Version at the v0.1.0 ecosystem release |
|---|---|
| Shared core (`netscope-core`) | 0.1.0 |
| CLI (`netscope-cli`) | 0.1.0 |
| Desktop (`netscope-desktop`) | 0.2.0 |
| Android app | 0.4.0 (versionCode 1) |

## [Unreleased]

Nothing yet.

## [0.1.0] — 2026-11-22

First public release of the NetScope ecosystem, published at
https://github.com/rip0x00/NetScope. Everything below is
implemented and tested as stated; platform limitations are listed
at the end of this entry and are part of the release's status, not
fine print.

### Added

- Project foundation: architecture documentation and decision
  records (ADR-001 to ADR-006), including the recorded deviations
  for Android (framework Kotlin via the manual build pipeline) and
  Apple platforms (documentation only until a macOS build host
  exists).
- Shared data contracts: `diagnostic-result` and `report` JSON
  Schemas (draft 2020-12) in `shared/schemas/`.
- Brand identity: original reticle mark in seven SVG variants and
  machine-readable design tokens in `assets/branding/`.
- Design system: dark and light palettes with measured contrast
  ratios, typography, spacing, iconography, motion, and
  accessibility rules in `docs/design/DESIGN_SYSTEM.md`.
- Project tracking: capability audit and platform matrix in
  `PROJECT_STATUS.md`, roadmap, and development log.

- Shared core engine — `netscope-core` 0.1.0 (`shared/core/`):
  layered host diagnostics (DNS, TCP, TLS, HTTP) measured with
  real phase timings; a hand-rolled DNS wire codec (A, AAAA,
  CNAME, MX, NS, TXT, SOA, PTR, SRV, CAA) with system-vs-public
  resolver comparison and poisoning flags; latency statistics
  (min/max/average/median/p90/p95/p99, standard deviation, jitter,
  packet loss); route tracing (ICMP with a TCP-TTL fallback);
  a configurable speed test; local interface inventory; a
  ten-code verdict engine (OK, DNS_POISONED, DNS_BLOCKED,
  TCP_BLOCKED, TLS_SNI_BLOCKED, HTTP_FILTERED, SERVER_DOWN,
  NETWORK_UNREACHABLE, SLOW_UNSTABLE, UNKNOWN); rule-based
  troubleshooting that keeps measured facts, possible causes and
  recommendations separate; and report rendering to JSON,
  Markdown, HTML and CSV. 87 tests pass, including validation of
  outputs against the shared JSON Schemas.

- Command-line interface — `netscope-cli` 0.1.0 (`apps/cli/`):
  nine commands over the shared core (`diagnose`, `dns`,
  `latency`, `route`, `speed`, `interfaces`, `status`, `monitor`,
  `version`), human and `--json` output, exit codes 0/1/2.
  24 tests pass.

- Desktop application — `netscope-desktop` 0.2.0
  (`apps/desktop/`): PySide6 client over the shared core with
  eleven pages (Overview, Live Monitor, Diagnostics, DNS
  Analyzer, Speed Test, Route Analyzer, Interfaces, History,
  Reports, Settings, About); SQLite history; JSON settings;
  dark and light themes generated from the design tokens;
  exports to Markdown, HTML, JSON, CSV and PDF. 20 tests pass.
  Verified on Linux with all GUI verification offscreen,
  including a fresh-venv install/launch/uninstall cycle.

- Android application — versionName 0.4.0, versionCode 1
  (`apps/android/`): framework Kotlin (no Gradle, per ADR-002)
  port of the core — DNS wire codec, probes, statistics,
  ten-code verdicts and troubleshooting rules — in one activity
  with six sections (Overview, Monitor, Diagnostics, Tools,
  History, Settings), SQLite history and a release-signed APK.
  59 JVM unit tests pass; the APK signature and badging are
  verified. **The app has not been run on a device or emulator.**

### Platform status at this release

- **Linux: supported** — core, CLI and desktop implemented and
  tested on Linux. Caveat: desktop GUI verification is
  offscreen-only (including the fresh-venv install/launch check);
  the desktop has not yet been run on a physical display.
- **Android: implemented** — JVM-tested and release-signed, but
  not device-tested, so it is not listed as supported.
- **Windows: unverified** — the same Python codebase; never
  executed on Windows.
- **macOS: documented only** — unverified; no build host
  available.
