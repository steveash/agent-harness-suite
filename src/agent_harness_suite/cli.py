"""CLI entrypoint for Agent Harness Suite."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

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
    from agent_harness_suite.scenarios import get_scenario

    sc = get_scenario(scenario)
    exit_code = 0
    for h in harness:
        adapter = get_harness(h, settings)
        console.print(f"[bold]--- {h} ---[/bold]")
        try:
            result = asyncio.run(sc.execute(adapter, repo_url, settings))
        except Exception as exc:
            console.print(f"[red]Harness '{h}' failed: {exc}[/red]")
            exit_code = 1
            continue
        _render_repo_to_plan(result)

    if exit_code:
        sys.exit(exit_code)


def _get_version() -> str:
    from agent_harness_suite import __version__
    return __version__


def _render_repo_to_plan(result: dict[str, Any]) -> None:
    """Pretty-print a repo-to-plan scenario result."""
    feature = result.get("feature") or {}
    metrics = result.get("metrics") or {}
    tasks = result.get("tasks") or []

    console.print(f"[bold]Feature:[/bold] {feature.get('title', '(none)')}")
    rationale = feature.get("rationale", "")
    if rationale:
        console.print(f"[dim]{rationale}[/dim]")

    console.print(f"[bold]Tasks:[/bold] {len(tasks)}")
    for task in tasks:
        deps = ", ".join(task.get("depends_on") or []) or "-"
        console.print(f"  {task.get('id')}: {task.get('title')} [dim](deps: {deps})[/dim]")

    console.print(
        f"[bold]Metrics:[/bold] tokens={metrics.get('total_tokens', 0)} "
        f"turns={metrics.get('total_turns', 0)} "
        f"spawned={metrics.get('spawned_agents', 0)}"
    )


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
