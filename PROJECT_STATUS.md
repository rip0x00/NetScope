# Project Status

Last updated: 2026-11-22. Phase B (shared core engine) and Phase D
(CLI) complete: the Python core exists and is tested, and the CLI is
implemented and verified in the Linux development environment (24 CLI
tests + 87 core tests passing; four smoke commands run on the sandbox
network). Phase C (desktop) is complete and verified in this
environment: the two startup blockers found by its 2026-11-22
verification (a history-store deadlock and an About-page version
attribute error) were fixed the same day and the follow-up
verification passed — 20 desktop tests (14 at Phase C, plus 6
Phase F regression tests), a real launch through the
entry point, navigation of all eleven pages, core integration,
theme switching, history clear/prune and PDF export, all offscreen.
Phase E (Android) is
implemented: the app builds to a release-signed APK with 59 passing
JVM unit tests, but it has not been run on a device or emulator.
Phase F (anti-slop audit + packaging) is complete: the audit found
no critical or high-severity issues (two medium conformance gaps —
page spacing uses Qt defaults instead of the design scale, and the
brand assets are not shipped in the desktop wheel), and the Linux
packages (wheels + sdists for core, CLI and desktop) were built
and verified through a fresh-venv install/launch/uninstall cycle.
Windows and macOS packaging is not verified. See
`docs/qa/PHASE_F_AUDIT.md` and the Phase F entry in
`DEVELOPMENT_LOG.md`.
Phase G (GitHub publication) was authorized on 2026-11-22. Its
pre-publication review found the publish set to be 112 files
(`docs/qa/PUBLISH_MANIFEST.md`), the secrets scan clean, and stale
platform claims in the README and app docs corrected; the test
baseline of the exact tree is 131 passing (core 87, CLI 24,
desktop 20). The repository was published the same day at
https://github.com/rip0x00/NetScope (public): all 112 files were
uploaded through the browser workflow only, in 24 commits on
`main`, and the final tree was verified on the repository home
page with the README rendering. No version tag or GitHub Release
exists; creating one requires the user's separate approval of the
proposed version, release notes and exact assets.

## Environment audit

Every entry below was verified in the build environment on 2026-11-22 by running
the tool or a probe, not assumed.

| Capability | Result | Evidence |
|---|---|---|
| Host OS | Linux x86_64 (Ubuntu userland) | `uname -a` |
| Python | 3.12.3, pip 24.0, `venv` works | `python3 --version`, test venv created |
| PySide6 | Installable: pip resolves PySide6 6.12.0 | `pip install --dry-run PySide6` → "Would install PySide6-6.12.0 …" |
| pytest | Installable: pip resolves pytest 9.2.0 (not preinstalled) | `pip install --dry-run pytest` |
| PyInstaller | Installable: pip resolves PyInstaller 6.22.3 (not preinstalled) | `pip install --dry-run pyinstaller` |
| JDK | OpenJDK Temurin 17.0.21, bundled at `~/workspace/tools/android/jdk` (not on `PATH`) | `java -version` from that path |
| Kotlin compiler | kotlin-compiler-embeddable 2.4.10 jar in `~/workspace/tools/m2repo`, with kotlin-stdlib 2.4.10 | directory listing |
| Android SDK tools | build-tools 35.0.0 (`aapt2`, `d8`, `apksigner`, `zipalign`), platform android-35 | directory listing |
| Git | 2.43.0 | `git --version` |
| HTTPS egress | Works through a proxy (pypi.org returned 200) | `urllib` request |

### Known environment constraints

- **`/tmp` is a 512 MB tmpfs.** Package installs that unpack large wheels
  (PySide6) fail there with "No space left on device". Installs must run with
  `TMPDIR` pointing at the home filesystem (142 GB free).
- **Gradle is unusable in this VM.** The distribution is present on disk, but
  the Gradle daemon's local IPC fails here (outbound TCP from Java processes
  is intercepted and closed), so Gradle builds cannot run. Android builds use
  the manual pipeline (kotlinc + aapt2 + d8 + zipalign + apksigner) driven by
  shell scripts.
- **No macOS host, no Xcode, no Swift toolchain.** Apple-platform code cannot
  be compiled or tested here.
- **No Windows host.** Windows behaviour can be coded for and reviewed, not
  executed here.
- **Raw sockets are denied.** Creating an `AF_INET/SOCK_RAW` socket returns
  `PermissionError: [Errno 1] Operation not permitted`. ICMP-based probing
  cannot be exercised in this environment; TCP-based measurement is the
  testable path.
- **Network results in this environment describe the sandbox, not the
  internet.** Egress is proxied; resolver answers and latencies measured here
  must never be presented as real-world measurements.

## Platform capability matrix

Status values: `supported` (implemented and tested on that platform),
`implemented` (built and verified, but platform support not yet claimed),
`in-progress`, `planned` (designed, not built), `documented-only`
(contracts and documentation, no implementation scheduled in this
environment).

| Platform | Tier | Status | Notes |
|---|---|---|---|
| Linux | 1 | supported | Supported — core, CLI and desktop implemented and tested on Linux; desktop GUI verification is offscreen-only and the desktop has not yet been run on a physical display. Detail: shared Python core implemented and tested in the Linux dev environment (87 fixture tests, live smoke on the sandbox network). CLI implemented and verified (24 tests passing; status/diagnose/dns/latency smoke commands run on the sandbox network, 2026-11-22). Desktop implemented and verified offscreen (eleven pages): 20 desktop tests passing; the real entry point launches (the start-up `HistoryStore.prune` deadlock and the About-page `netscope_core.VERSION` AttributeError found by the first verification were fixed and regression-tested); navigation of all 11 pages, Diagnostics core integration with SQLite history write, MainWindow theme switching, history clear-all and PDF export all verified offscreen on the sandbox network. Never run on a physical display. Packaging (Phase F): wheels + sdists for core/CLI/desktop built and verified via a fresh-venv install/launch/uninstall cycle (see `docs/qa/PHASE_F_AUDIT.md`). The core is written portably (no POSIX-only APIs), but it has only been executed on Linux. |
| Windows 10/11 | 1 | planned | Same Python codebase; cannot be executed in this environment, so verification is limited to code review and CI definitions until a Windows runner is available. |
| macOS | 1 | documented-only | PySide6 route is viable in principle; no macOS host exists here to build or verify. Not claimed as supported. |
| Android | 1 | implemented | Framework Kotlin via the manual pipeline (see ADR-002); Jetpack Compose deferred. App 0.4.0 (versionCode 1): six sections over a Kotlin port of the core (DNS wire codec, resolver comparison, TCP/TLS/HTTP probes, core statistics, ten-code verdicts, troubleshooting rules, TTL-limited TCP route trace via `android.system.Os`), SQLite history, SharedPreferences settings, design tokens and reticle identity applied. Verified in the build environment: 59 JVM unit tests pass; the release-signed APK (860,840 bytes) passes `apksigner verify` and badging inspection. **Not run on a device or emulator** — runtime behaviour is verified by compilation and API review only, so this is "implemented", not yet "supported". |
| iOS | 2 | documented-only | Shared schemas and platform notes only. No Swift code will be written until it can be compiled and tested. |
| iPadOS | 2 | documented-only | As iOS. |
| ChromeOS | 3 | documented-only | Expected routes are the Android app and the Linux app; neither is verified on ChromeOS. |
| FreeBSD / BSD | 3 | documented-only | Experimental. The Python core avoids platform-specific calls so a port stays possible; nothing is verified. |

No platform is marked supported before it is implemented and tested on that
platform. This matrix is updated at each release, and the README summary is
kept consistent with it.

## Phase summary

- **Phase A — Foundation (complete, 2026-11-22):** capability audit,
  architecture and decision records, shared JSON Schemas, brand identity,
  design system and tokens, roadmap, repository meta files.
- **Phase B — Shared core engine (complete, 2026-11-22):** the Python
  package `netscope_core` in `shared/core/` — probes (DNS, TCP, TLS,
  HTTP, route, speed), statistics, error classification, verdict engine,
  troubleshooting rules, report renderers — with 87 passing fixture
  tests and schema validation against `shared/schemas/`.
- **Phase D — CLI (complete, 2026-11-22):** the package `netscope_cli`
  0.1.0 in `apps/cli/` — nine commands (diagnose, dns, latency, route,
  speed, interfaces, status, monitor, version) over the shared core.
  Verification was initially blocked by an automated execution-risk
  classification after installation (not a user denial; no approval
  card existed) and was completed after the user's written approval:
  24 CLI tests passing, 87 core tests passing as regression, and four
  smoke commands executed on the sandbox network. See
  `DEVELOPMENT_LOG.md` for the full record.
- **Phase C — Desktop (complete, verified offscreen, 2026-11-22):**
  the package `netscope_desktop` 0.2.0 in `apps/desktop/` — eleven
  PySide6 pages over the shared core, SQLite history, theme support
  and PDF export. Verification was initially blocked by an automated
  execution-risk classification and was run after the user's written
  approval: installation and all 16 module imports verified; the
  first 12-test suite reported 9 passed, 2 failed, 1 error and found
  two launch blockers — (1) `HistoryStore.clear()` / `prune()`
  deadlocked by calling `count()` while holding the store's
  non-reentrant lock, hanging the entry point in `prune()` before
  any window; (2) `AboutPage` read `netscope_core.VERSION`, which
  the core package does not expose (it provides `__version__`), so
  `MainWindow` construction raised `AttributeError`. Both were
  fixed under a follow-up approval (the count moved to a
  `_count_unlocked()` helper under the existing strict lock;
  `__version__` used in the About page), with regression tests
  added: the desktop suite passed with **14 tests** (20 after the
  Phase F regression tests were added), with core (87) and CLI (24)
  regressions green. The follow-up verification launched
  the real entry point (window up, clean exit — previously a hang),
  navigated all 11 pages, switched themes through the main window,
  ran the Diagnostics page against the real core with the run
  persisted to SQLite history, cleared history through the History
  page, and exported a real report to PDF. All GUI verification is
  offscreen; the app has never run on a physical display.
- **Phase E — Android (implemented, 2026-11-22):** the native app
  in `apps/android/` — framework Kotlin per ADR-002, package
  `com.netscope.app`, versionName 0.4.0 / versionCode 1, six
  sections (Overview, Monitor, Diagnostics, Tools, History,
  Settings) over a Kotlin port of the core, design tokens and the
  reticle identity applied, SQLite history, SharedPreferences
  settings. Verification: 59 JVM unit tests passing (statistics,
  DNS fixtures, all ten verdict codes, rules, route
  classification); release-signed APK of 860,840 bytes verified
  with apksigner and aapt2 badging. The app has not been run on a
  device or emulator; that test is still pending. See
  `apps/android/README.md`.
- **Phase F — Anti-slop audit + packaging (complete, 2026-11-22):**
  the desktop UI, core, CLI and (at code level) Android app were
  audited against the design system and the zero-AI-slop rules —
  no critical/high findings; colours are 100% token-conformant, no
  gradients/glassmorphism/emoji icons exist, no fake data is
  displayed, no control is dead, and no telemetry or logging
  exists. Two medium findings (Qt-default page spacing vs the
  design scale; brand assets not shipped in the desktop wheel) and
  nine low/info findings are recorded with recommendations in
  `docs/qa/PHASE_F_AUDIT.md`; none were fixed in the audit phase
  itself. In an approved follow-up round the same day, the two
  medium findings were fixed and re-verified: F-01 — all page
  layout margins/spacings and stylesheet paddings now come from
  the design tokens' 4 px scale via `theme.design_spacing()`
  (desktop suite 20 passed, incl. 6 new regression tests); F-02 —
  `app-icon.svg` ships inside the `netscope_desktop.assets`
  subpackage and is resolved from the installed package, verified
  in a fresh-venv install (window icon and About-page icon render,
  all 11 pages navigate, theme transitions verified, uninstall
  clean). The low/info findings remain open recommendations.
  Linux packaging is verified: wheels + sdists for all three
  Python packages were built into `dist/` from unmodified
  metadata, installed into a fresh venv, launched (CLI commands
  and the desktop entry point), and uninstalled cleanly; the
  Android APK's signature and badging were re-verified. Windows
  and macOS packaging is **not verified** (no such environment;
  portable in principle, untested in fact).
- **Phase G — GitHub publication (complete, 2026-11-22):** the
  repository was reviewed before any upload — full inventory,
  `.gitignore` audit (gaps closed: `*.db`, `.env`, `*.log`, `*.whl`,
  `*.tar.gz`, `*.idsig`, `*.jar`, `.venv*/`), secrets scan (no
  credentials, tokens, private keys, personal addresses or
  infrastructure identifiers in the publish set; the only long hex
  strings are public package hashes and the APK certificate's
  public fingerprint), and a documentation accuracy pass (the root
  README's platform table and the desktop README's status section
  were stale and were corrected to match this matrix; the core
  README's portability claim was qualified to Linux-tested). The
  exact upload set — 112 files — and the exclusion list are in
  `docs/qa/PUBLISH_MANIFEST.md`. The repository was then published
  through the browser only: all 112 files in five upload batches
  plus one evidence commit — 25 commits on `main` — with the final
  tree verified and the README rendering; 0 tags, no Releases, no
  integrations. A version tag and GitHub Release require separate
  approval with proposed notes and assets; the v0.1.0 proposal
  (draft notes plus seven assets with SHA-256 checksums, prepared
  in the final consistency pass) awaits that approval.
- **Next:** the user's decision on the proposed v0.1.0 tag/Release;
  run the Android app on a device; the remaining Phase F low/info
  findings are optional follow-ups.
