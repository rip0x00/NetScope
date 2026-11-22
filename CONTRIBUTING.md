# Contributing

NetScope is developed in the open and contributions are welcome. This
document describes how the project works; the short version is: discuss
large changes first, keep changes focused, and never submit a measurement,
screenshot, or test result you did not actually produce.

## Before you start

- Read `docs/architecture/ARCHITECTURE.md` and `ARCHITECTURE_DECISIONS.md`.
  Changes that contradict a decision record need a new record, proposed in
  the same pull request.
- Check the platform matrix in `PROJECT_STATUS.md`. Do not describe a
  platform as supported in documentation or UI text unless it is implemented
  and tested there.
- For anything larger than a small fix, open an issue first so the approach
  can be agreed before code is written.

## Ground rules

- **No fabricated evidence.** Tests must run, screenshots must come from the
  real application, and performance figures must come from a stated method.
- **Schemas are contracts.** Changes to `shared/schemas/` follow the
  versioning rule in the architecture document and need matching fixture
  updates.
- **Privacy is an invariant.** No telemetry, no hidden network requests, no
  collection of credentials or private identifiers. See ADR-006.
- **Diagnostics are defensive.** Contributions that add scanning of third
  parties, interception, or load generation against targets the user does
  not control will not be accepted.
- **Design changes go through the design system.** New colours, spacing, or
  type styles are added to `docs/design/DESIGN_SYSTEM.md` and
  `assets/branding/tokens.json` together, or not at all.

## Workflow

1. Fork and branch from `main`.
2. Make the change, with tests where the change touches diagnostic logic.
3. Run the test suite for the parts you touched and say so in the pull
   request — including what you could not run, and why.
4. Fill in the pull request template completely.

## Commit style

Short imperative subject lines naming the area touched, for example
`core: classify TLS handshake resets separately from timeouts`. One logical
change per commit where practical.
