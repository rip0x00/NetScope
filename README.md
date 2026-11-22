# NetScope

Open-source network diagnostics for desktop and Android: layered DNS, TCP,
TLS, and HTTP checks that state what was measured, classify the likely point
of failure, and produce a report that can be shared with an ISP or a support
team.

*Understand Your Network. Take Control.*

## Status

NetScope is in early development. The foundation (architecture, data
contracts, design system), the shared diagnostic core, the CLI, the
desktop application and the Android application are implemented; see
[ROADMAP.md](ROADMAP.md) for what comes next. The current state of
every platform is tracked in [PROJECT_STATUS.md](PROJECT_STATUS.md)
and summarised below. A platform is listed as supported only after it
has been implemented and tested on that platform. Releases are
versioned at the repository level — v0.1.0 is the first ecosystem
release — while each component keeps its own independent version;
see the Versioning note in [CHANGELOG.md](CHANGELOG.md).

| Platform | Status |
|---|---|
| Linux | Supported — core, CLI and desktop implemented and tested on Linux; desktop GUI verification is offscreen-only (including a fresh-venv install/launch check) and the desktop has not yet been run on a physical display |
| Windows 10/11 | Unverified — same Python codebase as Linux; never executed on Windows |
| macOS | Documented only — unverified; no build host available |
| Android | Implemented — native Kotlin app; 59 JVM tests pass and the release-signed APK builds, but it has not been run on a device or emulator, so it is not yet listed as supported |
| iOS / iPadOS | Documented only — contracts and platform notes |
| ChromeOS, FreeBSD | Documented only — experimental, unverified |

## Repository layout

```
apps/            desktop (PySide6), CLI, and Android applications
shared/core/     Python reference diagnostic engine used by desktop and CLI
shared/schemas/  JSON Schema definitions of results and reports
assets/branding/ logo system, app icons, design tokens
docs/            architecture, design, networking, security, platform notes
```

## Command-line interface

The CLI (`apps/cli/`) is a thin front end over the shared core engine:
every command measures with the same code the desktop application
uses, and reports what it measured. Install it in a virtual environment
together with the core:

```
pip install -e shared/core
pip install -e apps/cli
```

Commands:

| Command | What it does |
|---|---|
| `netscope diagnose <host>` | Full layered check of one host (DNS, TCP, TLS, HTTP) with a verdict; `--json` for the schema-shaped report, `--report <path>` to write md/html/json/csv |
| `netscope dns <host>` | DNS record lookup and resolver comparison |
| `netscope latency <host>` | Repeated TCP connects with full latency statistics (median, p95, jitter, loss) |
| `netscope route <host>` | Trace the route to a host |
| `netscope speed` | Download/upload speed test (consumes data, up to a configured byte budget) |
| `netscope interfaces` | Local network interface inventory |
| `netscope status` | Quick local status: interfaces, DNS, and one TCP sample set |
| `netscope monitor <host>` | Sample TCP latency repeatedly until the duration ends |
| `netscope version` | Print the NetScope version |

Examples:

```
netscope diagnose example.com
netscope dns example.com --type MX
netscope latency example.com --count 20
```

Exit codes: 0 when the measured result is healthy, 1 when a check
found a problem or a measurement failed, 2 for usage errors.

## Documentation

- [Architecture](docs/architecture/ARCHITECTURE.md) and
  [architecture decisions](ARCHITECTURE_DECISIONS.md)
- [Design system](docs/design/DESIGN_SYSTEM.md)
- [Project status and platform matrix](PROJECT_STATUS.md)
- [Roadmap](ROADMAP.md) · [Development log](DEVELOPMENT_LOG.md)
- [Contributing](CONTRIBUTING.md) · [Security policy](SECURITY.md)

## Privacy

NetScope has no telemetry and makes no network requests other than the
diagnostics the user runs. Reports redact private identifiers by default.
See [ADR-006](ARCHITECTURE_DECISIONS.md).

## License

MIT. See [LICENSE](LICENSE).
