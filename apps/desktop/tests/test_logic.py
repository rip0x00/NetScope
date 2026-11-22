"""Qt-free logic tests for history, settings, themes and sampling."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from netscope_core.dnsprobe import DNSReport
from netscope_core.models import HostReport
from netscope_core.tcpprobe import Attempt, TCPResult
from netscope_core.verdict import Verdict

from netscope_desktop.history import HistoryStore
from netscope_desktop.sampler import ChartModel, LatencySampler
from netscope_desktop.settings import Settings
from netscope_desktop.theme import build_stylesheet, load_tokens, theme_colors


def make_report(
    host: str = "example.com", generated_at: str = "2026-11-22T10:00:00+00:00"
) -> HostReport:
    return HostReport(
        host=host,
        dns=DNSReport(
            hostname=host,
            system_addresses=["192.0.2.10"],
            system_latency_ms=3.0,
        ),
        tcp={
            443: TCPResult(host, 443, [Attempt(ok=True, latency_ms=12.5)]),
            80: TCPResult(host, 80, [Attempt(ok=True, latency_ms=15.0)]),
        },
        tls=None,
        http={},
        results=[],
        verdict=Verdict("OK", "Fixture report.", "high"),
        generated_at=generated_at,
        app_surface="desktop-test",
    )


def test_history_add_list_filter_and_read_back(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "nested" / "history.db")
    try:
        assert store.db_path.exists()
        first_id = store.add_report(make_report("alpha.example"))
        second_id = store.add_report(make_report("beta.example"))

        assert store.count() == 2
        assert [row.id for row in store.list_reports()] == [second_id, first_id]
        filtered = store.list_reports(host="alpha")
        assert [row.id for row in filtered] == [first_id]
        assert filtered[0].tcp443_avg_ms == pytest.approx(12.5)

        data = store.get_report_json(first_id)
        assert data is not None
        assert data["target"]["host"] == "alpha.example"
        assert data["summary"]["verdict"] == "OK"
        markdown = store.get_report_markdown(first_id)
        assert markdown is not None and "alpha.example" in markdown
    finally:
        store.close()


def test_history_delete(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.db")
    try:
        first_id = store.add_report(make_report("one.example"))
        store.add_report(make_report("two.example"))

        assert store.delete(first_id) is True
        assert store.delete(first_id) is False
        assert store.count() == 1
    finally:
        store.close()


def _run_history_operation(tmp_path: Path, operation: str) -> str:
    """Run a store operation in a subprocess with a hard timeout.

    A separate process keeps a defective, non-returning store method
    from hanging the whole test session; a timeout is a test failure
    with the operation name attached.
    """
    db_path = tmp_path / f"{operation}.db"
    tests_dir = Path(__file__).resolve().parent
    src_dir = tests_dir.parents[1] / "src"
    code = textwrap.dedent(
        f"""
        import sys
        from pathlib import Path
        sys.path.insert(0, {str(tests_dir)!r})
        sys.path.insert(0, {str(src_dir)!r})
        from test_logic import make_report
        from netscope_desktop.history import HistoryStore

        store = HistoryStore(Path({str(db_path)!r}))
        try:
            if {operation!r} == "clear":
                store.add_report(make_report("one.example"))
                store.add_report(make_report("two.example"))
                print(store.clear(), store.count())
            elif {operation!r} == "startup-prune":
                from netscope_desktop.settings import Settings

                settings = Settings()
                store.add_report(
                    make_report(
                        "old.example", generated_at="2020-01-01T00:00:00+00:00"
                    )
                )
                store.add_report(make_report("recent.example"))
                removed = store.prune(
                    settings.history_retention_days, settings.history_max_rows
                )
                hosts = [row.host for row in store.list_reports()]
                print(removed, store.count(), hosts)
            else:
                store.add_report(
                    make_report(
                        "old.example", generated_at="2020-01-01T00:00:00+00:00"
                    )
                )
                store.add_report(
                    make_report(
                        "recent-one.example",
                        generated_at="2026-11-22T10:00:00+00:00",
                    )
                )
                newest_id = store.add_report(
                    make_report(
                        "recent-two.example",
                        generated_at="2026-11-22T11:00:00+00:00",
                    )
                )
                removed_age = store.prune(retention_days=90, max_rows=10)
                hosts = [row.host for row in store.list_reports()]
                removed_rows = store.prune(retention_days=3650, max_rows=1)
                remaining = [row.id for row in store.list_reports()]
                print(removed_age, hosts, removed_rows, remaining == [newest_id])
        finally:
            store.close()
        """
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(f"HistoryStore {operation} did not return within 10s") from exc
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def test_history_clear_completes(tmp_path: Path) -> None:
    assert _run_history_operation(tmp_path, "clear") == "2 0"


def test_history_prune_enforces_age_and_row_retention(tmp_path: Path) -> None:
    output = _run_history_operation(tmp_path, "prune")
    assert output == "1 ['recent-two.example', 'recent-one.example'] 1 True"


def test_history_prune_on_startup_path_completes(tmp_path: Path) -> None:
    """Mirror ``app.main``: a fresh store pruned with the default settings.

    Regression test for the start-up deadlock — ``main`` calls
    ``store.prune(settings.history_retention_days,
    settings.history_max_rows)`` before any window exists, so a
    non-returning prune hangs the whole application launch.
    """
    output = _run_history_operation(tmp_path, "startup-prune")
    assert output == "1 1 ['recent.example']"


def test_settings_defaults_and_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "settings.json"
    settings = Settings(
        theme="light",
        resolvers=["1.1.1.1", "9.9.9.9"],
        speed_download_url="https://example.test/download",
        speed_upload_url="https://example.test/upload",
        history_retention_days=30,
        history_max_rows=25,
    )

    assert settings.save(path) == path
    loaded = Settings.load(path)
    assert loaded == settings
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["theme"] == "light"
    assert raw["history_max_rows"] == 25


def test_settings_missing_corrupt_and_unknown_keys_fall_back(tmp_path: Path) -> None:
    missing = Settings.load(tmp_path / "absent.json")
    assert missing.theme == "dark"
    assert missing.history_retention_days == 90

    corrupt_path = tmp_path / "settings.json"
    corrupt_path.write_text("{not json", encoding="utf-8")
    assert Settings.load(corrupt_path) == Settings()

    corrupt_path.write_text(
        json.dumps({"theme": "light", "unknown": "ignored", "history_max_rows": 12}),
        encoding="utf-8",
    )
    loaded = Settings.load(corrupt_path)
    assert loaded.theme == "light"
    assert loaded.history_max_rows == 12
    assert not hasattr(loaded, "unknown")


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_stylesheets_contain_exact_token_colours(theme: str) -> None:
    tokens = load_tokens()
    stylesheet = build_stylesheet(theme, tokens)
    colours = theme_colors(theme, tokens)

    assert colours == tokens["color"][theme]
    for value in colours.values():
        assert value in stylesheet
    assert tokens["typography"]["fontFamilyUi"] in stylesheet
    assert tokens["typography"]["fontFamilyMono"] in stylesheet


def test_sampler_statistics_and_bounded_series() -> None:
    values = iter([10.0, None, 30.0, 20.0])
    sampler = LatencySampler(
        "example.com", 443, max_samples=3, connector=lambda _host, _port: next(values)
    )

    assert sampler.sample_once() == 10.0
    assert sampler.sample_once() is None
    assert sampler.sample_once() == 30.0
    assert sampler.sample_once() == 20.0
    assert sampler.series == [None, 30.0, 20.0]

    stats = sampler.stats()
    assert stats["sent"] == 3
    assert stats["received"] == 2
    assert stats["loss_percent"] == pytest.approx(100.0 / 3.0)
    assert stats["last"] == 20.0
    assert stats["avg"] == pytest.approx(25.0)
    assert stats["min"] == 20.0
    assert stats["max"] == 30.0
    assert stats["jitter_avg"] == pytest.approx(10.0)


def test_chart_model_gap_segmentation_and_failure_positions() -> None:
    model = ChartModel([10.0, None, 30.0, 40.0])

    assert model.ceiling_ms() == 50.0
    segments = model.segments(width=300.0, height=100.0)
    assert len(segments) == 1
    assert len(segments[0]) == 2
    assert segments[0][0][0] == pytest.approx(200.0)
    assert model.failure_positions(300.0) == [100.0]
    assert ChartModel([]).ceiling_ms() == 100.0
    assert ChartModel([None]).failure_positions(80.0) == [40.0]
