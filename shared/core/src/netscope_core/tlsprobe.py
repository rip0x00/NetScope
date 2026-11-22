"""TLS handshake probing and certificate inspection.

The connect phase and the handshake phase are timed and reported
separately. A connection that is accepted at TCP level and then reset
during the handshake — after the ClientHello, which carries the server
name (SNI) — is the classic signature of SNI-based filtering, so the
phase an error occurred in is part of the result.

On success the certificate is summarised (subject, issuer, expiry)
for the TLS inspector. The peer chain length is recorded where the
runtime exposes it (``SSLSocket.get_verified_chain`` /
``get_unverified_chain``, Python 3.13+); on older runtimes it stays
``None`` rather than being guessed.
"""

from __future__ import annotations

import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from .errors import classify_socket_error


@dataclass
class TLSResult:
    hostname: str
    target: str
    port: int = 443
    ok: bool = False
    protocol: str | None = None
    cert_subject: str | None = None
    cert_issuer: str | None = None
    cert_not_after: str | None = None  # as reported by the peer, e.g. "Nov 22 12:00:00 2026 GMT"
    cert_not_after_iso: str | None = None  # RFC 3339
    cert_days_remaining: int | None = None
    chain_length: int | None = None
    connect_ms: float | None = None
    handshake_ms: float | None = None
    failed_phase: str | None = None  # "connect" | "handshake"
    error_kind: str | None = None  # reset | timeout | refused | unreachable | certificate | protocol | ...
    error: str | None = None


def _format_rdn(rdn_sequence) -> str | None:
    """Flatten a getpeercert() subject/issuer structure to 'CN=x, O=y'."""
    if not rdn_sequence:
        return None
    parts: list[str] = []
    for rdn in rdn_sequence:
        for key, value in rdn:
            parts.append(f"{key}={value}")
    return ", ".join(parts) if parts else None


def _cert_expiry(not_after: str | None) -> tuple[str | None, int | None]:
    """Convert a getpeercert() notAfter string to (RFC 3339, days left)."""
    if not not_after:
        return None, None
    try:
        epoch = ssl.cert_time_to_seconds(not_after)
    except (ValueError, OverflowError):
        return None, None
    moment = datetime.fromtimestamp(epoch, tz=timezone.utc)
    days = (moment - datetime.now(timezone.utc)).days
    return moment.isoformat(timespec="seconds"), days


def _chain_length(tls: ssl.SSLSocket) -> int | None:
    for name in ("get_verified_chain", "get_unverified_chain"):
        getter = getattr(tls, name, None)
        if callable(getter):
            try:
                chain = getter()
            except (ssl.SSLError, OSError):
                return None
            return len(chain) if chain else None
    return None


def probe_tls(hostname: str, target: str | None = None, port: int = 443, timeout: float = 6.0) -> TLSResult:
    """Run one TLS handshake with SNI set to ``hostname``."""
    target = target or hostname
    result = TLSResult(hostname=hostname, target=target, port=port)

    start = time.perf_counter()
    try:
        raw = socket.create_connection((target, port), timeout=timeout)
    except OSError as exc:
        result.failed_phase = "connect"
        result.error_kind = classify_socket_error(exc)
        result.error = str(exc)
        return result
    result.connect_ms = (time.perf_counter() - start) * 1000.0

    context = ssl.create_default_context()
    raw.settimeout(timeout)
    start = time.perf_counter()
    try:
        tls = context.wrap_socket(raw, server_hostname=hostname)
    except ssl.SSLCertVerificationError as exc:
        raw.close()
        result.failed_phase = "handshake"
        result.error_kind = "certificate"
        result.error = str(exc)
        return result
    except ssl.SSLError as exc:
        raw.close()
        result.failed_phase = "handshake"
        result.error_kind = "protocol"
        result.error = str(exc)
        return result
    except OSError as exc:
        raw.close()
        result.failed_phase = "handshake"
        result.error_kind = classify_socket_error(exc)
        result.error = str(exc)
        return result
    result.handshake_ms = (time.perf_counter() - start) * 1000.0

    cert = tls.getpeercert()
    result.protocol = tls.version()
    result.cert_subject = _format_rdn(cert.get("subject"))
    result.cert_issuer = _format_rdn(cert.get("issuer"))
    result.cert_not_after = cert.get("notAfter")
    result.cert_not_after_iso, result.cert_days_remaining = _cert_expiry(result.cert_not_after)
    result.chain_length = _chain_length(tls)
    result.ok = True
    tls.close()
    return result
