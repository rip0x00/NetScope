# Development Log

## 2026-11-22 — Final consistency pass before the first Release

A documentation and artifact consistency pass, performed after
publication and before any tag or Release (neither was created;
both still await the user's final approval).

**Linux status unified.** The README platform table called Linux
"Supported" while the PROJECT_STATUS capability matrix still
listed it as `in-progress` (and its status-value definitions had
no `supported` value at all). One status now applies in both:
**Linux is supported — core, CLI and desktop implemented and
tested on Linux — with the standing caveat that desktop GUI
verification is offscreen-only (including a fresh-venv
install/launch check) and the desktop has not yet been run on a
physical display.** PROJECT_STATUS gained the `supported` status
value, the Linux matrix row was updated, and two stale items were
corrected in passing: the Phase G summary no longer says
publication is pending (it records the 25-commit publication and
the pending release decision), and the Phase C summary now notes
the desktop suite grew from 14 to 20 tests in Phase F.

**CHANGELOG completed.** The `[Unreleased]` section previously
listed only the foundation. CHANGELOG.md now carries a
**Versioning** statement — v0.1.0 is the first ecosystem /
repository release; components stay independently versioned
(core 0.1.0, CLI 0.1.0, desktop 0.2.0, Android 0.4.0) — and a
complete `[0.1.0]` entry describing the core engine, the CLI,
the desktop and the Android app with their test counts and the
platform limitations (Android not device-tested; Windows
unverified; macOS documented-only). The README Status section
points to the Versioning note.

**Release assets verified.** All seven proposed assets exist
with the intended versions. Wheel/sdist internal metadata
(`METADATA` / `PKG-INFO`) matches every filename; the desktop
wheel is confirmed to be the post-F-02 build (it contains
`netscope_desktop/assets/app-icon.svg`); the APK was re-verified
with `apksigner verify` (signer CN=NetScope, O=NetScope
contributors, cert SHA-256
`1e60fca28c1451784e5ae9e1431560f6bcd6f52222387ab56b07a4457681b0ff`)
and `aapt2 dump badging` (package `com.netscope.app`,
versionName 0.4.0, versionCode 1, targetSdk 34, exactly the
INTERNET and ACCESS_NETWORK_STATE permissions).

| File | Size (bytes) | SHA-256 |
|---|---|---|
| netscope_core-0.1.0-py3-none-any.whl | 41,413 | `4e1f584f3dc3ee8c9e2589a6f8d4949cb5c66e547aa130aa862af5688eef705a` |
| netscope_core-0.1.0.tar.gz | 44,771 | `9e6bd734240b5a19ec71ba24ff37917aec32dfd94fbde83ea1cf229c19d8a316` |
| netscope_cli-0.1.0-py3-none-any.whl | 10,741 | `e4005bc686238472e8fed4d239feb4018afe8a20d9f542a7ebcd6d4d1ae35027` |
| netscope_cli-0.1.0.tar.gz | 13,208 | `18a7a91468f60cdc54403971edaecd22d51e7f0fabf106ee193d2e889a0d9792` |
| netscope_desktop-0.2.0-py3-none-any.whl | 34,800 | `055e5e8f7ca49215ad34fd0ce62a2f4430183e9c75af1f5957a6e9eb483d073d` |
| netscope_desktop-0.2.0.tar.gz | 35,133 | `8b6e1fa387c41e8f3b7714268ef02387232c9196715c4dc5bbe6fe8d5c127db5` |
| NetScope.apk (Android 0.4.0) | 860,840 | `c6f310a7a2cea9af69c2892c9481f8f1ff1848003270b13c2510261bf1db5eab` |

**Draft release notes** for "NetScope v0.1.0 — first public
release" were written to `dist/RELEASE_NOTES_v0.1.0.md` (a local
release-prep file in `dist/`, outside the published tree). They
state the test evidence as 131 Python tests (87 core + 24 CLI +
20 desktop) and, separately, 59 Android JVM tests; carry all
platform limitations; and include the checksum table above. No
tag or Release was created.

## 2026-11-22 — Phase G step 2: publication to GitHub

The repository was published on 2026-11-22 at
https://github.com/rip0x00/NetScope (public, owner rip0x00,
description "Understand Your Network. Take Control."), created
empty — no README, .gitignore or license initialized by GitHub.

**Method.** Browser workflow only (the GitHub web upload UI,
per-directory commits to `main`), per the user's standing rule for
this project — no connectors, no `git push`. All 112 files of
`docs/qa/PUBLISH_MANIFEST.md` were uploaded in five batches
(root + .github; apps/android; apps/cli + assets; apps/desktop;
docs + shared), totalling 24 commits on `main`. The final tree was
verified on the repository home page: all 16 top-level entries
present, the README renders, and the directory structure is
preserved at every path.

**Boundaries kept.** No version tag and no GitHub Release were
created (the Releases section is empty); no integrations, apps or
webhooks were enabled and no other repository settings were
changed. Creating a tag or Release remains subject to the user's
separate approval of the proposed version, release notes and exact
assets. This entry and the matching `PROJECT_STATUS.md` update are
uploaded as a follow-up commit so the published continuity
documents carry the publication evidence themselves.

## 2026-11-22 — Phase G step 1: pre-publication review

The user explicitly authorized Phase G (GitHub release preparation
and publication, browser workflow only) with conditions: a final
repository integrity review first, no fabricated CI/badges/release
assets, no Windows/macOS support claims, and no version tag or
GitHub Release without presenting the proposed version, notes and
assets for approval first. This entry records step 1 — the local
review and preparation. Nothing has been published yet.

**Inventory.** 248 files outside `.git` and the virtualenv; the
publishable set (what `.gitignore` leaves standing, verified with
`git add -A -n`) is 112 files including the new
`docs/qa/PUBLISH_MANIFEST.md`. Excluded on disk: the `.venv`
(6,218 files), root `dist/` wheels/sdists (6), Android `build/` and
`dist/` (APKs, dex, jars, idsig), per-package `build/` copies,
`*.egg-info` (17), `__pycache__`/`*.pyc` (54) and `.pytest_cache`
(14). The empty directories `.tmp/`, `packaging/` and `scripts/`
carry no files.

**`.gitignore` audit.** The Phase F gap was still open — the
history database's actual extension was not covered. Added at this
review: `*.db`, `*.db-wal`, `*.db-shm`, `.env`, `.env.*`, `*.log`,
`*.whl`, `*.tar.gz`, `*.idsig`, `*.jar`, `.venv*/`. Already covered:
venvs, `dist/`, `build/`, `*.apk`, egg-info, keystores and signing
material (`*.keystore`, `*.jks`, `*.pem`, `keystore-password*.txt`).

**Secrets scan.** Grep of the publish set for private-key material,
GitHub/AWS/Telegram token patterns, password/secret assignments,
personal email addresses, absolute home paths, the user's server
IPs and Telegram ID: no hits. The only 64-hex strings in the tree
are public values — SHA-256 hashes of built packages and the APK
signing certificate's public fingerprint (`docs/qa/PHASE_F_AUDIT.md`,
this log). Noted, not blocking: the Android `build.sh`/`test.sh`
and README reference the local build environment by `$HOME`-relative
paths (toolchain under `~/workspace/tools/`, release keystore
directory `~/workspace/netscope-release-key/` — path only; the
keystore and its password file are outside the repository and are
not published).

**Documentation accuracy fixes (platform support / install /
status only).**

- `README.md` — the Status section still described every platform
  as planned. Rewritten to match the platform matrix: Linux
  supported (tested on Linux; desktop offscreen + fresh-venv),
  Windows unverified, macOS documented-only/unverified, Android
  implemented and JVM-tested but not device-tested (not listed as
  supported), iOS/ChromeOS/FreeBSD documented-only. The layout
  block no longer lists the empty `packaging/` and `scripts/`
  directories, and the CLI section no longer says the desktop
  "will" use the core.
- `apps/desktop/README.md` — the Current status section still
  presented the two startup blockers as open and the build as "not
  yet verified as launchable". Rewritten: both defects fixed and
  re-verified the same day (20 desktop tests, real launch, all 11
  pages, fresh-venv icons), offscreen-only caveat kept.
- `shared/core/README.md` — "runs on Windows, Linux, macOS and
  Termux" qualified: portable by design, executed and tested on
  Linux only, other platforms unverified.
- `docs/architecture/ARCHITECTURE.md` — the desktop line now reads
  "Linux verified; Windows from the same codebase, unverified".

Verified accurate without changes: `LICENSE` (MIT, "NetScope
contributors", 2026), `CONTRIBUTING.md`, `SECURITY.md`,
`CODE_OF_CONDUCT.md`, `ARCHITECTURE_DECISIONS.md`, the CLI and
Android READMEs (install steps match the packages and entry points;
the Android README already states the not-device-tested status and
the keystore-outside-repo rule), `docs/design/DESIGN_SYSTEM.md`,
`docs/qa/PHASE_F_AUDIT.md`, `ROADMAP.md` (forward-looking goals,
not claims). Minor staleness noted, not rewritten: `CHANGELOG.md`'s
Unreleased section lists only the foundation, not the implemented
applications.

**Sanity.** The three suites were re-run on the exact tree to be
published: core 87 passed, CLI 24 passed, desktop 20 passed
(offscreen Qt environment) — 131 total, matching the baseline.

**Publish manifest.** `docs/qa/PUBLISH_MANIFEST.md` lists the 112
files by directory and the exclusion table; it drives the browser
upload step. Recommendation: GO for the browser publication step,
with the standing conditions — no tag, no Release, no integrations
— until separately approved.

## 2026-11-22 — Phase F follow-up: F-01 and F-02 fixed

The user approved fixing the two medium Phase F findings only,
under the same security conditions as the earlier phases (no
bypassing of security mechanisms, normal user permissions, no
system or network configuration changes, no external transmission,
stop immediately if a security check blocks). Phase G remains not
authorized and was not started. No security check blocked this
work. All GUI evidence is offscreen.

**F-01 — spacing on the design scale.** The design system's 4 px
scale now has a single programmatic source:
`theme.design_spacing()` derives the semantic values from
`assets/branding/tokens.json` — page margin 16, content margin 8,
item spacing 8, control padding 4 px vertical / 12 px horizontal —
and `pages/common.py` gained `apply_design_spacing()`, which
`MainWindow` applies to every page after construction (and the
History report dialog applies to itself). Mapping, chosen to keep
the current visual density: Qt default margins 9 → 8 for nested
layouts (page top-level margins 9 → 16, the audit's recommended
page inset), spacing 6 → 8. The off-scale stylesheet paddings the
audit named are generated from the same tokens: button padding
6/14 px → 4/12 px, input and table-header padding 5/8 px → 4/8 px.
No layout structure changed — only the numbers. A programmatic
re-audit walks all 114 layouts in the constructed window (the 11
pages' own layouts plus group-box, scroll-content and control-row
layouts beneath them): every margin and spacing is on the scale.

**F-02 — brand assets in the wheel.** The desktop loads exactly one
brand asset, `app-icon.svg` (window icon in `app.py`, About-page
logo in `pages/data_pages.py`). A copy now lives in the new
`netscope_desktop.assets` subpackage, shipped via
`[tool.setuptools.package-data]` in `apps/desktop/pyproject.toml`,
and `paths.brand_asset_path()` resolves it: the packaged copy first
(`importlib.resources`), the repository checkout's
`assets/branding` as fallback. Both call sites use the resolver.

**Regression tests** (`apps/desktop/tests/test_phase_f_fixes.py`,
6 new): every page layout's margins/spacings are on the scale;
stylesheet paddings are on the scale; the resolver returns the
packaged icon and `None` for a missing name; the icon is a valid
SVG; the About page renders a non-null 72×72 icon pixmap; a wheel
built from the tree contains `netscope_desktop/assets/app-icon.svg`
byte-identical to the canonical asset. Test counts (exact):
desktop **20 passed** (14 baseline + 6 new), core **87 passed**,
CLI **24 passed** — 131 total.

**Packaging re-verified.** The desktop wheel and sdist were
rebuilt into `dist/` (wheel 34,800 bytes, 23 files — was 21 —
SHA-256 `055e5e8f…`; sdist 35,133 bytes, SHA-256 `8b6e1fa3…`;
the SVG is in both). Core and CLI artefacts are unchanged. A
completely fresh venv installed the three wheels (`pip check`
clean, PySide6 6.12.0 from PyPI); from site-packages the installed
desktop resolved its icon inside the venv, set a non-null window
icon, constructed the main window, navigated all 11 pages,
rendered the About icon, kept every page layout on the spacing
scale, and transitioned dark → light → dark with the exact token
backgrounds; the installed `netscope-desktop` entry point stayed
in its event loop, and `netscope version` / `netscope status`
exited 0. Uninstall removed all three packages, their entry points
and their imports; the scratch venv was deleted. Windows/macOS
status claims are unchanged (not verified).

## 2026-11-22 — Phase F: Anti-slop quality audit + packaging

The user approved Phase F only (no GitHub publication, no public
release, no Phase G), under the same security conditions as the
earlier phases. No security check blocked this work. The full
report is `docs/qa/PHASE_F_AUDIT.md`.

**Audit.** All 11 desktop pages were audited against
`docs/design/DESIGN_SYSTEM.md` and `assets/branding/tokens.json`
by source inspection, programmatic scans and a scripted offscreen
Qt session (renders of every page with an empty store, a
button-wiring check, layout metrics, guard-path checks). Headline:
**no critical or high findings** — no gradients, no glassmorphism,
no emoji/symbol icons (programmatic scan: zero), zero non-token
colours in any of the four codebases, no fake or sample data
(every displayed value traces to a real probe; test doubles exist
only in tests), no dead controls (0 unwired buttons), and honest
empty states throughout. Findings: 2 medium — (F-01) page layout
margins/spacing are Qt defaults (9 px / 6 px), not the design
system's 4 px-base scale; (F-02) brand assets are not shipped in
the desktop wheel, so installed copies get no window icon and a
blank About icon. Plus 7 low (off-scale 13 px/9 pt type, the
unimplemented Lucide baseline, desktop/Android disagreeing on the
UNKNOWN verdict colour, the `netscope-desktop[gui]` install hint
naming a nonexistent extra, `.gitignore` missing `*.db`, local
data files relying on umask permissions, Android dark-theme-only)
and 4 info items — each with file evidence and a recommendation
in the audit document. No UI findings were fixed in this phase
(audit only, per instructions).

**Privacy/security.** No telemetry or analytics code exists; no
logging module is used; outbound traffic is exclusively
user-initiated diagnostics (DNS to the system + configured public
resolvers, probes to the user-specified host, speed test to the
configured endpoints with a zero-byte upload body). HTTP response
headers are redacted for credential-bearing names before storage
(verified in `httpprobe`). Storage is the documented SQLite
history (retention-pruned) and settings JSON on desktop, and
app-private SQLite + SharedPreferences on Android. Secret scans
found no credentials in the tree.

**Packaging (Linux) — verified.** Wheels and sdists for
netscope-core 0.1.0, netscope-cli 0.1.0 and netscope-desktop 0.2.0
were built into `dist/` from **unmodified** packaging metadata
(no metadata fix was needed; PyInstaller is not a route of this
repository — no spec exists — so no binary was built). The wheels
were installed into a fresh venv (`pip check` clean), the
installed `netscope version` and `netscope status` exited 0, the
installed desktop entry point launched and its main window
constructed/shown/closed from site-packages with all 11 pages,
and uninstall removed the packages, entry points and imports
cleanly. SHA-256 hashes for all six artefacts are recorded in the
audit document. The Android APK was re-verified only (apksigner +
badging: `com.netscope.app` 0.4.0, minSdk 26, targetSdk 34,
exactly the two declared permissions). **Windows and macOS
packaging is NOT VERIFIED** — no such environment exists here;
the pure-Python wheels and console-script entry points are
portable in principle, but nothing was built or run for those
platforms and no support is claimed.

**Tests re-run:** core 87, CLI 24, desktop 14 — 125 passed,
matching the Phase C/D baselines (desktop requires this sandbox's
Qt library path for libEGL; an environment property, not a
packaging defect).

## 2026-11-22 — Phase C: Desktop fixes and follow-up verification

The user approved fixing the two defects from the Phase C
verification entry below, bounded to those defects, under the same
security conditions (no bypassing of security mechanisms, normal user
permissions, no system or network configuration changes, no external
transmission, stop immediately if a security check blocks). No
security check blocked this work.

Fixes:

1. **History store deadlock** (`history.py`). The audit of every lock
   user in the file found exactly two nested call paths — `clear()`
   and `prune()` calling the public `count()` while holding the lock;
   all other methods acquire the lock once and call no other store
   method. Two candidate fixes were evaluated. An `RLock` would fix
   the symptom with a one-word change, but it makes lock ownership
   implicit: any future nested public call would silently re-enter,
   including inside the `sqlite3` transaction scopes some methods
   hold. The chosen fix keeps the plain non-reentrant
   `threading.Lock` and restructures instead: the row count now lives
   in a private `_count_unlocked()` helper that may only be called
   with the lock held, `count()` is a thin locking wrapper over it,
   and `clear()`/`prune()` call the helper directly. The invariant —
   every public method acquires the lock exactly once, helpers never
   acquire it — is stated in the module docstring, and a future
   nesting mistake deadlocks loudly in the watchdog tests rather than
   passing silently. In `prune()` the helper preserves the original
   semantics: the count is read inside the same transaction, after
   the age-based delete, so it sees the post-delete row count.
2. **About page version attribute** (`pages/data_pages.py`):
   `netscope_core.VERSION` → `netscope_core.__version__`, the name
   the core package actually exports. It was the only misuse in the
   package (verified by search).

Regression tests added to `apps/desktop/tests/` (14 tests total now):

- `test_history_prune_on_startup_path_completes` — mirrors
  `app.main`: a fresh store pruned with the default `Settings`
  values, run under the existing subprocess watchdog so a regression
  fails in 10 s instead of hanging the suite. The pre-existing
  watchdog tests for `clear()` and `prune()` are the other deadlock
  regressions; all three now pass.
- `test_about_page_shows_core_version` — constructs `AboutPage`
  offscreen and asserts a label shows `Core {__version__}` with the
  core's real version string. `MainWindow` construction is covered
  by the pre-existing navigation test, which previously errored on
  this defect.

Test counts (exact): desktop **14 passed** (previously 9 passed,
2 failed, 1 error of 12); core regression **87 passed**; CLI
regression **24 passed**.

Follow-up verification (all offscreen; sandbox-network caveat as
before):

- **Launch.** The real entry function `netscope_desktop.app.main`
  (exactly what `.venv/bin/netscope-desktop` invokes) ran with the
  real default settings and the real default history database — the
  start-up path that previously hung in `prune()` until a 15 s
  timeout (exit 124). This time the window appeared (offscreen),
  reported 11 pages with the expected navigation labels, the theme
  stylesheet was applied, and a queued quit returned exit code 0 in
  about 3 s.
- **Navigation.** A scripted session visited all 11 pages through
  the navigation list; each became the current widget without an
  exception (Overview, Live Monitor, Diagnostics, DNS Analyzer,
  Speed Test, Route Analyzer, Interfaces, History, Reports,
  Settings, About).
- **Theme switching.** Through `MainWindow.apply_theme`:
  dark → light → dark. The applied stylesheet changed at each step,
  contains the exact token backgrounds (`#101419` dark, `#F7F9FB`
  light), and returning to dark restored the original stylesheet
  byte for byte.
- **Core integration.** The Diagnostics page ran the real engine for
  `example.com` through its own worker path; a `HostReport` returned,
  the verdict label rendered, and the run was written to SQLite
  history with matching stored JSON. The verdict in this run was
  UNKNOWN (low) — the sandbox probes returned inconsistent evidence
  that run; the same path returned OK (high) in the earlier
  page-level verification and in the CLI smoke. Sandbox verdicts
  prove the code path, not real-world measurement.
- **History full cycle.** Add (via the diagnose run), list,
  read-back and Clear-all through `HistoryPage.clear_all()` — the
  previously deadlocking path — which reported "Cleared 1 stored
  run(s)." and left the store empty.
- **PDF.** The real report from the integration run exported
  through `exports.export_report(..., "pdf", ...)`: 19,140 bytes,
  beginning with `%PDF`.

**Conclusion: Phase C is complete and verified in this
environment.** The remaining limitation is unchanged and material:
all GUI verification is offscreen — the application has still never
run on a physical display.

## 2026-11-22 — Phase E: Android app (0.4.0)

The native Android app is implemented in `apps/android/` per
ADR-002: framework Kotlin (no AndroidX), one activity with six
sections (Overview, Monitor, Diagnostics, Tools, History,
Settings), built with the manual pipeline (kotlinc + aapt2 + d8 +
zipalign + apksigner). Package `com.netscope.app`, versionName
0.4.0, versionCode 1 (new repository lineage), minSdk 26,
targetSdk 34, permissions INTERNET and ACCESS_NETWORK_STATE.

The probe and analysis layer is a port of `netscope_core`: the DNS
wire codec (now with full rdata parsing for MX/NS/TXT/SOA/PTR/SRV/
CAA and unknown types carried as hex, matching the core where the
earlier lineage skipped them), system-vs-public resolver comparison
with the poisoning and partial-NXDOMAIN flags, TCP/TLS/HTTP probes
with the block-page marker scan, the core's statistics
(`Stats.kt`: linear-interpolation percentiles, population standard
deviation, jitter as mean/max absolute successive difference), the
ten-code verdict classifier, and the troubleshooting rules with
facts, causes and recommendations separated. The design tokens are
compiled into `Tokens.kt` from `assets/branding/tokens.json`; the
reticle is drawn programmatically in the header and shipped as an
adaptive launcher icon derived from `logo-symbol.svg`. Diagnostics
runs are stored in SQLite; settings in SharedPreferences; the
monitor samples TCP latency on a Handler loop with a canvas-drawn
chart (no wake locks, no foreground service).

Route tracing needed one platform decision: `java.net` cannot set
the unicast IP TTL (there is no `StandardSocketOptions.IP_TTL` in
the desktop JDK, so the first attempt did not compile). The probe
is implemented with `android.system.Os` — socket, `IP_TTL`
setsockopt, non-blocking connect, `poll` with timeout.
`Os.getsockoptInt` is not public API, so a pending refusal is
detected by re-issuing the connect and reading its errno
(ECONNREFUSED means the destination itself answered). The trace
loop and stop-point classification are pure Kotlin ports of the
core and are unit-tested with a scripted probe; the `Os` connect
itself is Android-only code, compiled against android.jar and
excluded from the JVM tests.

Verification (build environment, 2026-11-22):

- JVM unit tests: **59 passed, 0 failed** (`apps/android/test.sh`,
  which also compiles the whole logic layer). Coverage: statistics,
  DNS fixtures incl. the new record types, all ten verdict codes,
  rules, route classification and trace loop, markers, error
  classification.
- APK: `apps/android/dist/NetScope.apk`, **860,840 bytes**,
  release-signed. `apksigner verify` reports signer DN
  `CN=NetScope, O=NetScope contributors`, certificate SHA-256
  `1e60fca28c1451784e5ae9e1431560f6bcd6f52222387ab56b07a4457681b0ff`
  (the project release key, held outside the repository).
  `aapt2 dump badging` confirms the package, versions, SDK levels
  and exactly the two declared permissions; the dex was inspected
  and contains all application classes. (d8 printed a stack trace
  while dexing the Kotlin metadata but completed; the inspected
  dex and the signature verification are the evidence relied on.)
- A copy of the APK replaces the previous lineage's file at
  `~/workspace/your_files/NetScope.apk`, as instructed.

Not verified: the app has **not been run on a device or an
emulator**. The UI has never been rendered, and runtime behaviour
(ConnectivityManager link properties, the `Os` TTL connect, SQLite
on device) rests on compilation and API review only. No security
check blocked any part of this phase.

## 2026-11-22 — Phase C: Desktop verification (after execution-risk block)

The desktop package `netscope_desktop` 0.2.0 in `apps/desktop/` was
written in the preceding build step (eleven pages over
`netscope_core`). Its combined install/import step then failed an
automated system execution-risk check; the build agent stopped with
the package installation, tests and GUI smoke all unverified, and no
desktop tests in existence.

The user approved a bounded desktop verification in writing under the
same security conditions as the CLI verification: no bypassing or
weakening of any security mechanism, normal user permissions only, no
system or network configuration changes, no external uploads, timeouts
on network operations, and an immediate stop with the exact reason if
a security check blocked execution again. No security check blocked
this verification. No production code was changed; this phase added
tests and documentation only.

Installation and imports:

- `pip show` reports `netscope-desktop 0.2.0`, an editable install
  from `apps/desktop/`, requiring `netscope-core` and `PySide6`;
  `pip check` reports "No broken requirements found"; the
  `.venv/bin/netscope-desktop` entry point is present. No reinstall
  was needed or performed.
- All 16 `netscope_desktop` modules import cleanly with
  `QT_QPA_PLATFORM=offscreen` and the VM's extracted Qt libraries on
  `LD_LIBRARY_PATH`; `compileall` over the package and tests passes.

Tests (new suite in `apps/desktop/tests/`, 12 tests):

- Desktop: **9 passed, 2 failed, 1 error** (`pytest apps/desktop/tests`).
- Regression: core **87 passed**, CLI **24 passed**.

Two defects block the phase; both are reproduced, not inferred:

1. **History store deadlock (start-up blocker).**
   `HistoryStore.clear()` and `HistoryStore.prune()` call `count()`
   while already holding the store's `threading.Lock`, which is not
   re-entrant; `count()` waits on the same lock forever. Evidence: the
   clear and prune tests each failed to return within a 10-second
   subprocess timeout, and a `faulthandler` stack from the real entry
   point shows `app.main` → `history.prune` (line 110) →
   `history.count` (line 123). Running
   `timeout 15 .venv/bin/netscope-desktop` (offscreen) created the
   default database at `~/.local/share/netscope/history.db` and then
   hung until the timeout (exit 124); no window appeared. The same
   defect would also hang History "Clear all" and Settings save,
   which call `clear()`/`prune()`.
2. **About page version attribute (main-window blocker).**
   `AboutPage` formats `netscope_core.VERSION`, but the core package
   exposes the version only as `__version__`. Constructing
   `MainWindow` directly (bypassing the start-up prune) raises
   `AttributeError: module 'netscope_core' has no attribute 'VERSION'`
   at `pages/data_pages.py:377`. This is the 1 error in the desktop
   suite, and it blocks the scripted launch/navigation check: none of
   the eleven pages could be visited through the real main window.

What was verified despite the blockers (all offscreen; the sandbox
network caveat applies — resolver answers are synthetic and outbound
UDP/53 is refused with EPERM):

- Page-level core integration: `DiagnosticsPage`, hosted in a stub
  main window, ran the real engine for `example.com` through its own
  worker path: a `HostReport` returned with verdict **OK (high)** and
  6 check results, and the run was written to the SQLite history
  (store count 1, row `example.com / OK` afterwards).
- `DNSPage` A-record lookup populated its results table; the single
  configured resolver row reports `error ([Errno 1] Operation not
  permitted)` — the sandbox's UDP/53 refusal, reported as measured.
- `MonitorPage` with an injected fake connector produced the expected
  samples and stats line, including loss accounting.
- Themes: stylesheets generated for both themes contain the exact
  token colours from `assets/branding/tokens.json` (dark background
  `#101419`, light background `#F7F9FB`) and differ from each other;
  `SettingsPage`'s theme switch updates the setting and calls the host
  window's `apply_theme("light")`. Switching through the real
  `MainWindow` remains unverified (see defect 2).
- History store: add, list, host filter, JSON/Markdown read-back and
  delete are verified against temporary databases. Clear and prune
  are blocked by defect 1.
- PDF: a real `example.com` report (verdict OK, sandbox network) was
  exported through `exports.export_report(..., "pdf", ...)`:
  18,493 bytes, beginning with `%PDF`.
- Defect scan: no `TODO`/`FIXME`/`lorem` text in the package; the
  only "placeholder" matches are Qt `setPlaceholderText` API calls.
  Statically, the sources contain 18 `QPushButton(...)` statements
  and 18 `clicked.connect` statements (the Diagnostics export row
  creates five buttons from one looped connection). A runtime
  click-through of the full main window was not possible.

**Conclusion: Phase C is implemented as code but is not complete and
not verified as launchable.** The two defects above must be fixed and
the launch, navigation, history clear/prune and theme-switch checks
re-run before the desktop can be marked verified. All verification in
this environment is offscreen; the application has never run on a
physical display.

## 2026-11-22 — Phase D: CLI verification (after execution-risk block)

The CLI package `netscope_cli` 0.1.0 in `apps/cli/` was written in the
preceding build step (commands: diagnose, dns, latency, route, speed,
interfaces, status, monitor, version; thin front end over
`netscope_core`). Its installation into the project venv succeeded
(`pip install -e apps/cli`), but the tool result then failed an
automated system execution-risk check, and the build agent was
instructed not to run, test, import, or further process the content
without the user's explicit go-ahead. The agent stopped before any
test or smoke run. A later check of the permission history found no
user-facing approval card for that event: the block was an automated
execution-risk classification, not a user denial. No verbatim warning
text beyond this description was recorded, and none is reconstructed
here.

The user then approved CLI verification in writing, with binding
security requirements: no bypassing or weakening of any security
mechanism, normal user permissions only, no system network changes,
no arbitrary downloaded scripts, no uploading of diagnostic data,
timeouts on all network operations, and an immediate stop with the
exact reason if a security check blocked execution again.

Verification performed under that approval (2026-11-22):

- Installation: `pip show` reports `netscope-cli 0.1.0` and
  `netscope-core 0.1.0`, both editable installs from this repository;
  `netscope version` prints "NetScope CLI 0.1.0 / Core engine:
  netscope-core 0.1.0", exit 0.
- Unit tests: CLI suite 24 passed, 0 failed (`pytest apps/cli/tests`);
  core regression suite 87 passed, 0 failed
  (`pytest shared/core/tests`). No code changes were needed or made.
- Smoke tests (sandbox network — its resolver answers are synthetic
  198.18.0.0/15 and outbound UDP/53 is refused with EPERM, so these
  runs verify behaviour, not real-world measurements), each under
  `timeout 120`:
  - `netscope status` — exit 0; interface summary, DNS answer via the
    system resolver, TCP 443 4/4 connected.
  - `netscope diagnose example.com` — exit 0; verdict OK (confidence:
    high), real TLS 1.3 handshake and HTTP 200 recorded; the public
    resolver comparison shows errors for 1.1.1.1/8.8.8.8/9.9.9.9
    because UDP/53 is refused in this sandbox — the tool reports this
    as measured evidence rather than guessing.
  - `netscope dns example.com` — exit 1; system resolver answered,
    direct queries to the public resolvers failed with
    "[Errno 1] Operation not permitted", as expected in this sandbox.
  - `netscope latency example.com` — exit 0; 10 TCP samples, 0.0%
    loss, full statistics printed (min/average/median/p95/max/stddev,
    jitter avg/max).

No security check blocked this verification. Phase D acceptance
criteria are met; the CLI is implemented and verified in the Linux
development environment.

## 2026-11-22 — Phase B: Shared core engine

The reference diagnostic engine now exists as the Python package
`netscope_core` in `shared/core/` (zero runtime dependencies, standard
library only, `requires-python >=3.11`). It implements the Phase A
schemas rather than inventing a parallel shape: every probe produces
layer data, the engine converts it to schema-shaped results, and
`HostReport.to_dict()` emits the report schema exactly.

Modules: `models` (schema dataclasses), `stats` (latency distribution
with linear-interpolation percentiles, population standard deviation,
successive-difference jitter as defined by the schema, packet-loss
accounting), `errors` (one socket-error classifier for all probes;
exception types first, then a combined POSIX/Winsock errno table),
`dnsprobe` (hand-rolled wire codec with proper rdata parsing for A,
AAAA, CNAME, MX, NS, TXT, SOA, PTR, SRV and CAA; system-vs-public
resolver comparison with poisoning and NXDOMAIN-inconsistency flags),
`tcpprobe`, `tlsprobe` (connect and handshake phases timed separately;
certificate subject/issuer/expiry; chain length where the runtime
exposes it), `httpprobe` (manually connected sockets give DNS/connect/
TLS/TTFB phase timings; response headers captured with credential
headers redacted; block-page marker scan including the Persian
markers), `routeprobe` (ICMP traceroute with TCP-TTL fallback, method
recorded), `speedtest` (download/upload against configurable
endpoints — Cloudflare's public endpoints are the documented default,
not the only option; cancellation via an event; transport injectable),
`interfaces` (stdlib-only inventory with limitations stated, not
papered over), `verdict` (the ten-code classifier as a pure function),
`rules` (troubleshooting findings with measured facts, possible
causes, and recommendations kept in separate fields; a captive portal
is reported only as a low-confidence suspicion), `report` (JSON,
Markdown, standalone HTML in the design tokens, CSV), and `engine`
(the single orchestration entry point).

Verification: 87 fixture tests pass (`pytest`, no network), covering
the DNS codec across record types, statistics on known series, all
ten verdict codes, fact/hypothesis separation in the rules, header
redaction, speed-test arithmetic against a scripted transport, and
`jsonschema` validation of the report and result dicts against
`shared/schemas/`. A live smoke through the engine on this sandbox
network returned verdict OK for example.com and github.com with real
TLS and HTTP measurements, and both report dicts validated; the
sandbox caveat applies — its resolver answers are synthetic
(198.18.0.0/15) and its egress is proxied, so these runs prove the
code path, not real-world measurements. Raw sockets remain denied
here, so the ICMP route path is fixture-tested only and the TCP
fallback is what runs.

Adaptations, recorded: the certificate chain length is `None` on
Python < 3.13 because `SSLSocket` exposes no chain API there (the
field is populated where `get_verified_chain` exists); the desktop
history store (ADR-005) and the CLI are not part of this phase — the
core is a library, and front-ends come next per the roadmap.

## 2026-11-22 — Phase A: Foundation

Ground-up rebuild started in `~/workspace/NetScope/` under the master
specification (v2.0). The earlier prototype line is closed; nothing was
carried over except the verdict vocabulary, which the specification's schema
work reuses.

Environment audited by running the tools, not by assumption (full results in
`PROJECT_STATUS.md`): Python 3.12.3 and pip verified; PySide6 6.12.0,
pytest, and PyInstaller resolvable through the proxy; Temurin JDK 17 and the
Kotlin 2.4.10 embeddable compiler confirmed in the local toolchain; Gradle
confirmed unusable in this VM (daemon IPC failure), which forced ADR-002;
raw sockets confirmed denied, which constrains route probing to the TCP
method in this environment; `/tmp` confirmed to be a 512 MB tmpfs that
breaks large package installs unless `TMPDIR` is redirected.

Deliverables produced:

- `PROJECT_STATUS.md` — capability audit and platform capability matrix,
  with every platform at `planned` or `documented-only`.
- `docs/architecture/ARCHITECTURE.md` and `ARCHITECTURE_DECISIONS.md` —
  layered architecture and six decision records, including two recorded
  deviations from the specification (Android without Compose, ADR-002;
  Apple platforms as documentation only, ADR-003).
- `shared/schemas/` — `diagnostic-result.schema.json` and
  `report.schema.json` (JSON Schema draft 2020-12), covering the Part 11
  result shape, the latency distribution, and the ten verdict codes.
- `assets/branding/` — original reticle mark as seven SVG files (primary,
  compact, symbol, two monochrome variants, app icon, favicon) and
  `tokens.json`. All SVGs verified as well-formed XML; all JSON verified
  parseable.
- `docs/design/DESIGN_SYSTEM.md` — dark palette exactly as specified; a
  light palette designed separately, with accent values darkened where the
  brand values failed contrast on light surfaces (measured: brand accent
  3.73 : 1 on white). All published contrast figures were computed with the
  WCAG formula during this phase.
- Repository meta: README, MIT LICENSE, CONTRIBUTING, SECURITY,
  CODE_OF_CONDUCT, CHANGELOG, `.gitignore`, GitHub issue and pull-request
  templates. Git initialised on branch `main`; no commit yet, by plan.

No application code was written in this phase. Next: Phase B, the shared
core and CLI (roadmap v0.1).
