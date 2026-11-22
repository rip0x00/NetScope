# netscope-cli

The NetScope command-line interface. It is a thin front end over
[netscope-core](../../shared/core/README.md): all measurements are made
by the core engine, and the CLI only parses arguments, formats output,
and sets the exit code.

## Install

From the repository root, inside the repository virtual environment:

```
python -m venv .venv
.venv/bin/pip install -e shared/core
.venv/bin/pip install -e apps/cli
```

This provides the `netscope` command.

## Usage

```
netscope diagnose example.com                 full layered check (DNS, TCP, TLS, HTTP)
netscope diagnose example.com --report r.md   also write a report (.md, .html, .json, .csv)
netscope dns example.com --type MX            DNS record lookup; address lookups
                                              also compare system and public resolvers
netscope latency example.com --count 20       repeated TCP connects, full statistics
netscope route example.com                    route trace with a stop-point summary
netscope speed                                download/upload test (consumes data)
netscope interfaces                           local interface inventory
netscope status                               interfaces + DNS + one TCP sample set
netscope monitor example.com --duration 120   latency samples until the duration ends
netscope version                              print versions
```

Every command accepts `--json` for machine-readable output and
`--no-color` to disable colour (colour is also disabled automatically
when output is not a terminal).

Exit codes: 0 when the command's check passed, 1 when it ran and did
not pass, 2 on usage or target errors.
