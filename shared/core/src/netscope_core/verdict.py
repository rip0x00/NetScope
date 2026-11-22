"""The verdict classifier.

``classify`` is a pure function of the probe results: it walks the
layers in the order a connection is actually built (DNS, TCP, TLS,
HTTP) and returns the first layer that explains the failure, with a
plain-language explanation and a confidence level. Keeping it pure
makes the classification rules unit-testable without any network.
"""

from __future__ import annotations

from dataclasses import dataclass

from .dnsprobe import DNSReport
from .httpprobe import HTTPResult
from .tcpprobe import TCPResult
from .tlsprobe import TLSResult

OK = "OK"
DNS_POISONED = "DNS_POISONED"
DNS_BLOCKED = "DNS_BLOCKED"
TCP_BLOCKED = "TCP_BLOCKED"
TLS_SNI_BLOCKED = "TLS_SNI_BLOCKED"
HTTP_FILTERED = "HTTP_FILTERED"
SERVER_DOWN = "SERVER_DOWN"
NETWORK_UNREACHABLE = "NETWORK_UNREACHABLE"
SLOW_UNSTABLE = "SLOW_UNSTABLE"
UNKNOWN = "UNKNOWN"

ALL_CODES = [
    OK,
    DNS_POISONED,
    DNS_BLOCKED,
    TCP_BLOCKED,
    TLS_SNI_BLOCKED,
    HTTP_FILTERED,
    SERVER_DOWN,
    NETWORK_UNREACHABLE,
    SLOW_UNSTABLE,
    UNKNOWN,
]


@dataclass
class Verdict:
    code: str
    explanation: str
    confidence: str  # "high" | "medium" | "low"


def classify(
    dns: DNSReport,
    tcp: dict[int, TCPResult],
    tls: TLSResult | None,
    http: dict[str, HTTPResult],
) -> Verdict:
    # ---- DNS layer -------------------------------------------------------
    if dns.suspect_poisoning:
        return Verdict(
            DNS_POISONED,
            "Your resolver returns addresses that no public resolver returns. "
            "The DNS answer has likely been forged or hijacked on this network.",
            "high",
        )

    system_ok = bool(dns.system_addresses)
    public_ok = any(r.status == "ok" and r.addresses for r in dns.resolvers)
    if not system_ok:
        if public_ok:
            return Verdict(
                DNS_BLOCKED,
                "Your normal (system) resolver cannot resolve this name, but "
                "public resolvers can. DNS is being blocked or filtered locally.",
                "high",
            )
        statuses = [r.status for r in dns.resolvers]
        if statuses and all(s == "nxdomain" for s in statuses):
            return Verdict(
                DNS_BLOCKED,
                "Every resolver says this name does not exist (NXDOMAIN). "
                "Either the domain really does not exist, or DNS answers are being forged.",
                "medium",
            )
        if statuses and all(s in ("timeout", "error") for s in statuses):
            return Verdict(
                NETWORK_UNREACHABLE,
                "Nothing answers DNS queries at all — not the system resolver "
                "and not any public resolver. The network path itself looks broken.",
                "medium",
            )
        return Verdict(
            UNKNOWN,
            "DNS resolution failed in inconsistent ways across resolvers, "
            "so no single cause can be named.",
            "low",
        )

    # ---- TCP layer -------------------------------------------------------
    tcp443 = tcp.get(443)
    tcp80 = tcp.get(80)
    dead443 = tcp443 is not None and tcp443.successes == 0
    dead80 = tcp80 is not None and tcp80.successes == 0

    if dead443 and dead80:
        errors = {tcp443.dominant_error, tcp80.dominant_error}
        if errors == {"refused"}:
            return Verdict(
                SERVER_DOWN,
                "The host is reachable but refuses connections on ports 443 "
                "and 80. The server is most likely down or not running a web service.",
                "medium",
            )
        if "unreachable" in errors:
            return Verdict(
                NETWORK_UNREACHABLE,
                "The network reports the host as unreachable. There is no "
                "working route to it from here.",
                "high",
            )
        if errors == {"reset"}:
            return Verdict(
                TCP_BLOCKED,
                "Connections are actively reset on both web ports. Something "
                "on the path is tearing connections down.",
                "high",
            )
        if errors == {"timeout"}:
            return Verdict(
                TCP_BLOCKED,
                "Connections to both web ports time out without an answer. "
                "Packets are most likely being dropped on the path.",
                "medium",
            )
        return Verdict(
            TCP_BLOCKED,
            "Connections fail on both web ports with mixed errors "
            f"({', '.join(sorted(e for e in errors if e))}).",
            "low",
        )

    if dead443 and tcp80 is not None and tcp80.successes > 0:
        kind = tcp443.dominant_error
        if kind == "reset":
            return Verdict(
                TCP_BLOCKED,
                "Port 443 connections are reset while port 80 works. "
                "HTTPS traffic to this host appears to be blocked specifically.",
                "high",
            )
        return Verdict(
            TCP_BLOCKED,
            "Port 443 is unreachable while port 80 works, so the secure "
            "version of the site cannot be used from this network.",
            "medium",
        )

    # ---- TLS layer -------------------------------------------------------
    if tls is not None and not tls.ok and tcp443 is not None and tcp443.successes > 0:
        if tls.failed_phase == "handshake":
            if tls.error_kind == "reset":
                return Verdict(
                    TLS_SNI_BLOCKED,
                    "The TCP connection opens, but the TLS handshake is reset "
                    "as soon as the site name (SNI) is sent. This is the "
                    "signature of SNI-based filtering.",
                    "high",
                )
            if tls.error_kind == "timeout":
                return Verdict(
                    TLS_SNI_BLOCKED,
                    "The TCP connection opens, but the TLS handshake never "
                    "completes. The site name (SNI) is the only new "
                    "information at that point, so name-based filtering is likely.",
                    "medium",
                )
            if tls.error_kind == "certificate":
                return Verdict(
                    UNKNOWN,
                    "The TLS handshake fails certificate validation "
                    f"({tls.error}). The certificate may be expired or "
                    "misconfigured, or the connection may be intercepted.",
                    "medium",
                )
            return Verdict(
                UNKNOWN,
                f"The TLS handshake fails ({tls.error_kind}: {tls.error}).",
                "low",
            )

    # ---- HTTP layer ------------------------------------------------------
    https = http.get("https")
    plain = http.get("http")

    if https is not None and https.ok:
        if https.markers:
            return Verdict(
                HTTP_FILTERED,
                "The page that comes back is a block page, not the site: it "
                f"contains filtering markers ({', '.join(https.markers)}).",
                "high",
            )
        if https.status == 451:
            return Verdict(
                HTTP_FILTERED,
                "The server answers with HTTP 451 (Unavailable For Legal "
                "Reasons): the content is being withheld on this network or "
                "for this region.",
                "medium",
            )
        # The site answers over HTTPS. Remaining question: how well?
        if tcp443 is not None and tcp443.loss_pct >= 50.0:
            return Verdict(
                SLOW_UNSTABLE,
                f"The site loads, but {tcp443.loss_pct:.0f}% of connection "
                "attempts failed. The connection is unstable.",
                "medium",
            )
        if tcp443 is not None and (
            tcp443.loss_pct >= 25.0 or (tcp443.avg_latency_ms or 0) > 400.0
        ):
            return Verdict(
                SLOW_UNSTABLE,
                "The site loads, but connections are slow or intermittently "
                f"failing (loss {tcp443.loss_pct:.0f}%, average connect "
                f"{(tcp443.avg_latency_ms or 0):.0f} ms).",
                "low",
            )
        return Verdict(OK, "The site loads normally from this network.", "high")

    if plain is not None and plain.ok and plain.markers:
        return Verdict(
            HTTP_FILTERED,
            "The plain-HTTP page that comes back is a block page: it "
            f"contains filtering markers ({', '.join(plain.markers)}).",
            "medium",
        )
    if plain is not None and plain.status == 451:
        return Verdict(
            HTTP_FILTERED,
            "The server answers with HTTP 451 (Unavailable For Legal "
            "Reasons) over plain HTTP.",
            "medium",
        )

    if https is not None and not https.ok and https.error_kind == "reset" and tls is not None and tls.ok:
        return Verdict(
            HTTP_FILTERED,
            "TLS connects, but the connection is reset while the page is "
            "being fetched — filtering that inspects the request itself.",
            "medium",
        )

    if (
        https is not None and not https.ok
        and plain is not None and not plain.ok
        and tcp443 is not None and tcp443.successes > 0
    ):
        return Verdict(
            SERVER_DOWN,
            "The host accepts TCP connections but never answers HTTP or "
            "HTTPS requests. The web service itself looks down.",
            "medium",
        )

    return Verdict(
        UNKNOWN,
        "The probes did not produce a consistent explanation. The "
        "detailed results above are the evidence to work from.",
        "low",
    )
