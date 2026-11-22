"""NetScope command-line interface.

A thin front end over :mod:`netscope_core`: argument parsing lives
here, every measurement lives in the core. Exit codes: 0 when the
command's check passed, 1 when it ran and did not pass, 2 on usage or
target errors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from netscope_core import __version__ as CORE_VERSION
from netscope_core import engine
from netscope_core.dnsprobe import lookup, probe_dns
from netscope_core.interfaces import list_interfaces
from netscope_core.report import render_csv, render_html, render_json, render_markdown
from netscope_core.routeprobe import probe_route
from netscope_core.speedtest import SpeedConfig, run_speed_test
from netscope_core.tcpprobe import probe_tcp

from . import __version__
from .format import fmt_ms, format_host_report, format_route, stats_lines

DNS_TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR", "SRV", "CAA"]
_REPORT_RENDERERS = {
    ".md": render_markdown,
    ".html": render_html,
    ".json": render_json,
    ".csv": render_csv,
}


def _ensure_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _use_color(args: argparse.Namespace) -> bool:
    if getattr(args, "no_color", False) or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def parse_host(raw: str) -> str:
    """Reduce a URL or host[:port][/path] argument to a bare hostname."""
    raw = raw.strip()
    if "://" in raw:
        host = urlsplit(raw).hostname or ""
    else:
        host = raw.split("/")[0].split(":")[0]
    return host.rstrip(".")


def _host_or_error(parser: argparse.ArgumentParser, raw: str) -> str:
    host = parse_host(raw)
    if not host:
        parser.error(f"could not parse a host from {raw!r}")
    return host


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_version(args: argparse.Namespace) -> int:
    print(f"NetScope CLI {__version__}")
    print(f"Core engine: netscope-core {CORE_VERSION}")
    return 0


def cmd_diagnose(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    host = _host_or_error(parser, args.host)
    report = engine.run_host_check(host, app_surface="cli")
    if args.json:
        print(render_json(report))
    else:
        print(format_host_report(report, color=_use_color(args)))
    if args.report:
        renderer = _REPORT_RENDERERS.get(Path(args.report).suffix.lower())
        if renderer is None:
            print(
                "error: report path must end in .md, .html, .json or .csv",
                file=sys.stderr,
            )
            return 2
        try:
            Path(args.report).write_text(renderer(report), encoding="utf-8")
        except OSError as exc:
            print(f"error: could not write report: {exc}", file=sys.stderr)
            return 2
        print(f"Report written to {args.report}", file=sys.stderr)
    return 0 if report.verdict.code == "OK" else 1


def cmd_dns(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    host = _host_or_error(parser, args.host)
    resolver = args.resolver or "1.1.1.1"
    result = lookup(host, args.type, resolver=resolver)
    if args.json:
        print(json.dumps(
            {
                "name": result.name,
                "type": result.qtype,
                "resolver": result.resolver,
                "status": result.status,
                "latencyMs": result.latency_ms,
                "records": [asdict(r) for r in result.records],
                "error": result.error,
            },
            indent=2,
        ))
        return 0 if result.status == "ok" else 1

    print(f"DNS lookup — {host} {args.type}")
    print("")
    status = result.status
    if result.latency_ms is not None:
        status += f", {result.latency_ms:.0f} ms"
    print(f"Resolver {result.resolver} — {status}")
    if result.records:
        width = max(len(r.name) for r in result.records)
        for record in result.records:
            print(f"  {record.name:<{width}}  {record.type:<5}  {record.value}  (TTL {record.ttl})")
    elif result.error:
        print(f"  error: {result.error}")
    else:
        print("  no records in the answer")

    if args.type in ("A", "AAAA") and not args.resolver:
        report = probe_dns(host)
        print("")
        print("Resolver comparison (address records)")
        if report.system_addresses:
            print(f"  system      {', '.join(report.system_addresses)}")
        else:
            print(f"  system      failed ({report.system_error})")
        for entry in report.resolvers:
            detail = ", ".join(entry.addresses) if entry.addresses else entry.status
            print(f"  {entry.resolver:<11} {detail}")
        if report.suspect_poisoning:
            print(
                "  The system answer shares no address with any public resolver's "
                "answer; it appears to be forged."
            )
        elif report.system_addresses and any(
            r.status == "ok" and set(r.addresses) & set(report.system_addresses)
            for r in report.resolvers
        ):
            print("  The system answer agrees with at least one public resolver.")
    return 0 if result.status == "ok" else 1


def cmd_latency(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    host = _host_or_error(parser, args.host)
    result = probe_tcp(host, args.port, attempts=args.count, timeout=args.timeout)
    stats = result.latency
    if args.json:
        print(json.dumps(
            {
                "host": host,
                "port": args.port,
                "sent": len(result.attempts),
                "received": result.successes,
                "lossPercent": round(result.loss_pct, 3),
                "dominantError": result.dominant_error,
                "latency": stats.to_dict(),
            },
            indent=2,
        ))
    else:
        print(f"Latency — {host}:{args.port} (TCP connect, {len(result.attempts)} attempts)")
        print("")
        for line in stats_lines(stats, loss_pct=result.loss_pct):
            print(line)
        if result.dominant_error:
            print(f"  errors    dominant: {result.dominant_error}")
    return 0 if result.successes else 1


def cmd_route(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    host = _host_or_error(parser, args.host)
    result = probe_route(host, max_hops=args.max_hops)
    if args.json:
        print(json.dumps(
            {
                "host": result.host,
                "destinationIp": result.destination_ip,
                "method": result.method,
                "reached": result.reached,
                "stopPoint": result.stop_point,
                "note": result.note,
                "error": result.error,
                "hops": [
                    {"ttl": h.ttl, "ip": h.ip, "rttMs": h.rtt_ms, "probesSent": h.probes_sent}
                    for h in result.hops
                ],
            },
            indent=2,
        ))
    else:
        print(format_route(result))
    if result.error:
        return 2
    return 0 if result.reached else 1


def cmd_speed(args: argparse.Namespace) -> int:
    config = SpeedConfig()
    if args.download_url:
        config.download_urls = [args.download_url]
        config.latency_host = None
    if args.upload_url:
        config.upload_url = args.upload_url
    if args.size is not None:
        config.max_download_bytes = int(args.size * 1_000_000)
        config.max_upload_bytes = int(args.size * 1_000_000)
    result = run_speed_test(config)
    if args.json:
        print(json.dumps(
            {
                "downloadMbps": result.download_mbps,
                "uploadMbps": result.upload_mbps,
                "bytesDownloaded": result.bytes_downloaded,
                "bytesUploaded": result.bytes_uploaded,
                "downloadEndpoint": result.download_endpoint,
                "uploadEndpoint": result.upload_endpoint,
                "idleLatency": result.idle_latency.to_dict() if result.idle_latency else None,
                "loadedLatency": result.loaded_latency.to_dict() if result.loaded_latency else None,
                "cancelled": result.cancelled,
                "errors": result.errors,
            },
            indent=2,
        ))
    else:
        print("Speed test")
        print(f"  download endpoint   {result.download_endpoint}")
        print(f"  upload endpoint     {result.upload_endpoint}")
        print("")
        if result.download_mbps is not None:
            print(f"  download   {result.download_mbps:.2f} Mbps ({result.bytes_downloaded} bytes)")
        else:
            print("  download   not measured")
        if result.upload_mbps is not None:
            print(f"  upload     {result.upload_mbps:.2f} Mbps ({result.bytes_uploaded} bytes)")
        else:
            print("  upload     not measured")
        if result.idle_latency and result.idle_latency.count:
            print(f"  idle latency     avg {fmt_ms(result.idle_latency.avg)}")
        if result.loaded_latency and result.loaded_latency.count:
            print(f"  loaded latency   avg {fmt_ms(result.loaded_latency.avg)} (during download)")
        for error in result.errors:
            print(f"  error: {error}")
        if result.cancelled:
            print("  cancelled before completion")
    measured = result.download_mbps is not None or result.upload_mbps is not None
    return 0 if measured else 1


def cmd_interfaces(args: argparse.Namespace) -> int:
    inventory = list_interfaces()
    if args.json:
        print(json.dumps(asdict(inventory), indent=2))
        return 0
    print(f"Hostname          {inventory.hostname}")
    print(f"Outbound IPv4     {inventory.outbound_ipv4 or 'unknown'}")
    print(f"Default gateway   {inventory.default_gateway or 'unknown'}")
    addresses = ", ".join(inventory.local_addresses) or "unknown"
    print(f"Local addresses   {addresses}")
    print("")
    print("Interfaces")
    if inventory.interfaces:
        width = max(len(i.name) for i in inventory.interfaces)
        for iface in inventory.interfaces:
            loopback = "loopback" if iface.is_loopback else ""
            iface_addresses = ", ".join(iface.addresses)
            print(f"  {iface.index!s:>3}  {iface.name:<{width}}  {loopback:<8}  {iface_addresses}")
    else:
        print("  none enumerated on this platform")
    if inventory.notes:
        print("")
        print("Notes")
        for note in inventory.notes:
            print(f"  - {note}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    inventory = list_interfaces()
    host = args.host
    dns = probe_dns(host, timeout=3.0)
    target = dns.resolved_addresses[0] if dns.resolved_addresses else host
    tcp = probe_tcp(target, 443, attempts=4, timeout=3.0)
    if args.json:
        print(json.dumps(
            {
                "hostname": inventory.hostname,
                "interfaces": len(inventory.interfaces),
                "outboundIpv4": inventory.outbound_ipv4,
                "defaultGateway": inventory.default_gateway,
                "referenceHost": host,
                "resolvedAddresses": dns.resolved_addresses,
                "dnsLatencyMs": dns.system_latency_ms,
                "tcp443": {
                    "attempts": len(tcp.attempts),
                    "successes": tcp.successes,
                    "lossPercent": round(tcp.loss_pct, 3),
                    "latency": tcp.latency.to_dict(),
                },
            },
            indent=2,
        ))
    else:
        print(f"Host        {inventory.hostname} · {len(inventory.interfaces)} interfaces · "
              f"outbound IPv4 {inventory.outbound_ipv4 or 'unknown'} · "
              f"gateway {inventory.default_gateway or 'unknown'}")
        if dns.resolved_addresses:
            print(f"DNS         {host} → {', '.join(dns.resolved_addresses)} "
                  f"({fmt_ms(dns.system_latency_ms, 0)})")
        else:
            print(f"DNS         {host} did not resolve ({dns.system_error or 'no answer'})")
        if tcp.successes:
            print(f"TCP 443     {tcp.successes}/{len(tcp.attempts)} connected, "
                  f"avg {fmt_ms(tcp.avg_latency_ms, 0)}, loss {tcp.loss_pct:.0f}%")
        else:
            print(f"TCP 443     0/{len(tcp.attempts)} connected "
                  f"(dominant error: {tcp.dominant_error})")
    return 0 if dns.resolved_addresses and tcp.successes else 1


def _tcp_sample(host: str, port: int, timeout: float) -> float | None:
    result = probe_tcp(host, port, attempts=1, timeout=timeout)
    if result.successes and result.attempts[0].latency_ms is not None:
        return result.attempts[0].latency_ms
    return None


def monitor_loop(
    host: str,
    *,
    port: int = 443,
    interval: float = 2.0,
    duration: float = 60.0,
    sampler=None,
    emit=print,
    sleep=time.sleep,
    now=time.monotonic,
) -> tuple[int, int]:
    """Sample latency until ``duration`` seconds have passed.

    Returns (sent, received). ``sampler`` returns a latency in ms or
    None for a failed sample; sampler, emit, sleep and the clock are
    injectable so the loop can be tested without a network or real
    waiting.
    """
    if sampler is None:
        timeout = max(1.0, min(4.0, interval))
        sampler = lambda: _tcp_sample(host, port, timeout)  # noqa: E731
    start = now()
    sent = received = 0
    while True:
        value = sampler()
        sent += 1
        if value is not None:
            received += 1
        loss_pct = 100.0 * (sent - received) / sent
        stamp = datetime.now().strftime("%H:%M:%S")
        if value is None:
            emit(f"{stamp}  timeout        loss {loss_pct:.0f}%")
        else:
            emit(f"{stamp}  {value:>7.1f} ms     loss {loss_pct:.0f}%")
        if now() - start >= duration:
            break
        sleep(interval)
    return sent, received


def cmd_monitor(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    host = _host_or_error(parser, args.host)
    print(
        f"Monitoring {host}:{args.port} every {args.interval:g}s "
        f"for {args.duration:g}s — Ctrl+C to stop"
    )
    try:
        sent, received = monitor_loop(
            host, port=args.port, interval=args.interval, duration=args.duration
        )
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    loss = 100.0 * (sent - received) / sent if sent else 0.0
    print(f"Done: {received}/{sent} samples answered, loss {loss:.0f}%")
    return 0 if received else 1


# ---------------------------------------------------------------------------
# Parser and entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="print machine-readable JSON")
    common.add_argument(
        "--no-color", action="store_true", help="disable colour in text output"
    )

    parser = argparse.ArgumentParser(
        prog="netscope",
        description="NetScope network diagnostics. Every command measures "
        "with the shared core engine and reports what it measured.",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    p = sub.add_parser("diagnose", parents=[common],
                       help="full layered check of one host (DNS, TCP, TLS, HTTP)")
    p.add_argument("host", help="hostname or URL to check")
    p.add_argument("--report", metavar="PATH",
                   help="also write a report file; format from the extension "
                        "(.md, .html, .json, .csv)")

    p = sub.add_parser("dns", parents=[common], help="DNS record lookup and resolver comparison")
    p.add_argument("host", help="name to look up")
    p.add_argument("--type", default="A", choices=DNS_TYPES, help="record type (default: A)")
    p.add_argument("--resolver", metavar="IP",
                   help="resolver to query (default: 1.1.1.1; address lookups also "
                        "compare the system resolver with public resolvers)")

    p = sub.add_parser("latency", parents=[common],
                       help="repeated TCP connects with full latency statistics")
    p.add_argument("host", help="host to connect to")
    p.add_argument("--count", type=int, default=10, help="number of attempts (default: 10)")
    p.add_argument("--port", type=int, default=443, help="TCP port (default: 443)")
    p.add_argument("--timeout", type=float, default=4.0,
                   help="per-attempt timeout in seconds (default: 4)")

    p = sub.add_parser("route", parents=[common], help="trace the route to a host")
    p.add_argument("host", help="host to trace to")
    p.add_argument("--max-hops", type=int, default=30, help="maximum TTL (default: 30)")

    p = sub.add_parser("speed", parents=[common],
                       help="download/upload speed test (consumes data: up to the "
                            "configured byte budget per direction)")
    p.add_argument("--download-url", metavar="URL", help="download endpoint")
    p.add_argument("--upload-url", metavar="URL", help="upload endpoint")
    p.add_argument("--size", type=float, metavar="MB",
                   help="per-direction byte budget in megabytes")

    sub.add_parser("interfaces", parents=[common], help="local network interface inventory")

    p = sub.add_parser("status", parents=[common],
                       help="quick local status: interfaces, DNS and one TCP sample set")
    p.add_argument("--host", default="example.com",
                   help="reference host for the DNS/TCP checks (default: example.com)")

    p = sub.add_parser("monitor", parents=[common],
                       help="sample TCP latency repeatedly until the duration ends")
    p.add_argument("host", help="host to sample")
    p.add_argument("--port", type=int, default=443, help="TCP port (default: 443)")
    p.add_argument("--interval", type=float, default=2.0,
                   help="seconds between samples (default: 2)")
    p.add_argument("--duration", type=float, default=60.0,
                   help="total seconds to monitor (default: 60)")

    sub.add_parser("version", parents=[common], help="print the NetScope version")
    return parser


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command", None)
    if command is None:
        parser.print_help()
        return 2
    if command == "version":
        return cmd_version(args)
    if command == "diagnose":
        return cmd_diagnose(args, parser)
    if command == "dns":
        return cmd_dns(args, parser)
    if command == "latency":
        return cmd_latency(args, parser)
    if command == "route":
        return cmd_route(args, parser)
    if command == "speed":
        return cmd_speed(args)
    if command == "interfaces":
        return cmd_interfaces(args)
    if command == "status":
        return cmd_status(args)
    if command == "monitor":
        return cmd_monitor(args, parser)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
