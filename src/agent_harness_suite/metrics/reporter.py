"""Report writers for benchmark runs.

Produces two artifacts from a :class:`BenchmarkReport`:
* machine-readable JSON suitable for comparison tooling, and
* a human-readable Rich table rendered to the console (or plain text).
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import IO

from rich.console import Console
from rich.table import Table

from agent_harness_suite.metrics.collector import BenchmarkReport
from agent_harness_suite.types import RunStatus


def write_json(report: BenchmarkReport, path: Path) -> Path:
    """Serialize *report* to JSON at *path*.  Creates parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, indent=2, sort_keys=True, default=str)
    return path


def render_summary(report: BenchmarkReport, console: Console | None = None) -> None:
    """Render a summary table of *report* to *console* (defaults to stdout)."""
    console = console or Console()

    table = Table(title="Benchmark Results", show_lines=False)
    table.add_column("Adapter", style="cyan", no_wrap=True)
    table.add_column("Scenario", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Wall (s)", justify="right")
    table.add_column("Turns", justify="right")
    table.add_column("In tok", justify="right")
    table.add_column("Out tok", justify="right")
    table.add_column("Agents", justify="right")
    table.add_column("Tools", justify="right")

    for r in report.results:
        m = r.metrics
        table.add_row(
            r.adapter_name,
            r.scenario_name,
            _status_cell(r.status),
            f"{m.wall_clock_seconds:.2f}",
            str(m.total_turns),
            str(m.total_input_tokens),
            str(m.total_output_tokens),
            str(m.total_agents_spawned),
            str(m.tool_calls),
        )

    console.print(table)
    console.print(
        f"[dim]Total wall-clock: {report.wall_clock_seconds:.2f}s  "
        f"Runs: {len(report.results)}[/dim]"
    )
    for r in report.results:
        if r.error_message:
            console.print(
                f"[red]error[/red] {r.adapter_name}/{r.scenario_name}: {r.error_message}"
            )


def write_text_summary(report: BenchmarkReport, path: Path) -> Path:
    """Write a plain-text summary of *report* to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        _write_plain(report, fh)
    return path


def _write_plain(report: BenchmarkReport, fh: IO[str]) -> None:
    fh.write("Benchmark Results\n")
    fh.write("=================\n")
    started = _dt.datetime.fromtimestamp(report.started_at).isoformat(timespec="seconds")
    fh.write(f"Started: {started}\n")
    fh.write(f"Total wall-clock: {report.wall_clock_seconds:.2f}s\n")
    fh.write(f"Runs: {len(report.results)}\n\n")
    header = (
        f"{'adapter':<12} {'scenario':<24} {'status':<8} "
        f"{'wall(s)':>8} {'turns':>6} {'in_tok':>8} {'out_tok':>8} "
        f"{'agents':>6} {'tools':>6}\n"
    )
    fh.write(header)
    fh.write("-" * (len(header) - 1) + "\n")
    for r in report.results:
        m = r.metrics
        fh.write(
            f"{r.adapter_name:<12} {r.scenario_name:<24} {r.status.value:<8} "
            f"{m.wall_clock_seconds:>8.2f} {m.total_turns:>6} "
            f"{m.total_input_tokens:>8} {m.total_output_tokens:>8} "
            f"{m.total_agents_spawned:>6} {m.tool_calls:>6}\n"
        )
    fh.write("\n")
    for r in report.results:
        if r.error_message:
            fh.write(f"error {r.adapter_name}/{r.scenario_name}: {r.error_message}\n")


def default_output_paths(results_dir: Path, timestamp: float | None = None) -> tuple[Path, Path]:
    """Compute ``(json_path, summary_path)`` under *results_dir* using a timestamp slug."""
    ts = _dt.datetime.fromtimestamp(timestamp) if timestamp else _dt.datetime.now()
    slug = ts.strftime("%Y%m%d-%H%M%S")
    return (
        results_dir / f"benchmark-{slug}.json",
        results_dir / f"benchmark-{slug}.txt",
    )


def _status_cell(status: RunStatus) -> str:
    colors = {
        RunStatus.SUCCESS: "green",
        RunStatus.FAILURE: "yellow",
        RunStatus.TIMEOUT: "yellow",
        RunStatus.ERROR: "red",
    }
    color = colors.get(status, "white")
    return f"[{color}]{status.value}[/{color}]"
