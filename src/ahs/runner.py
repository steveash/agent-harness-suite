"""``ahs run`` CLI — thin wrapper around ``inspect_ai.eval``."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ahs.benchmarks import smoke
from ahs.models import resolve_model

BENCHMARKS = {
    "smoke": smoke,
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
def run(benchmark: str, model: str, log_dir: Path, limit: int | None) -> None:
    """Run a benchmark against a model and emit an Inspect log."""
    from inspect_ai import eval as inspect_eval  # imported here to keep --help snappy

    log_dir.mkdir(parents=True, exist_ok=True)
    task_fn = BENCHMARKS[benchmark]
    model_spec = resolve_model(model)

    logs = inspect_eval(
        task_fn(),
        model=model_spec,
        log_dir=str(log_dir),
        limit=limit,
    )

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
