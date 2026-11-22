# NetScope for Android

Native Android client for NetScope: layered internet diagnostics
(DNS, TCP, TLS, HTTP) with the same verdicts, statistics and
troubleshooting rules as the Python core in `shared/core/`.

- Package: `com.netscope.app`
- Version: 0.4.0 (versionCode 1, new repository lineage)
- minSdk 26, targetSdk 34
- Permissions: `INTERNET`, `ACCESS_NETWORK_STATE`
- Framework APIs only — no AndroidX, no third-party dependencies

## Why it is built this way

Gradle cannot run in the project's build environment (ADR-002), so
the app is framework Kotlin compiled with the manual pipeline
(kotlinc + aapt2 + d8 + zipalign + apksigner), and Jetpack Compose
is deferred until a Gradle-capable environment exists. The user
interface is one activity with six sections (Overview, Monitor,
Diagnostics, Tools, History, Settings) whose views are swapped in a
content frame; the bottom navigation is built from labelled text
views, not icon fonts or emoji.

The visual design applies the NetScope design system
(`docs/design/DESIGN_SYSTEM.md`, `assets/branding/tokens.json`):
the dark palette (#101419 background, #1B232C surface, #3987D8
accent, #EDF2F7 text) is compiled into `src/Tokens.kt`, and the
reticle mark is drawn programmatically in the header and shipped as
an adaptive launcher icon derived from
`assets/branding/logo-symbol.svg`.

## Behavioural parity with the core

The probe and analysis layer is a Kotlin port of `netscope_core`:

- `DnsWire.kt` — the hand-written DNS wire codec: query building,
  compression-safe name parsing, rdata for A/AAAA/CNAME/MX/NS/TXT/
  SOA/PTR/SRV/CAA, unknown types carried as hex.
- `DnsProbe.kt` — system resolver plus UDP queries to public
  resolvers, with the core's poisoning comparison (system answer
  set disjoint from every public answer set) and partial-NXDOMAIN
  flag.
- `TcpProbe.kt`, `TlsProbe.kt`, `HttpProbe.kt` — connection
  attempts, TLS handshake with separate connect/handshake timing
  and certificate details, HTTP fetch with redirect following and
  the block-page marker scan (including the Persian markers).
- `Stats.kt` — the core's statistics: percentiles by linear
  interpolation, population standard deviation, jitter as mean and
  maximum absolute successive difference, packet-loss accounting.
- `Verdict.kt` — the same ten verdict codes and explanations.
- `Rules.kt` — troubleshooting findings with facts, possible causes
  and recommendations kept separate.
- `RouteProbe.kt` + `RouteAndroid.kt` — route tracing. Android
  applications cannot open raw sockets, so there is no ICMP method;
  the trace uses TTL-limited TCP connects (the TTL is set through
  `android.system.Os`, which `java.net` cannot do) and is labelled
  a reachability trace: hop addresses stay unknown, and the
  classification says so.

Diagnostics runs save their text report to a local SQLite database
(`HistoryDb.kt`); settings persist in SharedPreferences. Nothing is
sent anywhere: the only network traffic is the probes themselves
(ADR-006, zero telemetry).

## Build

Requirements (paths are those of the project's build environment):
JDK 17, the kotlin-compiler-embeddable jars in a local Maven
repository, and Android build-tools 35.0.0 with platform android-35.

```sh
./test.sh    # JVM unit tests for the logic layer
./build.sh   # release-signed APK in dist/NetScope.apk
```

`build.sh` signs with the project release keystore, which lives
outside this repository (`~/workspace/netscope-release-key/`, with
its password in a mode-600 file there). The keystore and password
must never be committed.

## Verification status

Verified in the build environment on 2026-11-22:

- 59 JVM unit tests pass (`test.sh`): statistics on known inputs,
  DNS wire fixtures (A/AAAA/CNAME/MX/NS/TXT/SOA/PTR/SRV/CAA,
  unknown types, NXDOMAIN, compression-pointer loops, truncation),
  all ten verdict codes, troubleshooting rules, route
  classification and the trace loop, block markers, socket-error
  classification. The whole logic layer is compiled by the test
  script, so it is type-checked on a plain JVM as well.
- The APK builds and passes `apksigner verify`; `aapt2 dump
  badging` reports package `com.netscope.app`, versionName 0.4.0,
  versionCode 1, minSdk 26, targetSdk 34 and exactly the two
  declared permissions. The dex was inspected and contains all
  application classes.

Not verified:

- **The app has not been run on a device or an emulator.** The UI
  has never been rendered; behaviour that depends on the Android
  runtime (ConnectivityManager link properties, the `Os`-based TTL
  connect, SQLite on device) is verified only by compilation and
  code review against the platform APIs.
- Network behaviour on a real network is untested; the build
  environment's network is a sandbox and its results would not be
  representative anyway.
