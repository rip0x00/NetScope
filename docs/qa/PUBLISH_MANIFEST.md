# Publish Manifest — Phase G

Prepared 2026-11-22 at the Phase G pre-publication review. This is the
exact set of files to upload in the browser publication step: every
file in the repository tree that is not excluded below (the set
`.gitignore` leaves standing, verified with `git add -A -n`).
**112 files** in total, including this manifest.

## Files to publish

### Repository root — 11

```
.gitignore
ARCHITECTURE_DECISIONS.md
CHANGELOG.md
CODE_OF_CONDUCT.md
CONTRIBUTING.md
DEVELOPMENT_LOG.md
LICENSE
PROJECT_STATUS.md
README.md
ROADMAP.md
SECURITY.md
```

### .github — 3

```
.github/ISSUE_TEMPLATE/bug_report.md
.github/ISSUE_TEMPLATE/feature_request.md
.github/PULL_REQUEST_TEMPLATE.md
```

### apps/android — 25

```
apps/android/AndroidManifest.xml
apps/android/README.md
apps/android/build.sh
apps/android/test.sh
apps/android/res/drawable/ic_launcher_background.xml
apps/android/res/drawable/ic_launcher_foreground.xml
apps/android/res/mipmap-anydpi-v26/ic_launcher.xml
apps/android/src/ChartView.kt
apps/android/src/Checks.kt
apps/android/src/DnsProbe.kt
apps/android/src/DnsWire.kt
apps/android/src/HistoryDb.kt
apps/android/src/HttpProbe.kt
apps/android/src/MainActivity.kt
apps/android/src/Models.kt
apps/android/src/NetErrors.kt
apps/android/src/RouteAndroid.kt
apps/android/src/RouteProbe.kt
apps/android/src/Rules.kt
apps/android/src/Stats.kt
apps/android/src/TcpProbe.kt
apps/android/src/TlsProbe.kt
apps/android/src/Tokens.kt
apps/android/src/Verdict.kt
apps/android/tests/TestMain.kt
```

Note: `build.sh` / `test.sh` reference the project's local build
environment (`$HOME/workspace/tools/...` toolchain paths and the
release keystore directory outside the repository). They contain no
credentials; they document the manual pipeline (ADR-002) and are not
portable as-is.

### apps/cli — 8

```
apps/cli/README.md
apps/cli/pyproject.toml
apps/cli/src/netscope_cli/__init__.py
apps/cli/src/netscope_cli/__main__.py
apps/cli/src/netscope_cli/format.py
apps/cli/src/netscope_cli/main.py
apps/cli/tests/conftest.py
apps/cli/tests/test_cli.py
```

### apps/desktop — 24

```
apps/desktop/README.md
apps/desktop/pyproject.toml
apps/desktop/src/netscope_desktop/__init__.py
apps/desktop/src/netscope_desktop/app.py
apps/desktop/src/netscope_desktop/assets/__init__.py
apps/desktop/src/netscope_desktop/assets/app-icon.svg
apps/desktop/src/netscope_desktop/chart.py
apps/desktop/src/netscope_desktop/exports.py
apps/desktop/src/netscope_desktop/history.py
apps/desktop/src/netscope_desktop/main_window.py
apps/desktop/src/netscope_desktop/pages/__init__.py
apps/desktop/src/netscope_desktop/pages/common.py
apps/desktop/src/netscope_desktop/pages/core_pages.py
apps/desktop/src/netscope_desktop/pages/data_pages.py
apps/desktop/src/netscope_desktop/pages/tool_pages.py
apps/desktop/src/netscope_desktop/paths.py
apps/desktop/src/netscope_desktop/sampler.py
apps/desktop/src/netscope_desktop/settings.py
apps/desktop/src/netscope_desktop/theme.py
apps/desktop/src/netscope_desktop/workers.py
apps/desktop/tests/conftest.py
apps/desktop/tests/test_gui.py
apps/desktop/tests/test_logic.py
apps/desktop/tests/test_phase_f_fixes.py
```

### assets — 8

```
assets/branding/app-icon.svg
assets/branding/favicon.svg
assets/branding/logo-compact.svg
assets/branding/logo-mono-dark.svg
assets/branding/logo-mono-light.svg
assets/branding/logo-primary.svg
assets/branding/logo-symbol.svg
assets/branding/tokens.json
```

### docs — 4

```
docs/architecture/ARCHITECTURE.md
docs/design/DESIGN_SYSTEM.md
docs/qa/PHASE_F_AUDIT.md
docs/qa/PUBLISH_MANIFEST.md
```

### shared — 29

```
shared/core/README.md
shared/core/pyproject.toml
shared/core/src/netscope_core/__init__.py
shared/core/src/netscope_core/dnsprobe.py
shared/core/src/netscope_core/engine.py
shared/core/src/netscope_core/errors.py
shared/core/src/netscope_core/httpprobe.py
shared/core/src/netscope_core/interfaces.py
shared/core/src/netscope_core/models.py
shared/core/src/netscope_core/report.py
shared/core/src/netscope_core/routeprobe.py
shared/core/src/netscope_core/rules.py
shared/core/src/netscope_core/speedtest.py
shared/core/src/netscope_core/stats.py
shared/core/src/netscope_core/tcpprobe.py
shared/core/src/netscope_core/tlsprobe.py
shared/core/src/netscope_core/verdict.py
shared/core/tests/conftest.py
shared/core/tests/test_dns_wire.py
shared/core/tests/test_httpprobe.py
shared/core/tests/test_interfaces.py
shared/core/tests/test_report.py
shared/core/tests/test_route.py
shared/core/tests/test_rules.py
shared/core/tests/test_speedtest.py
shared/core/tests/test_stats.py
shared/core/tests/test_verdict.py
shared/schemas/diagnostic-result.schema.json
shared/schemas/report.schema.json
```

## Exclusions — never upload

| Exclusion | On-disk count | Reason |
|---|---|---|
| `.venv/` (project virtualenv) | 6,218 files | Local environment; never source |
| `dist/` (root) — 3 wheels + 3 sdists | 6 files | Build artifacts; releases are a separate, separately approved step |
| `apps/android/build/` (intermediate APKs, dex, jars) | part of 41 build-dir files | Build intermediates |
| `apps/android/dist/` (`NetScope.apk`, `.idsig`) | 2 files | Built binary; not part of the source publication |
| `apps/cli/build/`, `apps/desktop/build/`, `shared/core/build/` | rest of the 41 | Build output copies |
| `*.egg-info/` (cli, desktop, core) | 17 files | Packaging metadata generated at build time |
| `__pycache__/` + `*.pyc` | 54 files | Bytecode caches |
| `.pytest_cache/` (cli, desktop, core) | 14 files | Test-run caches |
| Empty directories `.tmp/`, `packaging/`, `scripts/` | 0 files | Empty; cannot be represented in an upload and carry no content |
| The release keystore and its password file | not in this tree | Live outside the repository (`~/workspace/netscope-release-key/`); never committed (also covered by `.gitignore`) |
| Local data (`*.db`, settings, history) | none present in the tree | Runtime data lives under the user's XDG dirs, not the repo; patterns added to `.gitignore` at this review |

## Review notes for the upload step

- Secrets scan of the publish set: no credentials, tokens, private
  keys, personal email addresses, absolute home paths, or personal
  infrastructure identifiers found. The only long hex strings are
  public values: SHA-256 hashes of the built packages and the APK
  signing certificate's public fingerprint, in `docs/qa/PHASE_F_AUDIT.md`
  and `DEVELOPMENT_LOG.md`.
- Platform claims in the publish set distinguish implemented /
  tested / supported: Linux supported (tested on Linux); Android
  implemented and JVM-tested, not device-tested; Windows unverified;
  macOS, iOS, ChromeOS and FreeBSD documented-only / unverified.
- Test baseline of this exact tree: core 87 + CLI 24 + desktop 20 =
  131 tests passing (2026-11-22).
