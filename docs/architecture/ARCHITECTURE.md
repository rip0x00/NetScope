# Architecture

NetScope is a monorepo. One shared diagnostic model runs on every platform;
each platform has its own interface and its own operating-system integrations.
Nothing in the shared layers knows which UI produced a request.

## Layers

```
        Desktop (PySide6)        CLI              Android (Kotlin)
              \                    |                    /
               \                   |                   /
        Platform adapters (interfaces, permissions, OS APIs)
                              |
        Shared core — diagnostic engine, statistics, verdicts,
        troubleshooting rules, report model
                              |
        Shared contracts — JSON Schemas in shared/schemas/
```

### Shared contracts — `shared/schemas/`

The data contract is defined once, as JSON Schema (draft 2020-12):

- `diagnostic-result.schema.json` — one check: status, timestamp, target,
  protocol, duration, measured values (including a latency distribution with
  min/max/average/median/p90/p95/p99/standard deviation), structured error,
  confidence, explanation.
- `report.schema.json` — one session: the results, the platform they were
  measured on, and a single session verdict with recommendations.

Every implementation (Python, Kotlin, and later Swift) produces and consumes
these shapes. Schemas are versioned (`schemaVersion`); minor versions may add
fields, never change the meaning of existing ones.

### Shared core — `shared/core/`

The reference implementation of the diagnostic engine, in Python, used
directly by the desktop application and the CLI:

- Probe modules per layer: DNS, TCP, TLS, HTTP, latency, route.
- Statistics: latency distribution, jitter, packet-loss accounting.
- Error classification shared by all probes, so a connection reset means the
  same thing in every report.
- Verdict engine: classifies a session from corroborating probe evidence.
- Troubleshooting rules: measured facts, possible causes, and recommendations
  kept as separate fields — never merged into a single confident claim.
- Report model and exporters (Markdown, HTML, JSON).

The core is standard-library-first. A third-party dependency is added only
when the standard library cannot do the job (the desktop UI toolkit is the
standing example).

### Platform adapters

Operating-system specifics live outside the core: interface enumeration,
resolver configuration, permission handling, Wi-Fi information, background
execution rules. Adapters return the shared result shape and report what the
platform would not disclose as an explicit limitation, never as invented data.

### Applications — `apps/`

- `apps/desktop/` — PySide6 application (Linux verified; Windows from the
  same codebase, unverified; macOS when a build host exists). Consumes
  the shared core in-process.
- `apps/cli/` — command-line interface over the same core; readable output by
  default, `--json` for the report schema.
- `apps/android/` — native Android application in framework Kotlin, built with
  the manual pipeline (ADR-002). It re-implements the probes against Android
  APIs but implements the same schemas, the same error classification, and the
  same verdict rules; parity is checked against shared test fixtures.

## Storage

Desktop history is a local SQLite database (ADR-005): measurements, sessions,
and events, with retention and deletion controls. Android uses its own local
storage behind the same report model. There is no account system and no
synchronisation in the current roadmap; if sync is ever added it is opt-in
and off by default.

## Privacy boundaries

- No telemetry. No analytics. No hidden network requests: the only outbound
  traffic is the diagnostic traffic the user asked for, to the targets the
  user specified (plus explicitly configured public resolvers).
- Reports redact private identifiers by default before export.
- No feature requires administrator rights for ordinary diagnostics; anything
  that would need elevation says so before it runs.

## Repository layout

```
apps/            desktop, cli, android applications
shared/core/     Python reference diagnostic engine (desktop + CLI)
shared/schemas/  JSON Schema data contracts
assets/branding/ logo system, app icons, design tokens
docs/            architecture, design, networking, security, platforms
packaging/       installer and distribution definitions
scripts/         build and maintenance scripts
.github/         CI workflows and contribution templates
```
