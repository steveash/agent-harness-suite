"""``ahs run`` CLI — thin wrapper around ``inspect_ai.eval``."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from ahs.benchmarks import smoke, tb2, tb2_smoke
from ahs.harnesses import HARNESS_PRESETS, resolve_harness
from ahs.models import resolve_model

# Benchmark name (CLI-facing, dash-delimited) → zero-arg task factory.
BENCHMARKS: dict[str, Any] = {
    "smoke": smoke,
    "tb-smoke": tb2_smoke,
    "tb": tb2,
}


@click.group()
def cli() -> None:
    """Agent Harness Suite CLI."""


@cli.command("run")
@click.option(
    "--benchmark",
    "-b",
    required=True,
    type=click.Choice(sorted(BENCHMARKS)),
    help="Benchmark to run.",
)
@click.option(
    "--model",
    "-m",
    required=True,
    help="Model preset name (e.g. haiku45) or fully-qualified spec (e.g. mockllm/model).",
)
@click.option(
    "--harness",
    "-H",
    type=click.Choice(sorted(HARNESS_PRESETS)),
    default=None,
    help=(
        "Harness/agent preset (e.g. mini-swe). When set, overrides the benchmark "
        "Task's default solver — required for benchmarks like Terminal-Bench whose "
        "Inspect Task is harness-agnostic."
    ),
)
@click.option(
    "--task-names",
    "task_names",
    multiple=True,
    help=(
        "Filter benchmark dataset by Harbor task ID (repeat for multiple, supports "
        "glob patterns). Only applies to Harbor-backed benchmarks (tb, tb-smoke)."
    ),
)
@click.option(
    "--log-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("results"),
    show_default=True,
    help="Directory to write Inspect logs to.",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Optional sample limit (passes through to inspect_ai.eval).",
)
def run(
    benchmark: str,
    model: str,
    harness: str | None,
    task_names: tuple[str, ...],
    log_dir: Path,
    limit: int | None,
) -> None:
    """Run a benchmark against a model and emit an Inspect log."""
    from inspect_ai import eval as inspect_eval  # imported here to keep --help snappy

    log_dir.mkdir(parents=True, exist_ok=True)
    task_fn = BENCHMARKS[benchmark]
    model_spec = resolve_model(model)

    task_kwargs: dict[str, Any] = {}
    if task_names:
        if benchmark not in {"tb", "tb-smoke"}:
            raise click.UsageError(
                f"--task-names is only supported for Harbor-backed benchmarks "
                f"(tb, tb-smoke); got --benchmark {benchmark}."
            )
        task_kwargs["dataset_task_names"] = list(task_names)

    eval_kwargs: dict[str, Any] = {
        "model": model_spec,
        "log_dir": str(log_dir),
        "limit": limit,
    }
    if harness is not None:
        eval_kwargs["solver"] = resolve_harness(harness)

    logs = inspect_eval(task_fn(**task_kwargs), **eval_kwargs)

    # inspect_eval returns a list[EvalLog]; surface a non-zero exit if any failed.
    failed = [log for log in logs if log.status != "success"]
    if failed:
        click.echo(f"FAILED: {len(failed)}/{len(logs)} eval(s) did not succeed", err=True)
        sys.exit(1)


def main() -> None:
    """Entry point for the ``ahs`` console script."""
    cli()


if __name__ == "__main__":
    main()
