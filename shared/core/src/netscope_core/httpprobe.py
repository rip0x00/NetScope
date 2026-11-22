"""HTTP/HTTPS fetching with redirect following and block-page detection.

Filtering products and ISPs often answer blocked requests with an
ordinary-looking HTTP response — a warning page, a redirect to a
notice, or a 403/451 status. This module fetches the page the way a
browser would and scans the body for known markers of such pages.

Timing is broken into phases (DNS, TCP connect, TLS handshake, time
to first response, total) by connecting the socket manually and
handing it to ``http.client``. Response headers are captured with
credential-bearing headers redacted before they can reach a report.
"""

from __future__ import annotations

import hashlib
import http.client
import socket
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from .errors import classify_socket_error

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 NetScope/0.1"
)

# Substrings (lowercase) commonly found on ISP and filtering block
# pages. Matching is deliberately conservative: a marker is evidence,
# not proof, and the verdict layer weighs it accordingly.
BLOCK_MARKERS = [
    "access denied",
    "access to this site has been blocked",
    "this site has been blocked",
    "this website has been blocked",
    "site blocked",
    "content blocked",
    "blocked by",
    "web filtering",
    "internet filtering",
    "request blocked",
    # Persian markers, as served by Iranian ISP block pages.
    "فیلترینگ",
    "مسدود شده است",
    "دسترسی به این تارنما",
    "دسترسی به این سایت",
]

# Headers that can carry credentials or session material. Their values
# are replaced before headers are stored anywhere.
SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "proxy-authorization"}
REDACTED = "[redacted]"

_SCAN_BYTES = 65536
_READ_BYTES = 1024 * 1024
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def find_block_markers(text: str) -> list[str]:
    """Return the block-page markers present in ``text``."""
    lowered = text.lower()
    return [marker for marker in BLOCK_MARKERS if marker in lowered]


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return ``headers`` with sensitive values replaced by ``[redacted]``."""
    return {
        key: (REDACTED if key.lower() in SENSITIVE_HEADERS else value)
        for key, value in headers.items()
    }


@dataclass
class HTTPResult:
    scheme: str
    url: str
    ok: bool = False  # True when an HTTP response was received at all
    status: int | None = None
    reason: str | None = None
    final_url: str | None = None
    redirects: int = 0
    size_bytes: int = 0
    body_sha256: str | None = None
    markers: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)  # response headers, redacted
    phases: dict[str, float | None] = field(default_factory=dict)  # dns/connect/tls/ttfb/total, ms
    latency_ms: float | None = None
    error_kind: str | None = None
    error: str | None = None

    @property
    def final_host(self) -> str | None:
        if not self.final_url:
            return None
        return urlsplit(self.final_url).hostname


def _fetch_once(url: str, timeout: float) -> tuple[int, str, dict[str, str], bytes, dict[str, float | None]]:
    parts = urlsplit(url)
    host = parts.hostname
    if host is None:
        raise ValueError(f"URL has no host: {url}")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    phases: dict[str, float | None] = {"dns": None, "connect": None, "tls": None, "ttfb": None}

    start = time.perf_counter()
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    phases["dns"] = (time.perf_counter() - start) * 1000.0
    address = infos[0][4]

    start = time.perf_counter()
    raw = socket.socket(infos[0][0], socket.SOCK_STREAM)
    raw.settimeout(timeout)
    raw.connect(address)
    phases["connect"] = (time.perf_counter() - start) * 1000.0

    sock: socket.socket | ssl.SSLSocket = raw
    if parts.scheme == "https":
        start = time.perf_counter()
        sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        phases["tls"] = (time.perf_counter() - start) * 1000.0

    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    connection.sock = sock  # pre-connected: http.client skips its own connect
    try:
        start = time.perf_counter()
        connection.request(
            "GET",
            path,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "close"},
        )
        response = connection.getresponse()
        phases["ttfb"] = (time.perf_counter() - start) * 1000.0
        body = response.read(_READ_BYTES)
        header_map = {k.lower(): v for k, v in response.getheaders()}
        return response.status, response.reason, header_map, body, phases
    finally:
        connection.close()


def probe_http(hostname: str, scheme: str = "https", timeout: float = 10.0, max_redirects: int = 5) -> HTTPResult:
    """Fetch ``scheme://hostname/``, following up to ``max_redirects`` redirects."""
    url = f"{scheme}://{hostname}/"
    result = HTTPResult(scheme=scheme, url=url)
    start = time.perf_counter()
    current = url
    try:
        while True:
            status, reason, headers, body, phases = _fetch_once(current, timeout)
            if status in _REDIRECT_STATUSES and "location" in headers and result.redirects < max_redirects:
                current = urljoin(current, headers["location"])
                result.redirects += 1
                result.phases = phases
                continue
            result.ok = True
            result.status = status
            result.reason = reason
            result.final_url = current
            result.size_bytes = len(body)
            result.body_sha256 = hashlib.sha256(body).hexdigest()
            result.markers = find_block_markers(body[:_SCAN_BYTES].decode("utf-8", errors="ignore"))
            result.headers = redact_headers(headers)
            result.phases = phases
            break
    except ssl.SSLCertVerificationError as exc:
        result.error_kind = "certificate"
        result.error = str(exc)
    except ssl.SSLError as exc:
        result.error_kind = "protocol"
        result.error = str(exc)
    except http.client.HTTPException as exc:
        result.error_kind = "protocol"
        result.error = str(exc)
    except OSError as exc:
        result.error_kind = classify_socket_error(exc)
        result.error = str(exc)
    except ValueError as exc:
        result.error_kind = "error"
        result.error = str(exc)
    result.latency_ms = (time.perf_counter() - start) * 1000.0
    result.phases["total"] = result.latency_ms
    return result
