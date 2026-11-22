"""Latency statistics, jitter, and packet-loss accounting.

Pure functions over measured samples. The same definitions are used by
every probe and every platform implementation, so figures stay
comparable between reports.

Definitions used here:

- Percentiles use linear interpolation between closest ranks (the
  method commonly called "linear", as in NumPy's default): the rank of
  percentile ``p`` over ``n`` sorted samples is ``p/100 * (n - 1)``,
  interpolated between the neighbouring samples.
- Standard deviation is the population standard deviation: the series
  being summarised is the complete set of measurements taken, not a
  sample drawn from a larger population.
- Jitter follows the schema definition in
  ``shared/schemas/diagnostic-result.schema.json``: ``jitterAvg`` is
  the mean absolute difference between consecutive samples and
  ``jitterMax`` is the largest such difference. This is the
  successive-difference measure in the style of the RFC 3550 jitter
  estimator, reported as a plain average rather than the RFC's
  exponentially weighted form, so the figure can be reproduced from
  the raw samples alone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass
class LatencyStats:
    """A latency distribution in milliseconds, in the schema's shape."""

    count: int = 0
    min: float | None = None
    max: float | None = None
    avg: float | None = None
    median: float | None = None
    p90: float | None = None
    p95: float | None = None
    p99: float | None = None
    stddev: float | None = None
    jitter_avg: float | None = None
    jitter_max: float | None = None

    def to_dict(self) -> dict:
        out: dict = {"count": self.count}
        for key, value in (
            ("min", self.min),
            ("max", self.max),
            ("avg", self.avg),
            ("median", self.median),
            ("p90", self.p90),
            ("p95", self.p95),
            ("p99", self.p99),
            ("stddev", self.stddev),
            ("jitterAvg", self.jitter_avg),
            ("jitterMax", self.jitter_max),
        ):
            if value is not None:
                out[key] = round(float(value), 3)
        return out


def _percentile(sorted_samples: list[float], p: float) -> float:
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    rank = (p / 100.0) * (len(sorted_samples) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_samples[int(rank)]
    fraction = rank - low
    return sorted_samples[low] + fraction * (sorted_samples[high] - sorted_samples[low])


def jitter(samples: list[float]) -> tuple[float | None, float | None]:
    """(average, maximum) absolute successive difference of ``samples``.

    Returns (None, None) when fewer than two samples exist, because no
    successive difference is defined.
    """
    if len(samples) < 2:
        return None, None
    diffs = [abs(b - a) for a, b in zip(samples, samples[1:])]
    return sum(diffs) / len(diffs), max(diffs)


def latency_stats(samples: Iterable[float]) -> LatencyStats:
    """Compute the full latency distribution for a series of samples."""
    values = [float(s) for s in samples]
    if not values:
        return LatencyStats(count=0)
    ordered = sorted(values)
    count = len(values)
    mean = sum(values) / count
    variance = sum((v - mean) ** 2 for v in values) / count
    jitter_avg, jitter_max = jitter(values)
    return LatencyStats(
        count=count,
        min=ordered[0],
        max=ordered[-1],
        avg=mean,
        median=_percentile(ordered, 50),
        p90=_percentile(ordered, 90),
        p95=_percentile(ordered, 95),
        p99=_percentile(ordered, 99),
        stddev=math.sqrt(variance),
        jitter_avg=jitter_avg,
        jitter_max=jitter_max,
    )


@dataclass
class PacketLoss:
    """Packet-loss accounting for one probe series."""

    sent: int = 0
    received: int = 0
    timeouts: int = 0

    @property
    def loss_percent(self) -> float:
        if self.sent == 0:
            return 0.0
        return 100.0 * (self.sent - self.received) / self.sent


def packet_loss(sent: int, received: int, timeouts: int = 0) -> PacketLoss:
    """Build a :class:`PacketLoss` from raw counters.

    ``received`` is clamped to ``sent``; a probe that records more
    responses than probes sent has a bookkeeping bug, and the loss
    figure must not go negative to hide it.
    """
    received = max(0, min(received, sent))
    return PacketLoss(sent=sent, received=received, timeouts=timeouts)
