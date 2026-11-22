"""Throughput measurement against configurable endpoints.

A speed test is only meaningful if the endpoint is known, so the
endpoints are configuration, not constants baked into the logic. The
defaults below point at Cloudflare's public speed-test endpoints
(``speed.cloudflare.com``); they are used only when the caller does
not configure its own, they are named in the result, and no traffic
is generated until :func:`run_speed_test` is called. A self-hosted
endpoint (for example an iperf-style HTTP target or a static file on
the user's own server) can replace them entirely.

Method: download reads the response body in chunks until the byte
budget, the duration budget, or cancellation stops it; upload posts a
generated body of the configured size. Throughput is
``bytes * 8 / elapsed``. Idle latency is measured before the transfer;
latency under load is sampled with TCP connects while the download
runs. The transport is an injectable object so the arithmetic can be
tested without a network.
"""

from __future__ import annotations

import http.client
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol
from urllib.parse import urlsplit

from .stats import LatencyStats, latency_stats

# Default endpoints, used only when the configuration does not provide
# its own. Both are Cloudflare's public speed-test service.
DEFAULT_DOWNLOAD_URL = "https://speed.cloudflare.com/__down"
DEFAULT_UPLOAD_URL = "https://speed.cloudflare.com/__up"

_CHUNK = 65536
_UPLOAD_BLOCK = b"\x00" * _CHUNK


@dataclass
class SpeedConfig:
    download_urls: list[str] = field(default_factory=lambda: [DEFAULT_DOWNLOAD_URL])
    upload_url: str | None = DEFAULT_UPLOAD_URL
    max_download_bytes: int = 10_000_000
    max_upload_bytes: int = 5_000_000
    max_duration_s: float = 15.0
    latency_host: str | None = None  # defaults to the first download URL's host
    latency_port: int = 443
    latency_samples: int = 5


class Transport(Protocol):
    """Byte-moving operations, injectable for tests.

    Both methods return ``(bytes_transferred, elapsed_seconds)`` as
    measured by the transport, and must stop early when ``cancel`` is
    set, returning whatever was transferred.
    """

    def download(self, url: str, max_bytes: int, max_duration_s: float, cancel: threading.Event) -> tuple[int, float]:
        ...

    def upload(self, url: str, total_bytes: int, max_duration_s: float, cancel: threading.Event) -> tuple[int, float]:
        ...


class HttpTransport:
    """The default transport, built on ``http.client``."""

    def download(self, url: str, max_bytes: int, max_duration_s: float, cancel: threading.Event) -> tuple[int, float]:
        parts = urlsplit(url)
        host = parts.hostname
        if host is None:
            raise ValueError(f"URL has no host: {url}")
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        connection = self._connect(parts, host)
        start = time.perf_counter()
        received = 0
        try:
            connection.request("GET", path, headers={"User-Agent": "NetScope/0.1 speedtest"})
            response = connection.getresponse()
            while received < max_bytes and not cancel.is_set():
                if time.perf_counter() - start > max_duration_s:
                    break
                chunk = response.read(min(_CHUNK, max_bytes - received))
                if not chunk:
                    break
                received += len(chunk)
        finally:
            connection.close()
        return received, time.perf_counter() - start

    def upload(self, url: str, total_bytes: int, max_duration_s: float, cancel: threading.Event) -> tuple[int, float]:
        parts = urlsplit(url)
        host = parts.hostname
        if host is None:
            raise ValueError(f"URL has no host: {url}")
        path = parts.path or "/"
        connection = self._connect(parts, host)
        start = time.perf_counter()
        sent = 0
        try:
            connection.putrequest("POST", path)
            connection.putheader("Content-Type", "application/octet-stream")
            connection.putheader("Content-Length", str(total_bytes))
            connection.putheader("User-Agent", "NetScope/0.1 speedtest")
            connection.endheaders()
            while sent < total_bytes and not cancel.is_set():
                if time.perf_counter() - start > max_duration_s:
                    break
                block = _UPLOAD_BLOCK[: min(_CHUNK, total_bytes - sent)]
                connection.send(block)
                sent += len(block)
            if sent == total_bytes:
                response = connection.getresponse()
                response.read()
        finally:
            connection.close()
        return sent, time.perf_counter() - start

    @staticmethod
    def _connect(parts, host: str) -> http.client.HTTPConnection:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if parts.scheme == "https":
            return http.client.HTTPSConnection(host, port, timeout=10.0)
        return http.client.HTTPConnection(host, port, timeout=10.0)


@dataclass
class SpeedResult:
    download_mbps: float | None = None
    upload_mbps: float | None = None
    bytes_downloaded: int = 0
    bytes_uploaded: int = 0
    download_endpoint: str | None = None
    upload_endpoint: str | None = None
    idle_latency: LatencyStats | None = None
    loaded_latency: LatencyStats | None = None
    cancelled: bool = False
    errors: list[str] = field(default_factory=list)


def _mbps(byte_count: int, elapsed_s: float) -> float | None:
    if byte_count <= 0 or elapsed_s <= 0:
        return None
    return byte_count * 8 / elapsed_s / 1_000_000.0


def _default_connector(host: str, port: int) -> Callable[[], float | None]:
    def connect() -> float | None:
        start = time.perf_counter()
        try:
            sock = socket.create_connection((host, port), timeout=3.0)
        except OSError:
            return None
        sock.close()
        return (time.perf_counter() - start) * 1000.0

    return connect


def run_speed_test(
    config: SpeedConfig,
    cancel: threading.Event | None = None,
    transport: Transport | None = None,
    latency_connector: Callable[[], float | None] | None = None,
) -> SpeedResult:
    """Run a download/upload speed test per ``config``.

    ``cancel`` stops the test between chunks and between phases; the
    result records ``cancelled=True`` and whatever was measured before
    the stop. ``transport`` and ``latency_connector`` are injectable
    for tests.
    """
    if not config.download_urls and config.upload_url is None:
        raise ValueError("speed test needs at least one download or upload endpoint")
    cancel = cancel if cancel is not None else threading.Event()
    transport = transport if transport is not None else HttpTransport()
    result = SpeedResult()

    latency_host = config.latency_host
    if latency_host is None and config.download_urls:
        latency_host = urlsplit(config.download_urls[0]).hostname
    connector = latency_connector
    if connector is None and latency_host:
        connector = _default_connector(latency_host, config.latency_port)

    if connector is not None and not cancel.is_set():
        idle: list[float] = []
        for _ in range(config.latency_samples):
            if cancel.is_set():
                break
            sample = connector()
            if sample is not None:
                idle.append(sample)
        result.idle_latency = latency_stats(idle)

    if config.download_urls and not cancel.is_set():
        url = config.download_urls[0]
        result.download_endpoint = url
        loaded: list[float] = []
        stop_sampling = threading.Event()

        def sampler() -> None:
            while not stop_sampling.is_set() and not cancel.is_set():
                if connector is not None:
                    sample = connector()
                    if sample is not None:
                        loaded.append(sample)
                stop_sampling.wait(0.05)

        thread = threading.Thread(target=sampler, daemon=True)
        thread.start()
        try:
            byte_count, elapsed = transport.download(
                url, config.max_download_bytes, config.max_duration_s, cancel
            )
            result.bytes_downloaded = byte_count
            result.download_mbps = _mbps(byte_count, elapsed)
        except (OSError, ValueError) as exc:
            result.errors.append(f"download: {exc}")
        finally:
            stop_sampling.set()
            thread.join(timeout=2.0)
        if loaded:
            result.loaded_latency = latency_stats(loaded)

    if config.upload_url and not cancel.is_set():
        result.upload_endpoint = config.upload_url
        try:
            byte_count, elapsed = transport.upload(
                config.upload_url, config.max_upload_bytes, config.max_duration_s, cancel
            )
            result.bytes_uploaded = byte_count
            result.upload_mbps = _mbps(byte_count, elapsed)
        except (OSError, ValueError) as exc:
            result.errors.append(f"upload: {exc}")

    result.cancelled = cancel.is_set()
    return result
