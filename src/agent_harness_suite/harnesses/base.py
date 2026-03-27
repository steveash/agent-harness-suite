"""Abstract base class for harness adapters.

Bridges the scaffold's Settings-based harness implementations with the
core adapter protocol defined in adapter.py.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from agent_harness_suite.adapter import HarnessAdapter as _CoreAdapter
from agent_harness_suite.config import Settings
from agent_harness_suite.types import LifecycleEvent, RunResult, RunStatus, ScenarioConfig


@dataclass
class AgentResult:
    """Result from a single agent invocation."""

    output: str
    total_tokens: int | None = None
    total_turns: int | None = None
    spawned_agents: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class HarnessAdapter(_CoreAdapter):
    """Base class for harness adapters that take Settings at init.

    Subclasses implement ``invoke()`` — the simpler single-call interface.
    The core adapter protocol methods (``setup``, ``teardown``, ``run``,
    ``stream_events``, ``supported_features``) are provided with defaults
    that delegate to ``invoke()``.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this harness."""

    @abstractmethod
    async def invoke(self, prompt: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Send a prompt to the agent and return the result."""

    # -- Core adapter protocol defaults ------------------------------------

    async def setup(self, config: dict[str, Any]) -> None:
        """No-op setup by default."""

    async def teardown(self) -> None:
        """No-op teardown by default."""

    async def run(self, scenario: ScenarioConfig) -> RunResult:
        """Execute a scenario by delegating to invoke()."""
        import time

        from agent_harness_suite.types import RunMetrics

        context: dict[str, Any] = {}
        if scenario.repo_url:
            context["repo_url"] = scenario.repo_url
        context.update(scenario.params)

        start = time.monotonic()
        try:
            result = await self.invoke(scenario.prompt, context)
            elapsed = time.monotonic() - start
            return RunResult(
                status=RunStatus.SUCCESS,
                metrics=RunMetrics(
                    wall_clock_seconds=elapsed,
                    total_turns=result.total_turns or 0,
                    total_input_tokens=result.total_tokens or 0,
                    total_agents_spawned=result.spawned_agents or 0,
                ),
                events=[],
                output=result.output,
                adapter_name=self.name,
                scenario_name=scenario.name,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            return RunResult(
                status=RunStatus.ERROR,
                metrics=RunMetrics(wall_clock_seconds=elapsed, errors=1),
                events=[],
                error_message=str(exc),
                adapter_name=self.name,
                scenario_name=scenario.name,
            )

    async def stream_events(self, scenario: ScenarioConfig) -> AsyncIterator[LifecycleEvent]:
        """Default: run the scenario and yield a single RUN_COMPLETED event."""
        from agent_harness_suite.types import EventKind

        result = await self.run(scenario)
        yield LifecycleEvent(kind=EventKind.RUN_COMPLETED, data={"result": result})

    def supported_features(self) -> set[str]:
        """Return empty feature set by default."""
        return set()
