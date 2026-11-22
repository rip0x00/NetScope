# Security Policy

## Reporting a vulnerability

Report security problems privately to the maintainers through GitHub's
private vulnerability reporting on this repository (Security → Report a
vulnerability). Do not open a public issue for a vulnerability, and do not
include other users' data in a report.

Please include: the affected component and version, the platform, steps to
reproduce, and the impact as you understand it. You will get an
acknowledgement; fixes for confirmed problems are prioritised over feature
work.

## Scope notes

NetScope is a defensive diagnostic tool. The following are design
invariants, and regressions in them are treated as security issues:

- No telemetry or hidden network traffic (ADR-006).
- No collection of credentials, tokens, or private traffic content.
- Reports redact private identifiers by default before export.
- Diagnostics run only against targets the user specifies.
- Signing keys and credentials are never committed to this repository.

## Supported versions

Until the first stable release, only the latest development state is
supported. After v1.0, this section will name the supported release lines.
