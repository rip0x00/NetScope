"""Background workers: every network operation runs off the UI thread.

Errors are reported as plain message strings — never as tracebacks in
a dialog. The monitor worker owns its timer loop so a slow connect
delays the next tick instead of overlapping with it.
"""

from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QThread, Signal

from netscope_core.speedtest import SpeedConfig, SpeedResult, run_speed_test

from .sampler import LatencySampler


class FunctionWorker(QThread):
    """Run one callable in the background; emit its result or error."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable, *args, **kwargs) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # surfaced as a plain message, by design
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(result)


class MonitorWorker(QThread):
    """Sample latency on an interval until stopped."""

    tick = Signal(dict)
    failed = Signal(str)

    def __init__(self, sampler: LatencySampler, interval_s: float) -> None:
        super().__init__()
        self._sampler = sampler
        self._interval_s = interval_s
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._sampler.sample_once()
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")
                return
            self.tick.emit(self._sampler.stats())
            self._stop.wait(self._interval_s)


class SpeedWorker(QThread):
    """Run the core speed test with a cancellation event."""

    done = Signal(object)  # SpeedResult
    failed = Signal(str)

    def __init__(self, config: SpeedConfig) -> None:
        super().__init__()
        self._config = config
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def run(self) -> None:
        try:
            result: SpeedResult = run_speed_test(self._config, cancel=self.cancel_event)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(result)
