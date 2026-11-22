"""TCP connect probing.

Latency here is the time to complete a TCP connect. That is not a pure
network round-trip (it includes the peer accepting the connection),
but it needs no special privileges and works the same on every
platform. Error classification is shared with all probes via
:mod:`netscope_core.errors`.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field

from .errors import classify_socket_error
from .stats import LatencyStats, latency_stats

__all__ = ["Attempt", "TCPResult", "classify_socket_error", "probe_tcp"]


@dataclass
class Attempt:
    ok: bool
    latency_ms: float | None = None
    error_kind: str | None = None
    error: str | None = None


@dataclass
class TCPResult:
    target: str
    port: int
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def successes(self) -> int:
        return sum(1 for a in self.attempts if a.ok)

    @property
    def loss_pct(self) -> float:
        if not self.attempts:
            return 100.0
        return 100.0 * (len(self.attempts) - self.successes) / len(self.attempts)

    @property
    def timeouts(self) -> int:
        return sum(1 for a in self.attempts if not a.ok and a.error_kind == "timeout")

    @property
    def avg_latency_ms(self) -> float | None:
        stats = self.latency
        return stats.avg if stats.count else None

    @property
    def latency(self) -> LatencyStats:
        return latency_stats(
            [a.latency_ms for a in self.attempts if a.ok and a.latency_ms is not None]
        )

    @property
    def dominant_error(self) -> str | None:
        counts: dict[str, int] = {}
        for a in self.attempts:
            if not a.ok and a.error_kind:
                counts[a.error_kind] = counts.get(a.error_kind, 0) + 1
        if not counts:
            return None
        return max(counts, key=counts.get)


def probe_tcp(target: str, port: int, attempts: int = 4, timeout: float = 4.0) -> TCPResult:
    """Connect to ``target``:``port`` several times and record each attempt."""
    result = TCPResult(target=target, port=port)
    for _ in range(attempts):
        start = time.perf_counter()
        try:
            sock = socket.create_connection((target, port), timeout=timeout)
        except OSError as exc:
            result.attempts.append(
                Attempt(ok=False, error_kind=classify_socket_error(exc), error=str(exc))
            )
            continue
        latency = (time.perf_counter() - start) * 1000.0
        sock.close()
        result.attempts.append(Attempt(ok=True, latency_ms=latency))
    return result
