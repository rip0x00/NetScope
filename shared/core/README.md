# netscope-core

The NetScope shared diagnostic engine, in Python. It is the reference
implementation used by the desktop application and the CLI: probes for DNS,
TCP, TLS, HTTP, route and throughput, latency statistics, error
classification, the verdict engine, troubleshooting rules, and report
renderers (JSON, Markdown, HTML, CSV).

Every result follows the shared data contract in `shared/schemas/`
(JSON Schema draft 2020-12). The package has zero runtime dependencies —
standard library only — and avoids platform-specific APIs so it can run
anywhere CPython runs. It has been executed and tested on Linux only;
Windows, macOS and other platforms are unverified.

Development:

```
python -m venv .venv
.venv/bin/pip install -e shared/core[dev]
.venv/bin/python -m pytest shared/core/tests
```
