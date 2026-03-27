"""Benchmark runner: executes scenarios across adapters and collects results."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .adapter import HarnessAdapter
from .types import RunResult, RunStatus, ScenarioConfig

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Drives benchmark scenarios across one or more harness adapters.

    Usage::

        runner = BenchmarkRunner()
        runner.register(ClaudeAgentAdapter())
        runner.register(CopilotAdapter())

        results = await runner.run_all(scenarios)
    """

    def __init__(self) -> None:
        self._adapters: dict[str, HarnessAdapter] = {}

    def register(self, adapter: HarnessAdapter) -> None:
        """Register an adapter. Raises if the name collides."""
        if adapter.name in self._adapters:
            raise ValueError(f"Adapter '{adapter.name}' is already registered")
        self._adapters[adapter.name] = adapter

    @property
    def adapter_names(self) -> list[str]:
        return list(self._adapters.keys())

    def get_adapter(self, name: str) -> HarnessAdapter:
        return self._adapters[name]

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    async def setup_all(self, configs: dict[str, dict[str, Any]] | None = None) -> None:
        """Initialize all registered adapters.

        *configs* maps adapter name → adapter-specific config dict.
        """
        configs = configs or {}
        for name, adapter in self._adapters.items():
            logger.info("Setting up adapter: %s", name)
            await adapter.setup(configs.get(name, {}))

    async def teardown_all(self) -> None:
        for name, adapter in self._adapters.items():
            logger.info("Tearing down adapter: %s", name)
            try:
                await adapter.teardown()
            except Exception:
                logger.exception("Error tearing down adapter %s", name)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_scenario(
        self,
        adapter_name: str,
        scenario: ScenarioConfig,
    ) -> RunResult:
        """Run a single scenario on a single adapter."""
        adapter = self._adapters[adapter_name]

        # Check feature requirements
        required_features = set(scenario.params.get("required_features", []))
        supported = adapter.supported_features()
        missing = required_features - supported
        if missing:
            logger.warning(
                "Adapter %s missing features %s for scenario %s — skipping",
                adapter_name,
                missing,
                scenario.name,
            )
            return RunResult(
                status=RunStatus.ERROR,
                metrics=_empty_metrics(),
                events=[],
                adapter_name=adapter_name,
                scenario_name=scenario.name,
                error_message=f"Adapter missing required features: {missing}",
            )

        logger.info("Running scenario '%s' on adapter '%s'", scenario.name, adapter_name)
        return await adapter.run(scenario)

    async def run_all(
        self,
        scenarios: list[ScenarioConfig],
        adapter_names: list[str] | None = None,
        parallel: bool = False,
    ) -> list[RunResult]:
        """Run every scenario on every specified adapter.

        If *adapter_names* is ``None``, all registered adapters are used.
        If *parallel* is ``True``, adapter×scenario pairs run concurrently.
        """
        names = adapter_names or list(self._adapters.keys())
        pairs = [(name, sc) for name in names for sc in scenarios]

        if parallel:
            results = await asyncio.gather(
                *(self.run_scenario(n, sc) for n, sc in pairs),
                return_exceptions=True,
            )
            return [
                r
                if isinstance(r, RunResult)
                else RunResult(
                    status=RunStatus.ERROR,
                    metrics=_empty_metrics(),
                    events=[],
                    error_message=str(r),
                    adapter_name=n,
                    scenario_name=sc.name,
                )
                for (n, sc), r in zip(pairs, results)
            ]
        else:
            results = []
            for name, sc in pairs:
                results.append(await self.run_scenario(name, sc))
            return results


def _empty_metrics():
    from .types import RunMetrics

    return RunMetrics()
