"""Data model: schema-shaped results and the per-host report aggregate.

The dataclasses in this module mirror
``shared/schemas/diagnostic-result.schema.json`` and
``shared/schemas/report.schema.json`` field for field. Their
``to_dict()`` output is what every exporter and every other platform
implementation must match; the test suite validates it against the
schemas with ``jsonschema``.

Layer-specific probe data (DNS answers, TCP attempts, certificates,
HTTP responses, route hops) lives in the probe modules. ``HostReport``
aggregates those objects with the schema-shaped results derived from
them, the session verdict, and the troubleshooting findings.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .stats import LatencyStats

if TYPE_CHECKING:  # type-only: probe modules import this module, not the reverse
    from .dnsprobe import DNSReport
    from .httpprobe import HTTPResult
    from .routeprobe import RouteResult
    from .rules import Finding
    from .tcpprobe import TCPResult
    from .tlsprobe import TLSResult
    from .verdict import Verdict

VERSION = "0.1.0"
SCHEMA_VERSION = "1.0"


def utc_now_iso() -> str:
    """Current time as an RFC 3339 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def detect_platform_os() -> str:
    """Map the running platform to the report schema's OS vocabulary."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("freebsd"):
        return "freebsd"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


@dataclass
class Target:
    host: str
    port: int | None = None
    url: str | None = None

    def to_dict(self) -> dict:
        out: dict = {"host": self.host}
        if self.port is not None:
            out["port"] = self.port
        if self.url is not None:
            out["url"] = self.url
        return out


@dataclass
class ProbeError:
    """A structured error in the schema's vocabulary.

    ``kind`` is one of the schema's error kinds (``dns_failure``,
    ``connection_refused``, ``connection_reset``, ``timeout``,
    ``tls_failure``, ``network_unreachable``, ``permission_denied``,
    ``unknown``). Probes record internal kinds; the engine converts
    them with :func:`netscope_core.errors.schema_error_kind`.
    """

    kind: str
    message: str
    code: str | None = None

    def to_dict(self) -> dict:
        out: dict = {"kind": self.kind, "message": self.message}
        if self.code is not None:
            out["code"] = self.code
        return out


@dataclass
class CertificateInfo:
    subject: str | None = None
    issuer: str | None = None
    not_after: str | None = None  # RFC 3339
    days_remaining: int | None = None

    def to_dict(self) -> dict:
        out: dict = {}
        if self.subject is not None:
            out["subject"] = self.subject
        if self.issuer is not None:
            out["issuer"] = self.issuer
        if self.not_after is not None:
            out["notAfter"] = self.not_after
        if self.days_remaining is not None:
            out["daysRemaining"] = self.days_remaining
        return out


@dataclass
class PacketStats:
    sent: int = 0
    received: int = 0

    @property
    def loss_percent(self) -> float:
        if self.sent == 0:
            return 0.0
        return 100.0 * (self.sent - self.received) / self.sent

    def to_dict(self) -> dict:
        return {
            "sent": self.sent,
            "received": self.received,
            "lossPercent": round(self.loss_percent, 3),
        }


@dataclass
class Measurement:
    """Measured values of one check; every field is optional."""

    addresses: list[str] | None = None
    resolver: str | None = None
    latency: LatencyStats | None = None
    packets: PacketStats | None = None
    bytes_received: int | None = None
    http_status: int | None = None
    redirects: int | None = None
    tls_version: str | None = None
    certificate: CertificateInfo | None = None

    def to_dict(self) -> dict:
        out: dict = {}
        if self.addresses is not None:
            out["addresses"] = list(self.addresses)
        if self.resolver is not None:
            out["resolver"] = self.resolver
        if self.latency is not None:
            out["latency"] = self.latency.to_dict()
        if self.packets is not None:
            out["packets"] = self.packets.to_dict()
        if self.bytes_received is not None:
            out["bytesReceived"] = self.bytes_received
        if self.http_status is not None:
            out["httpStatus"] = self.http_status
        if self.redirects is not None:
            out["redirects"] = self.redirects
        if self.tls_version is not None:
            out["tlsVersion"] = self.tls_version
        if self.certificate is not None:
            out["certificate"] = self.certificate.to_dict()
        return out


@dataclass
class ProbeResult:
    """One diagnostic check, in the shape of the result schema."""

    check: str  # connectivity | dns | tcp | tls | http | latency | route
    status: str  # ok | degraded | failed | blocked | timeout | error | skipped
    target: Target
    protocol: str  # dns | tcp | tls | http | https | icmp | udp | system
    duration_ms: float
    confidence: str  # high | medium | low
    explanation: str
    timestamp: str = field(default_factory=utc_now_iso)
    measurement: Measurement | None = None
    error: ProbeError | None = None
    verdict: str | None = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schemaVersion": self.schema_version,
            "check": self.check,
            "status": self.status,
            "timestamp": self.timestamp,
            "target": self.target.to_dict(),
            "protocol": self.protocol,
            "durationMs": round(float(self.duration_ms), 3),
            "measurement": self.measurement.to_dict() if self.measurement is not None else None,
            "error": self.error.to_dict() if self.error is not None else None,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "verdict": self.verdict,
        }


@dataclass
class HostReport:
    """Everything measured about one host in one session.

    ``to_dict()`` produces the report schema's shape: the session
    verdict and the recommendations aggregated from the troubleshooting
    findings.
    """

    host: str
    dns: "DNSReport"
    tcp: dict[int, "TCPResult"]
    tls: "TLSResult | None"
    http: dict[str, "HTTPResult"]
    results: list[ProbeResult]
    verdict: "Verdict"
    findings: list["Finding"] = field(default_factory=list)
    route: "RouteResult | None" = None
    generated_at: str = field(default_factory=utc_now_iso)
    platform_os: str = field(default_factory=detect_platform_os)
    platform_os_version: str | None = None
    app_surface: str | None = None

    def to_dict(self) -> dict:
        recommendations: list[str] = []
        for finding in self.findings:
            for rec in finding.recommendations:
                if rec not in recommendations:
                    recommendations.append(rec)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "tool": {"name": "NetScope", "version": VERSION},
            "generatedAt": self.generated_at,
            "platform": {
                "os": self.platform_os,
                "osVersion": self.platform_os_version,
                "appSurface": self.app_surface,
            },
            "target": {"host": self.host},
            "redacted": True,
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "verdict": self.verdict.code,
                "confidence": self.verdict.confidence,
                "explanation": self.verdict.explanation,
                "recommendations": recommendations,
            },
        }
