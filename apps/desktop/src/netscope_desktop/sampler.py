"""Latency sampler and chart data model — Qt-free, unit-testable.

The sampler measures TCP-connect latency to one host/port. Failed
connects are recorded as gaps (``None``) and counted as loss; latency
statistics are computed over successful samples only, using the core
engine's statistics so the desktop, the CLI and the reports agree on
the numbers.

The chart model turns a sample series into drawing coordinates and a
readable axis ceiling, with no Qt involvement: the widget in
``chart.py`` only paints what the model computes.
"""

from __future__ import annotations

import socket
import time
from collections import deque
from typing import Callable

from netscope_core.stats import latency_stats

Connector = Callable[[str, int], "float | None"]


def default_connector(host: str, port: int, timeout: float = 3.0) -> float | None:
    """Time one TCP connect; ``None`` when the connect fails."""
    start = time.perf_counter()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return None
    sock.close()
    return (time.perf_counter() - start) * 1000.0


class LatencySampler:
    """A bounded series of latency samples for one target."""

    def __init__(
        self,
        host: str,
        port: int = 443,
        max_samples: int = 300,
        connector: Connector | None = None,
    ) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be at least 1")
        self.host = host
        self.port = port
        self.max_samples = max_samples
        self._connector = connector if connector is not None else default_connector
        self._samples: deque[float | None] = deque(maxlen=max_samples)

    def sample_once(self) -> float | None:
        value = self._connector(self.host, self.port)
        self._samples.append(value)
        return value

    def clear(self) -> None:
        self._samples.clear()

    @property
    def series(self) -> list[float | None]:
        return list(self._samples)

    @property
    def sent(self) -> int:
        return len(self._samples)

    @property
    def received(self) -> int:
        return sum(1 for s in self._samples if s is not None)

    @property
    def loss_percent(self) -> float:
        if not self._samples:
            return 0.0
        return 100.0 * (len(self._samples) - self.received) / len(self._samples)

    def stats(self) -> dict:
        """Summary statistics; latency fields are ``None`` with no successes."""
        good = [s for s in self._samples if s is not None]
        dist = latency_stats(good)
        return {
            "last": self._samples[-1] if self._samples else None,
            "avg": dist.avg,
            "min": dist.min,
            "max": dist.max,
            "p95": dist.p95,
            "jitter_avg": dist.jitter_avg,
            "jitter_max": dist.jitter_max,
            "sent": self.sent,
            "received": self.received,
            "loss_percent": self.loss_percent,
        }


_NICE_CEILINGS = (10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)


class ChartModel:
    """Geometry for one latency series: axis ceiling and line segments."""

    def __init__(self, series: list[float | None]) -> None:
        self.series = list(series)

    def ceiling_ms(self) -> float:
        values = [s for s in self.series if s is not None]
        if not values:
            return 100.0
        peak = max(values)
        for nice in _NICE_CEILINGS:
            if peak <= nice:
                return float(nice)
        return peak * 1.2

    def segments(self, width: float, height: float) -> list[list[tuple[float, float]]]:
        """Line segments in widget coordinates; failures break the line.

        ``width``/``height`` are the plot area in pixels, y growing
        downward (Qt convention): a sample's y is ``height`` at 0 ms
        and ``0`` at the ceiling.
        """
        if len(self.series) < 1 or width <= 0 or height <= 0:
            return []
        ceiling = self.ceiling_ms()
        step = width / max(1, len(self.series) - 1) if len(self.series) > 1 else 0.0
        segments: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []
        for index, value in enumerate(self.series):
            if value is None:
                if len(current) >= 2:
                    segments.append(current)
                current = []
                continue
            x = index * step if len(self.series) > 1 else width / 2.0
            y = height - (value / ceiling) * height
            current.append((x, y))
        if len(current) >= 2:
            segments.append(current)
        return segments

    def failure_positions(self, width: float) -> list[float]:
        """X coordinates of failed samples, for baseline markers."""
        if len(self.series) <= 1:
            return [width / 2.0] if self.series and self.series[0] is None else []
        step = width / max(1, len(self.series) - 1)
        return [i * step for i, s in enumerate(self.series) if s is None]
