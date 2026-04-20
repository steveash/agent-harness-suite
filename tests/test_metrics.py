"""Tests for the metrics collector and reporter."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from agent_harness_suite.metrics import (
    BenchmarkReport,
    default_output_paths,
    render_summary,
    write_json,
    write_text_summary,
)
from agent_harness_suite.types import (
    EventKind,
    LifecycleEvent,
    RunMetrics,
    RunResult,
    RunStatus,
)


def _result(
    *,
    adapter: str = "stub",
    scenario: str = "basic",
    status: RunStatus = RunStatus.SUCCESS,
    turns: int = 2,
    in_tok: int = 100,
    out_tok: int = 50,
    agents: int = 1,
    tools: int = 3,
    error: str | None = None,
    output: str | None = "ok",
) -> RunResult:
    return RunResult(
        status=status,
        metrics=RunMetrics(
            wall_clock_seconds=1.5,
            total_turns=turns,
            total_input_tokens=in_tok,
            total_output_tokens=out_tok,
            total_agents_spawned=agents,
            tool_calls=tools,
        ),
        events=[LifecycleEvent(kind=EventKind.RUN_COMPLETED)],
        output=output,
        adapter_name=adapter,
        scenario_name=scenario,
        error_message=error,
    )


class TestBenchmarkReport:
    def test_add_and_finalize(self):
        report = BenchmarkReport()
        assert report.results == []
        assert report.finished_at is None

        report.add(_result())
        report.finalize()

        assert len(report.results) == 1
        assert report.finished_at is not None
        assert report.wall_clock_seconds >= 0.0

    def test_to_dict_shape(self):
        report = BenchmarkReport(metadata={"repo_url": "https://example/x"})
        report.add(_result(adapter="claude", scenario="repo-to-plan"))
        report.add(_result(adapter="copilot", status=RunStatus.ERROR, error="boom"))
        report.finalize()

        data = report.to_dict()
        assert data["metadata"] == {"repo_url": "https://example/x"}
        assert len(data["runs"]) == 2

        first = data["runs"][0]
        assert first["adapter"] == "claude"
        assert first["scenario"] == "repo-to-plan"
        assert first["status"] == "success"
        assert first["metrics"]["total_tokens"] == 150
        assert first["metrics"]["total_turns"] == 2
        assert first["metrics"]["total_agents_spawned"] == 1
        assert first["event_count"] == 1

        second = data["runs"][1]
        assert second["status"] == "error"
        assert second["error_message"] == "boom"

    def test_output_truncated(self):
        big = "x" * 5000
        report = BenchmarkReport()
        report.add(_result(output=big))
        truncated = report.to_dict()["runs"][0]["output"]
        assert truncated.startswith("x" * 2000)
        assert "truncated" in truncated


class TestReporter:
    def test_write_json_roundtrip(self, tmp_path: Path):
        report = BenchmarkReport(metadata={"scenario": "repo-to-plan"})
        report.add(_result(adapter="claude"))
        report.add(_result(adapter="copilot", status=RunStatus.FAILURE, error="nope"))
        report.finalize()

        out = tmp_path / "benchmark.json"
        write_json(report, out)

        loaded = json.loads(out.read_text())
        assert loaded["metadata"]["scenario"] == "repo-to-plan"
        assert len(loaded["runs"]) == 2
        assert loaded["runs"][1]["status"] == "failure"
        assert loaded["runs"][1]["error_message"] == "nope"

    def test_write_json_creates_parents(self, tmp_path: Path):
        report = BenchmarkReport()
        report.add(_result())
        report.finalize()

        out = tmp_path / "nested" / "dir" / "b.json"
        write_json(report, out)
        assert out.exists()

    def test_write_text_summary(self, tmp_path: Path):
        report = BenchmarkReport()
        report.add(_result(adapter="claude"))
        report.add(_result(adapter="copilot", status=RunStatus.ERROR, error="boom"))
        report.finalize()

        out = tmp_path / "summary.txt"
        write_text_summary(report, out)
        text = out.read_text()

        assert "Benchmark Results" in text
        assert "claude" in text
        assert "copilot" in text
        assert "Runs: 2" in text
        assert "error copilot/basic: boom" in text

    def test_render_summary_to_console(self):
        report = BenchmarkReport()
        report.add(_result(adapter="claude"))
        report.add(_result(adapter="copilot", status=RunStatus.ERROR, error="boom"))
        report.finalize()

        console = Console(record=True, width=160)
        render_summary(report, console=console)
        out = console.export_text()
        assert "claude" in out
        assert "copilot" in out
        assert "boom" in out

    def test_default_output_paths(self, tmp_path: Path):
        j, t = default_output_paths(tmp_path, timestamp=0)
        assert j.parent == tmp_path
        assert t.parent == tmp_path
        assert j.suffix == ".json"
        assert t.suffix == ".txt"
        assert j.stem == t.stem
