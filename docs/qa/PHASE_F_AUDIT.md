# Phase F — Anti-Slop Quality Audit + Packaging

Date: 2026-11-22. Scope: the complete desktop UI (primary), the
shared core and CLI, and the Android app at code level (labelled as
such — the Android app has still never run on a device or emulator).
Reference documents: `docs/design/DESIGN_SYSTEM.md` (the master
specification's Part 30 anti-slop rules are embodied in the design
system and the project rules; no separate Part 30 document exists in
the repository) and `assets/branding/tokens.json`.

Method: source inspection of every desktop module; programmatic
scans (hex colours vs tokens, emoji/unicode-icon scan, gradient and
transparency scan, placeholder/sample-data scan, secret-pattern and
high-entropy scans); a scripted offscreen Qt session that rendered
all 11 pages to PNG with an empty store, checked every button's
signal wiring, read layout metrics, and exercised guard paths;
packaging builds and a fresh-venv install/launch/uninstall cycle.
All GUI evidence is **offscreen** (headless VM, no physical display)
and all network evidence describes the **sandbox** network, never
the real internet.

## Verdict in one paragraph

No critical or high-severity findings. The interface is genuinely
free of the patterns the anti-slop rules prohibit: no gradients, no
glassmorphism, no emoji or symbol icons, no fake or sample data
presented as real, no dead controls, no decorative dashboard
widgets. Every displayed number traces to a real measurement.
Findings are conformance and packaging gaps of medium and low
severity: page spacing uses Qt defaults instead of the design
system's scale, and the brand assets are not shipped in the desktop
package. (Both medium findings were fixed in an approved follow-up
round the same day; see the Status notes under F-01 and F-02.) Linux packaging (wheels + sdists) is built and verified
end-to-end; Windows and macOS packaging is **not verified** — no
such environment exists here and none is claimed.

## Findings

Severity counts: **critical 0 · high 0 · medium 2 · low 7 · info 4.**

### F-01 — Page spacing is Qt default, not the design scale · medium · design conformance

`docs/design/DESIGN_SYSTEM.md` §Spacing fixes a 4 px base scale
(4, 8, 12, 16, 24, 32, 48) and states "No other spacing values in
components." The desktop pages never set layout margins or spacing:
a runtime read of all 11 pages shows Qt defaults — contents margins
9/9/9/9 px and spacing 6 px — neither of which is on the scale. The
stylesheet adds further off-scale values (button padding 6 px,
input padding 5 px, nav item padding 8/16 px is on-scale).
Evidence: scripted offscreen session (margins/spacing per page);
`apps/desktop/src/netscope_desktop/theme.py` (stylesheet paddings);
no `setContentsMargins`/`setSpacing` call exists in any page.
Recommendation: set page layout margins/spacing from the tokens
(e.g. 16 px margins, 8 px spacing) in the `Page` base class or per
page, and bring stylesheet paddings onto the scale. Not fixed in
this phase (audit only).

**Status: FIXED** (approved follow-up round, 2026-11-22).
`theme.design_spacing()` derives the semantic values from
`tokens.json` (page margin 16, content margin 8, item spacing 8,
control padding 4/12 px); `pages/common.apply_design_spacing()`
applies them to every page layout at `MainWindow` construction
(mapping: top-level margins 9 → 16, nested margins 9 → 8, spacing
6 → 8), and the stylesheet's button/input/header paddings are
generated from the same tokens (6/14 → 4/12 px, 5/8 → 4/8 px).
Verified by regression tests and a programmatic re-audit of all
114 layouts in the constructed window: every margin and spacing
is on the scale. See `DEVELOPMENT_LOG.md`.

### F-02 — Brand assets are not shipped in the desktop package · medium · packaging

The desktop wheel contains 21 files and no brand assets.
`paths.branding_dir()` resolves `assets/branding` only inside a
repository checkout, so an installed copy gets **no window icon**
(`app.py` sets it only when the directory exists) and a **blank
About-page icon** (the `AboutPage` icon block silently renders
nothing when the SVG is missing). The theme has an identical
embedded token fallback, so colours are unaffected; the icons have
no fallback. Evidence: wheel namelist inspection;
`apps/desktop/src/netscope_desktop/paths.py`,
`apps/desktop/src/netscope_desktop/app.py`,
`apps/desktop/src/netscope_desktop/pages/data_pages.py` (AboutPage).
Recommendation: ship `assets/branding` as package data (or embed
the app icon) and resolve it from the installed package. Not fixed
in this phase.

**Status: FIXED** (approved follow-up round, 2026-11-22). The one
brand asset the desktop loads, `app-icon.svg`, now ships inside
the new `netscope_desktop.assets` subpackage via
`[tool.setuptools.package-data]`, and `paths.brand_asset_path()`
resolves the packaged copy first (`importlib.resources`) with the
repository checkout as fallback; both call sites (`app.py`,
`AboutPage`) use it. Verified: the rebuilt wheel (23 files) and
sdist contain the SVG byte-identical to the canonical asset, and
in a fresh-venv install the resolver returns the site-packages
path, the window icon is non-null, and the About page renders its
72×72 icon pixmap. See `DEVELOPMENT_LOG.md`.

### F-03 — Off-scale type sizes; Display style unused · low · typography

Stylesheet font sizes are 12/13/14/16/20 px. 13 px (mono tables and
text edits, `theme.py`) is not in the type scale (12/14/16/20/28),
and the chart's axis labels are drawn at 9 pt (`chart.py`). The
28 px Display style defined in the tokens is used nowhere (the
design system makes it conditional — "when one exists" — so this
is an observation, not a violation). Recommendation: map mono text
to the 12 px caption size or document a mono size in the scale;
draw chart labels at 12 px.

### F-04 — The prescribed Lucide icon set is not implemented · low · iconography

`DESIGN_SYSTEM.md` §Iconography names Lucide SVGs as the baseline
set. Neither desktop nor Android ships any icon set: navigation is
text-only, and the only icon in the product is the brand reticle.
This avoids every icon misuse the rules prohibit (no emoji — a
programmatic scan of all Python/Kotlin UI code found zero emoji or
unicode-symbol icons — and no mixed styles), but it deviates from
the written baseline. Recommendation: either adopt Lucide icons
paired with the existing text labels, or amend the design system
to record text-only navigation as the baseline.

### F-05 — UNKNOWN verdict colour differs between desktop and Android · low · consistency

Desktop `verdict_status()` (`pages/core_pages.py`) maps UNKNOWN to
"degraded" (the warning colour); Android `Tokens.verdictColor()`
maps UNKNOWN to `TEXT_SECONDARY` (neutral). The same verdict is
therefore coloured differently per platform. In both cases the
verdict code and explanation are also shown as text, so status is
never carried by colour alone. Recommendation: fix one mapping in
the design tokens and apply it on both platforms.

### F-06 — Install hint names a package extra that does not exist · low · correctness

`app.py`'s missing-PySide6 message advises
`pip install "netscope-desktop[gui]"`, but
`apps/desktop/pyproject.toml` defines no `gui` extra — PySide6 is a
hard dependency, so the message is also nearly unreachable.
Recommendation: add the extra (moving PySide6 into it) or change
the message to `pip install netscope-desktop`.

### F-07 — `.gitignore` does not cover `*.db` · low · privacy hygiene

`.gitignore` covers `*.sqlite3` and `*.db-journal` but not `*.db`,
while the history database is named `history.db`. It normally lives
outside the tree (`~/.local/share/netscope/`), but a portable or
test run with `NETSCOPE_DATA_DIR` pointed into the repository would
leave an unignored database containing diagnosed hosts and full
reports. Recommendation: add `*.db` to `.gitignore`.

### F-08 — Local data files rely on umask permissions · low · privacy

The history database stores every diagnosed host, resolved
addresses, and the full JSON + Markdown report of each run.
Files and directories are created with process defaults (the
database was observed as mode 0640 under this sandbox's umask
0007; under a typical umask 022 it would be 0644, readable by other
local users). No explicit restrictive permissions are applied.
Recommendation: create the data/config directories and database
with owner-only permissions on POSIX systems.

### F-09 — Android implements the dark theme only · low · parity

The design system defines dark and light themes; desktop implements
both (verified switching in Phase C and in this audit's renders).
Android `Tokens.kt` compiles in the dark palette only, on a
`Theme.Material` base. Android is recorded as "implemented, not
supported", so this is a parity gap, not a false claim.
Recommendation: add the light palette when Android theming is
revisited; keep the platform matrix wording unchanged until then.

### F-10 — Android cleartext flag is app-wide · info · security posture

`AndroidManifest.xml` sets `usesCleartextTraffic="true"`. The
plain-HTTP probe is a core feature — measuring how `http://`
targets behave is the product's purpose — and its targets are
arbitrary user-entered hosts, so domain-scoped cleartext rules
cannot express the requirement. The app has no backend and creates
no other traffic. Recorded as a deliberate, functionally required
posture, not a defect.

### F-11 — Inter-package dependency is unpinned · info · packaging

`netscope-cli` and `netscope-desktop` declare `netscope-core` with
no version constraint. Local installs must therefore supply the
core wheel alongside (as this audit's verification did). Before
any future publication, pin a compatible range so the name cannot
resolve to an unrelated package. (Publication is Phase G and was
not performed.)

### F-12 — Empty tables show default column widths · info · cosmetic

In offscreen renders, tables with no rows keep default column
widths (columns are content-sized only when data arrives, via
`resizeColumnsToContents` in `fill_table`). The empty Overview and
Diagnostics renders look sparse but show no misleading content.
Noted from the Phase F renders; no action required.

### F-13 — Audit environment lacks the brand fonts · info · environment

Neither Inter nor JetBrains Mono is installed in this environment
(`fc-list` finds neither), so every render in this audit used the
design system's documented fallbacks (system sans / monospace).
This is an environment property, not a product defect; on a user's
machine the specified families apply when installed and fall back
exactly as designed when not.

## What was verified clean (no finding)

- **Colours.** A programmatic scan of every hex value in the
  desktop, CLI, core and Android sources against `tokens.json`
  found **zero non-token colours** (25 token colours; the single
  addition is `#FFFFFF` text-on-accent, used by both themes'
  stylesheets and Android's `ON_ACCENT`). Both desktop themes
  render with the exact token palettes (offscreen renders, dark
  and light).
- **No gradients, no glassmorphism.** No gradient, backdrop, blur
  or transparency styling exists in the Python UI. Android's
  `GradientDrawable` is used only as a solid rounded-rectangle
  shape (`setColor` only; no gradient colours are ever set).
  The HTML report renderer states and follows the same rule, with
  colours taken from the tokens.
- **No fake data.** Every displayed value traces to a real probe:
  the monitor chart and statistics come from real TCP connects
  (`LatencySampler`/`default_connector`, core statistics); Overview
  shows the real local inventory (`list_interfaces`) and real
  diagnose runs; Diagnostics/DNS/Route/Interfaces pages render the
  core probes' actual results; the speed test performs real
  transfers to the endpoints shown in its own form and warns about
  data usage before running; History and Reports show only stored
  or session reports from real runs. Test doubles exist only in
  test suites. Pre-filled field values (`example.com`, the default
  resolvers) are inputs, never presented as results.
- **Empty states are honest.** With an empty store: Monitor says
  "No samples yet." (the chart draws an empty grid and its
  accessible description says the same), Speed Test says "No test
  run yet.", tables have zero rows, summaries show "—", and guard
  actions answer with plain status text ("Run a check first.",
  "Select a stored run first."). Nothing is pre-populated.
- **No dead controls.** A runtime check over every `QPushButton`
  in all 11 pages found **0 buttons without a `clicked` receiver**.
  Disabled-state logic is correct: Stop/Cancel start disabled and
  enable only while running; Run buttons disable during their
  operation.
- **Status is never colour-alone.** Verdicts and states always
  render with their code/name and an explanation in text.
- **Privacy.** There is no telemetry, analytics or phone-home code
  anywhere in the Python or Kotlin sources (the only matches for
  those terms are the statements in About/Settings asserting their
  absence, citing ADR-006). No `logging` module is used in core,
  CLI or desktop; the CLI prints only to stdout/stderr as the
  direct result of a user command. Outbound traffic is exclusively
  the diagnostics the user runs:
  - DNS queries over UDP/53 to the system resolver and the
    configured public resolvers (default 1.1.1.1, 8.8.8.8,
    9.9.9.9), disclosing the queried hostname to those resolvers;
  - TCP/TLS/HTTP probes to the user-specified host; the HTTP
    probe's stored response headers are redacted for
    `authorization`, `cookie`, `set-cookie` and
    `proxy-authorization` before they can reach a report
    (`httpprobe.redact_headers`, applied at capture);
  - route probes (ICMP where permitted, TCP-TTL fallback);
  - speed test transfers to `speed.cloudflare.com` (`__down` /
    `__up`) by default — user-editable in Settings and on the
    Speed Test page; the upload body is zero bytes, no user data;
  - monitor TCP connects to the user-specified host/port.
- **Local storage.** Desktop: `history.db` (SQLite: timestamp,
  host, verdict, confidence, TCP-443 average, full report JSON and
  Markdown) in the XDG data directory, pruned at start-up by
  retention (default 90 days / 500 runs, user-configurable);
  `settings.json` holds theme, resolvers, speed-test URLs and
  retention only. Android: app-private SQLite history and
  `MODE_PRIVATE` SharedPreferences (resolver choice, monitor
  interval, sample count). No other files are written.
- **Secrets.** Pattern and high-entropy scans found no credentials
  in the repository. The only 64-hex string is the Android signing
  certificate's SHA-256 fingerprint in `DEVELOPMENT_LOG.md` — a
  public certificate identity, not a secret. `.gitignore` excludes
  keystores, key files and password files (see F-07 for its one
  gap).

## Packaging

### Linux — built and verified

No packaging metadata changes were needed: the declared setuptools
metadata built everything as-is. PyInstaller is **not** a packaging
route of this repository (no spec file or packaging configuration
exists), so no binary was built; the legacy 1.0 line's PyInstaller
artefact is not part of the 2.0 tree.

Built into `dist/` (wheel + sdist per package):

| Artefact | Bytes | SHA-256 |
|---|---|---|
| netscope_core-0.1.0-py3-none-any.whl | 41,413 | `4e1f584f3dc3ee8c9e2589a6f8d4949cb5c66e547aa130aa862af5688eef705a` |
| netscope_core-0.1.0.tar.gz | 44,771 | `9e6bd734240b5a19ec71ba24ff37917aec32dfd94fbde83ea1cf229c19d8a316` |
| netscope_cli-0.1.0-py3-none-any.whl | 10,741 | `e4005bc686238472e8fed4d239feb4018afe8a20d9f542a7ebcd6d4d1ae35027` |
| netscope_cli-0.1.0.tar.gz | 13,208 | `18a7a91468f60cdc54403971edaecd22d51e7f0fabf106ee193d2e889a0d9792` |
| netscope_desktop-0.2.0-py3-none-any.whl | 34,800 | `055e5e8f7ca49215ad34fd0ce62a2f4430183e9c75af1f5957a6e9eb483d073d` |
| netscope_desktop-0.2.0.tar.gz | 35,133 | `8b6e1fa387c41e8f3b7714268ef02387232c9196715c4dc5bbe6fe8d5c127db5` |

(The desktop artefacts were rebuilt in the F-01/F-02 fix round —
23 files in the wheel, including the packaged brand asset — and
the fresh-venv install/launch/uninstall cycle was re-run against
them, additionally verifying the window icon, the About-page icon,
on-scale spacing and theme transitions in the installed copy.
The other four artefacts are unchanged from the original build.)

Verification cycle (fresh venv, user-level, neutral working
directory so imports resolved from site-packages):

1. `pip install` of the three wheels → PySide6 6.12.0 resolved from
   PyPI; `pip check` → "No broken requirements found".
2. `netscope version` → "NetScope CLI 0.1.0 / Core engine:
   netscope-core 0.1.0", exit 0.
3. `netscope status` → exit 0 (host inventory + probes; values are
   sandbox-network artefacts and are not real-world measurements).
4. Installed desktop: `MainWindow` constructed from site-packages,
   shown offscreen with all 11 pages, closed cleanly; the
   `netscope-desktop` entry point launched and stayed in its event
   loop (alive after 6 s, terminated by the test timeout).
5. `pip uninstall` of all three packages → entry points gone,
   `import netscope_core` fails with `ModuleNotFoundError`, no
   package directories remain. The scratch venv was then removed.

Environment note: in this sandbox, Qt needs
`LD_LIBRARY_PATH=~/workspace/.qtlibs/...` to find `libEGL.so.1`
(the desktop test suite errors at collection without it and passes
14/14 with it). That is a property of this VM's Qt libraries, not
of the packages; a normal Linux desktop provides libEGL from the
system.

### Android — signature and badging re-verified (not rebuilt)

`apksigner verify` passes for `apps/android/dist/NetScope.apk`
(860,840 bytes, SHA-256
`c6f310a7a2cea9af69c2892c9481f8f1ff1848003270b13c2510261bf1db5eab`),
signer `CN=NetScope, O=NetScope contributors`, certificate SHA-256
`1e60fca28c1451784e5ae9e1431560f6bcd6f52222387ab56b07a4457681b0ff`.
Badging: `com.netscope.app` versionCode 1 / versionName 0.4.0,
minSdk 26, targetSdk 34, and exactly the two declared permissions
(INTERNET, ACCESS_NETWORK_STATE). The app remains **not run on a
device or emulator**.

### Windows / macOS — NOT VERIFIED

No Windows or macOS environment exists here, so no package was
built, installed or executed for either platform, and no support
is claimed. Readiness assessment from the code only: the packages
are pure-Python wheels (`py3-none-any`) with console-script entry
points, and the core avoids POSIX-only APIs (platform branches
exist for OS naming; the Linux gateway reader has fallbacks;
raw-socket ICMP degrades to the TCP route method). That makes the
wheels *plausibly* installable on Windows/macOS, but plausibility
is not verification: PySide6 behaviour, fonts, and the route/ICMP
paths are untested there. Status stays `planned` (Windows) and
`documented-only` (macOS) in `PROJECT_STATUS.md`.

## Test baseline re-run for this audit

Core 87 passed · CLI 24 passed · Desktop 14 passed (with the Qt
library path above) — 125 total, matching the Phase C/D baselines.
After the F-01/F-02 fix round: Desktop 20 passed (14 + 6 new
regression tests), Core 87, CLI 24 — 131 total.

## Limitations of this audit

- All GUI evidence is offscreen rendering; layout, contrast and
  interaction on a physical display, at 200% text scaling, and
  with a screen reader remain unverified.
- Android findings are code-level only.
- Sandbox network: resolver answers are synthetic and UDP/53 to
  public resolvers is refused in this environment; no audit result
  here is a real-world network measurement.
