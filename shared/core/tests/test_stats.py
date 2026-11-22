import math

import pytest

from netscope_core.stats import jitter, latency_stats, packet_loss


def test_empty_series():
    stats = latency_stats([])
    assert stats.count == 0
    assert stats.avg is None
    assert stats.median is None
    assert stats.jitter_avg is None


def test_single_sample():
    stats = latency_stats([10.0])
    assert stats.count == 1
    assert stats.min == stats.max == stats.avg == 10.0
    assert stats.median == stats.p90 == stats.p95 == stats.p99 == 10.0
    assert stats.stddev == 0.0
    assert stats.jitter_avg is None  # no successive difference exists


def test_percentiles_known_series():
    stats = latency_stats([float(i) for i in range(1, 101)])
    assert stats.count == 100
    assert stats.min == 1.0
    assert stats.max == 100.0
    assert stats.avg == 50.5
    assert stats.median == 50.5
    # Linear interpolation: rank = p/100 * (n - 1)
    assert stats.p90 == pytest.approx(90.1)
    assert stats.p95 == pytest.approx(95.05)
    assert stats.p99 == pytest.approx(99.01)


def test_stddev_population():
    stats = latency_stats([float(i) for i in range(1, 101)])
    expected = math.sqrt((100**2 - 1) / 12)  # population stddev of 1..100
    assert stats.stddev is not None
    assert abs(stats.stddev - expected) < 1e-9


def test_jitter_known_series():
    avg, maximum = jitter([10.0, 12.0, 11.0, 15.0])
    assert avg == 7.0 / 3.0  # diffs are 2, 1, 4
    assert maximum == 4.0


def test_jitter_needs_two_samples():
    assert jitter([]) == (None, None)
    assert jitter([5.0]) == (None, None)


def test_latency_stats_includes_jitter():
    stats = latency_stats([10.0, 20.0, 10.0])
    assert stats.jitter_avg == 10.0
    assert stats.jitter_max == 10.0


def test_packet_loss_percent():
    loss = packet_loss(sent=4, received=3, timeouts=1)
    assert loss.loss_percent == 25.0
    assert loss.timeouts == 1


def test_packet_loss_no_probes():
    assert packet_loss(0, 0).loss_percent == 0.0


def test_packet_loss_clamps_received():
    loss = packet_loss(sent=2, received=5)
    assert loss.received == 2
    assert loss.loss_percent == 0.0


def test_to_dict_shape():
    data = latency_stats([10.0, 20.0]).to_dict()
    assert data["count"] == 2
    assert data["avg"] == 15.0
    assert data["jitterAvg"] == 10.0
    assert data["jitterMax"] == 10.0
    empty = latency_stats([]).to_dict()
    assert empty == {"count": 0}
