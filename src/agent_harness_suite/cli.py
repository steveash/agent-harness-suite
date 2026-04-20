"""CLI entrypoint for Agent Harness Suite."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from agent_harness_suite.config import load_settings

console = Console()


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), default=None)
@click.pass_context
def main(ctx: click.Context, config: Path | None) -> None:
    """Agent Harness Suite - benchmark multi-agent coding harnesses."""
    settings = load_settings(config)
    _setup_logging(settings.log_level)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings


@main.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show current configuration and available harnesses."""
    settings = ctx.obj["settings"]
    console.print("[bold]Agent Harness Suite[/bold]", f"v{_get_version()}")
    console.print()
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Log level:    {settings.log_level}")
    console.print(f"  Results dir:  {settings.results_dir}")
    console.print()
    console.print("[bold]Harnesses:[/bold]")
    console.print(f"  Claude:  {'enabled' if settings.claude.enabled else 'disabled'}"
                  f" (model: {settings.claude.model})")
    console.print(f"  Copilot: {'enabled' if settings.copilot.enabled else 'disabled'}"
                  f" (model: {settings.copilot.model})")
    console.print()
    _check_keys(settings)


@main.command()
@click.argument("repo_url")
@click.option("--harness", "-h", multiple=True, default=["claude"],
              help="Harness(es) to run (claude, copilot). Can be specified multiple times.")
@click.option("--scenario", "-s", default="repo-to-plan",
              help="Scenario to run (default: repo-to-plan).")
@click.pass_context
def run(ctx: click.Context, repo_url: str, harness: tuple[str, ...], scenario: str) -> None:
    """Run a benchmark scenario against a GitHub repo.

    REPO_URL is the GitHub repository to analyze.
    """
    settings = ctx.obj["settings"]
    _check_keys(settings, fatal=True)

    console.print(f"[bold]Running scenario:[/bold] {scenario}")
    console.print(f"[bold]Target repo:[/bold]     {repo_url}")
    console.print(f"[bold]Harnesses:[/bold]       {', '.join(harness)}")
    console.print()

    import asyncio

    from agent_harness_suite.harnesses import get_harness
    from agent_harness_suite.metrics import (
        BenchmarkReport,
        default_output_paths,
        render_summary,
        write_json,
        write_text_summary,
    )
    from agent_harness_suite.runner import BenchmarkRunner
    from agent_harness_suite.scenarios import get_scenario
    from agent_harness_suite.types import ScenarioConfig

    runner = BenchmarkRunner()
    for h in harness:
        adapter = get_harness(h, settings)
        runner.register(adapter)

    sc = get_scenario(scenario)
    scenario_cfg = ScenarioConfig(name=sc.name, prompt=sc.description, repo_url=repo_url)

    report = BenchmarkReport(
        metadata={
            "repo_url": repo_url,
            "scenario": scenario,
            "harnesses": list(harness),
        }
    )
    run_results = asyncio.run(_run_benchmark(runner, [scenario_cfg], list(harness)))
    for r in run_results:
        report.add(r)
    report.finalize()

    if not run_results:
        console.print("[red]No results produced.[/red]")
        sys.exit(1)

    render_summary(report, console=console)

    json_path, txt_path = default_output_paths(settings.results_dir, report.started_at)
    write_json(report, json_path)
    write_text_summary(report, txt_path)
    console.print(f"[dim]Wrote results to[/dim] {json_path}")
    console.print(f"[dim]Wrote summary to[/dim] {txt_path}")


def _get_version() -> str:
    from agent_harness_suite import __version__
    return __version__


async def _run_benchmark(runner, scenarios, adapter_names):
    """Run benchmark scenarios asynchronously."""
    await runner.setup_all()
    try:
        return await runner.run_all(scenarios, adapter_names=adapter_names)
    finally:
        await runner.teardown_all()


def _check_keys(settings: object, fatal: bool = False) -> None:
    """Check that required API keys are configured."""
    from agent_harness_suite.config import Settings
    assert isinstance(settings, Settings)

    missing = []
    if not settings.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")
    if not settings.github_token:
        missing.append("GITHUB_TOKEN")

    if missing:
        msg = f"Missing API keys: {', '.join(missing)} — set in .env or environment"
        if fatal:
            console.print(f"[red]{msg}[/red]")
            sys.exit(1)
        else:
            console.print(f"  [yellow]Warning:[/yellow] {msg}")
