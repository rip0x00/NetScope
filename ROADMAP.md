# Roadmap

Phases are ordered by verifiability in the build environment: what can be
built and tested here comes first. A version is released when its quality
requirements are met, not on a date. Platform statuses live in
`PROJECT_STATUS.md` and are the source of truth; this file describes the
order of work.

## v0.1 — Foundation, core, CLI

- Repository foundation: architecture, decision records, schemas, brand,
  design system. *(Phase A, complete 2026-11-22.)*
- Shared Python core: DNS, TCP, TLS, HTTP probes; error classification;
  latency statistics; verdict engine; report model and exporters.
- CLI over the core: `check`, `scan`, `route` (TCP-based), JSON output.
- Test suite: fixture-based unit tests, no network required.

## v0.2 — Desktop

- PySide6 application on the shared core: Overview, Diagnostics, DNS
  Analyzer, Route Analyzer, Reports, Settings, About.
- Dark and light themes from the design tokens.
- Live monitor view with a latency chart.
- Linux first (verifiable here); Windows from the same codebase.

## v0.3 — Monitoring and history

- Continuous monitoring with bounded concurrency and cancellation.
- SQLite history: sessions, latency series, connection events.
- History views with filtering and session comparison.

## v0.4 — Android

- Native Android application (framework Kotlin, manual pipeline, ADR-002):
  Overview, Diagnostics, Monitor, History, Settings.
- Same schemas, error classification, and verdict rules as the core;
  parity checked against shared fixtures.
- Release-signed APK.

## v0.5 — Advanced diagnostics

- Speed test (download/upload against configurable endpoints, with data-use
  warnings and cancellation).
- TLS/certificate inspection and HTTP timing breakdown.
- IPv6 readiness analysis.
- ICMP route probing where the platform grants raw-socket permission,
  with the TCP fallback retained and labelled.

## v1.0 — Stable Tier-1 release

- Linux, Windows, Android verified on real systems; macOS included only if
  a build host has made it verifiable by then.
- Documentation complete and audited against the shipped behaviour.
- Anti-slop audit (visual, engineering, content) passed for every shipped
  surface.
- Reproducible release builds.

## Beyond v1.0 — undecided, in evaluation order

- Apple platforms (blocked on a macOS/Xcode environment, ADR-003).
- Local developer API (FastAPI, local-only by default).
- Localization beyond English and Persian.
- ChromeOS and BSD verification.
- Optional, opt-in synchronisation.

Nothing in this section is a commitment or a date.
