"""Benchmark scenarios — define what agents are asked to do."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_harness_suite.scenarios.base import Scenario

_REGISTRY: dict[str, type[Scenario]] = {}


def register_scenario(name: str, cls: type[Scenario]) -> None:
    """Register a scenario class by name."""
    _REGISTRY[name] = cls


def get_scenario(name: str) -> Scenario:
    """Instantiate a scenario by name."""
    if not _REGISTRY:
        _load_builtins()
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(f"Unknown scenario: {name!r}. Available: {available}")
    return _REGISTRY[name]()


def _load_builtins() -> None:
    """Lazily load built-in scenarios."""
    from agent_harness_suite.scenarios.repo_to_plan import RepoToPlanScenario

    register_scenario("repo-to-plan", RepoToPlanScenario)
