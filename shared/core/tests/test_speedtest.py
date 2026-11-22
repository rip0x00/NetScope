"""Speed-test arithmetic with a scripted transport: no network."""

import threading
import time

import pytest

from netscope_core.speedtest import SpeedConfig, run_speed_test


class FakeTransport:
    def __init__(self, down=(8_000_000, 8.0), up=(5_000_000, 5.0), download_delay=0.0):
        self.down = down
        self.up = up
        self.download_delay = download_delay
        self.download_calls = 0
        self.upload_calls = 0

    def download(self, url, max_bytes, max_duration_s, cancel):
        self.download_calls += 1
        if self.download_delay:
            time.sleep(self.download_delay)
        return self.down

    def upload(self, url, total_bytes, max_duration_s, cancel):
        self.upload_calls += 1
        return self.up


def config(**kwargs):
    base = {"download_urls": ["https://speed.example.test/down"], "upload_url": "https://speed.example.test/up"}
    base.update(kwargs)
    return SpeedConfig(**base)


def test_throughput_math():
    result = run_speed_test(config(), transport=FakeTransport(), latency_connector=lambda: 10.0)
    assert result.bytes_downloaded == 8_000_000
    assert result.download_mbps == pytest.approx(8.0)  # 8 MB in 8 s = 8 Mbit/s
    assert result.bytes_uploaded == 5_000_000
    assert result.upload_mbps == pytest.approx(8.0)
    assert result.cancelled is False
    assert result.errors == []


def test_idle_latency_uses_connector_samples():
    result = run_speed_test(
        config(latency_samples=5), transport=FakeTransport(), latency_connector=lambda: 12.5
    )
    assert result.idle_latency is not None
    assert result.idle_latency.count == 5
    assert result.idle_latency.avg == 12.5


def test_loaded_latency_sampled_during_download():
    transport = FakeTransport(download_delay=0.3)
    result = run_speed_test(config(), transport=transport, latency_connector=lambda: 20.0)
    assert result.loaded_latency is not None
    assert result.loaded_latency.count >= 1


def test_pre_set_cancel_skips_everything():
    cancel = threading.Event()
    cancel.set()
    transport = FakeTransport()
    result = run_speed_test(config(), cancel=cancel, transport=transport, latency_connector=lambda: 1.0)
    assert result.cancelled is True
    assert transport.download_calls == 0
    assert transport.upload_calls == 0
    assert result.bytes_downloaded == 0


def test_cancel_during_download_keeps_partial_result():
    cancel = threading.Event()

    class CancellingTransport(FakeTransport):
        def download(self, url, max_bytes, max_duration_s, cancel_event):
            cancel_event.set()
            return (1000, 0.5)

    transport = CancellingTransport()
    result = run_speed_test(config(), cancel=cancel, transport=transport, latency_connector=lambda: 1.0)
    assert result.cancelled is True
    assert result.bytes_downloaded == 1000
    assert result.download_mbps == pytest.approx(1000 * 8 / 0.5 / 1_000_000)
    assert transport.upload_calls == 0  # upload skipped after cancellation


def test_no_endpoints_is_a_configuration_error():
    with pytest.raises(ValueError):
        run_speed_test(SpeedConfig(download_urls=[], upload_url=None), transport=FakeTransport())


def test_transport_error_is_recorded_not_raised():
    class BrokenTransport(FakeTransport):
        def download(self, url, max_bytes, max_duration_s, cancel):
            raise OSError("connection reset")

    result = run_speed_test(config(), transport=BrokenTransport(), latency_connector=lambda: 1.0)
    assert result.download_mbps is None
    assert any("download" in e for e in result.errors)
