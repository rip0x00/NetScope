# Architecture Decisions

Each record states the decision, the context that forced it, and the
consequence. Deviations from the master specification are recorded here with
their reasons, never silently.

## ADR-001 — Python shared core for desktop and CLI

**Status:** accepted, 2026-11-22.

**Context.** The desktop application and the CLI must produce identical
diagnostics; duplicating the engine per front-end guarantees drift. Python
3.12 is available and verified in the build environment, and the diagnostic
work (DNS, TCP, TLS, HTTP, timing) is I/O-bound, not CPU-bound.

**Decision.** One Python package is the reference diagnostic engine. The
desktop application and the CLI are both front-ends to it. The core is
standard-library-first; PySide6 is a desktop-only dependency.

**Consequences.** Verdict logic, statistics, and report generation exist in
exactly one place for desktop-class platforms. Mobile platforms re-implement
against the same schemas and shared fixtures (ADR-004).

## ADR-002 — Android in framework Kotlin via the manual pipeline

**Status:** accepted, 2026-11-22. **Deviation from the master specification,
Part 8** (which prefers Jetpack Compose and AndroidX).

**Context.** Gradle cannot run in the build environment: the Gradle daemon's
local IPC fails because outbound TCP from Java processes is intercepted and
closed (verified; the manual pipeline exists for exactly this reason).
Jetpack Compose and AndroidX are normally delivered and built through
Gradle. A verified manual pipeline is available instead: Kotlin compiler
2.4.10 (embeddable), Android build-tools 35.0.0 (aapt2, d8, zipalign,
apksigner), platform android-35, Temurin JDK 17.

**Decision.** The Android application is written in Kotlin against the
Android framework only — no AndroidX, no Compose — and built with the manual
pipeline. Material-style components are implemented with framework views,
styled by the NetScope design tokens. The deviation is revisited if a
working Gradle environment becomes available; the application's internal
layering (probes / model / UI) is kept separable so a Compose UI could
replace the view layer without touching diagnostics.

**Consequences.** The app is buildable and verifiable here, at the cost of
more hand-written UI code and no access to AndroidX conveniences (Room,
Navigation). Local storage uses the framework SQLite APIs directly.

## ADR-003 — Apple platforms: contracts and documentation only, for now

**Status:** accepted, 2026-11-22.

**Context.** There is no macOS host, no Xcode, and no Swift toolchain in the
build environment. Swift code written here could not be compiled, run, or
tested, and the project's rule is that unverifiable code is not shipped or
claimed.

**Decision.** For iOS, iPadOS, and the native-macOS option, this repository
currently carries the shared schemas and platform documentation only. No
Swift sources are written until a macOS environment exists in which they can
be built and tested. The desktop application remains PySide6-based, which
keeps a macOS build possible later without a second desktop codebase.

**Consequences.** Apple platforms are listed as `documented-only` in the
capability matrix and are never described as supported.

## ADR-004 — JSON Schemas are the cross-platform data contract

**Status:** accepted, 2026-11-22.

**Context.** Three implementation languages (Python now; Kotlin next; Swift
eventually) need one definition of a diagnostic result and a report, or the
platforms will diverge in exactly the fields users compare.

**Decision.** `shared/schemas/` holds JSON Schema (draft 2020-12) definitions
of the diagnostic result and the report. They are the contract: platform
code is written to them, shared test fixtures are written against them, and
changes follow the versioning rule in `docs/architecture/ARCHITECTURE.md`.

**Consequences.** Cross-platform parity is testable. Schema changes are
deliberate, reviewed events rather than side effects of one platform's code.

## ADR-005 — SQLite for desktop history

**Status:** accepted, 2026-11-22.

**Context.** Monitoring and history need durable, queryable local storage
with filters and comparisons. The data is single-user and local; a server
database would be unjustified complexity.

**Decision.** Desktop history is stored in SQLite through the Python standard
library. Retention limits and full deletion are part of the storage layer,
not afterthoughts. Android stores the same report model in its own local
SQLite database (framework APIs, per ADR-002).

## ADR-006 — Zero telemetry, no hidden network traffic

**Status:** accepted, 2026-11-22.

**Context.** A diagnostic tool that quietly contacts its own servers would
contradict its purpose, and its measurements would be suspect.

**Decision.** NetScope sends no telemetry and makes no network requests other
than the diagnostics the user initiates (and resolver queries to resolvers
the user configured or the system provided). Updates are checked only where
the user enables it, in later phases. This is a product invariant, not a
setting that defaults on.
