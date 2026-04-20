"""Tests for the harness adapter abstraction layer."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from agent_harness_suite.adapter import HarnessAdapter
from agent_harness_suite.registry import get_adapter, list_adapters, register_adapter
from agent_harness_suite.runner import BenchmarkRunner
from agent_harness_suite.types import (
    EventKind,
    LifecycleEvent,
    RunMetrics,
    RunResult,
    RunStatus,
    ScenarioConfig,
)

# ------------------------------------------------------------------
# Stub adapter for testing
# ------------------------------------------------------------------


class StubAdapter(HarnessAdapter):
    """Minimal adapter that returns canned results for testing."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self._setup_called = False
        self._teardown_called = False

    @property
    def name(self) -> str:
        return "stub"

    async def setup(self, config: dict[str, Any]) -> None:
        self._setup_called = True

    async def teardown(self) -> None:
        self._teardown_called = True

    async def run(self, scenario: ScenarioConfig) -> RunResult:
        events = [
            LifecycleEvent(kind=EventKind.RUN_STARTED),
            LifecycleEvent(kind=EventKind.TURN_STARTED, data={"turn": 0}),
            LifecycleEvent(kind=EventKind.TURN_COMPLETED, data={"turn": 0}),
            LifecycleEvent(kind=EventKind.RUN_COMPLETED),
        ]
        metrics = RunMetrics(
            wall_clock_seconds=1.23,
            total_turns=1,
            total_input_tokens=100,
            total_output_tokens=50,
        )

        if self._fail:
            return RunResult(
                status=RunStatus.FAILURE,
                metrics=metrics,
                events=events,
                adapter_name=self.name,
                scenario_name=scenario.name,
                error_message="Stubbed failure",
            )

        return RunResult(
            status=RunStatus.SUCCESS,
            metrics=metrics,
            events=events,
            output="Stub output",
            adapter_name=self.name,
            scenario_name=scenario.name,
        )

    async def stream_events(  # type: ignore[override]
        self, scenario: ScenarioConfig
    ) -> AsyncIterator[LifecycleEvent]:
        yield LifecycleEvent(kind=EventKind.RUN_STARTED)
        yield LifecycleEvent(kind=EventKind.RUN_COMPLETED)

    def supported_features(self) -> set[str]:
        return {"streaming", "tool_use"}


# ------------------------------------------------------------------
# Type tests
# ------------------------------------------------------------------


class TestTypes:
    def test_event_kind_values(self):
        assert EventKind.RUN_STARTED == "run_started"
        assert EventKind.RUN_COMPLETED == "run_completed"

    def test_run_status_values(self):
        assert RunStatus.SUCCESS == "success"
        assert RunStatus.TIMEOUT == "timeout"

    def test_lifecycle_event_defaults(self):
        event = LifecycleEvent(kind=EventKind.RUN_STARTED)
        assert event.agent_id is None
        assert event.data == {}
        assert event.timestamp > 0

    def test_run_metrics_defaults(self):
        m = RunMetrics()
        assert m.wall_clock_seconds == 0.0
        assert m.total_turns == 0
        assert m.custom == {}

    def test_scenario_config(self):
        sc = ScenarioConfig(name="test", prompt="Hello")
        assert sc.timeout_seconds == 300.0
        assert sc.params == {}


# ------------------------------------------------------------------
# Adapter protocol tests
# ------------------------------------------------------------------


class TestStubAdapter:
    @pytest.fixture
    def adapter(self) -> StubAdapter:
        return StubAdapter()

    @pytest.fixture
    def scenario(self) -> ScenarioConfig:
        return ScenarioConfig(name="basic", prompt="Do something")

    async def test_setup_teardown(self, adapter: StubAdapter):
        await adapter.setup({})
        assert adapter._setup_called
        await adapter.teardown()
        assert adapter._teardown_called

    async def test_run_success(self, adapter: StubAdapter, scenario: ScenarioConfig):
        await adapter.setup({})
        result = await adapter.run(scenario)
        assert result.status == RunStatus.SUCCESS
        assert result.output == "Stub output"
        assert result.adapter_name == "stub"
        assert result.scenario_name == "basic"
        assert result.metrics.total_turns == 1
        assert result.metrics.total_input_tokens == 100

    async def test_run_failure(self, scenario: ScenarioConfig):
        adapter = StubAdapter(fail=True)
        await adapter.setup({})
        result = await adapter.run(scenario)
        assert result.status == RunStatus.FAILURE
        assert result.error_message == "Stubbed failure"

    async def test_stream_events(self, adapter: StubAdapter, scenario: ScenarioConfig):
        events = []
        async for event in adapter.stream_events(scenario):
            events.append(event)
        assert len(events) == 2
        assert events[0].kind == EventKind.RUN_STARTED
        assert events[1].kind == EventKind.RUN_COMPLETED

    def test_supported_features(self, adapter: StubAdapter):
        features = adapter.supported_features()
        assert "streaming" in features
        assert "tool_use" in features


# ------------------------------------------------------------------
# Runner tests
# ------------------------------------------------------------------


class TestBenchmarkRunner:
    @pytest.fixture
    def runner(self) -> BenchmarkRunner:
        r = BenchmarkRunner()
        r.register(StubAdapter())
        return r

    @pytest.fixture
    def scenario(self) -> ScenarioConfig:
        return ScenarioConfig(name="basic", prompt="Do something")

    def test_register_duplicate_raises(self, runner: BenchmarkRunner):
        with pytest.raises(ValueError, match="already registered"):
            runner.register(StubAdapter())

    def test_adapter_names(self, runner: BenchmarkRunner):
        assert runner.adapter_names == ["stub"]

    async def test_setup_teardown(self, runner: BenchmarkRunner):
        await runner.setup_all()
        adapter = runner.get_adapter("stub")
        assert isinstance(adapter, StubAdapter)
        assert adapter._setup_called
        await runner.teardown_all()
        assert adapter._teardown_called

    async def test_run_scenario(self, runner: BenchmarkRunner, scenario: ScenarioConfig):
        await runner.setup_all()
        result = await runner.run_scenario("stub", scenario)
        assert result.status == RunStatus.SUCCESS

    async def test_run_all(self, runner: BenchmarkRunner, scenario: ScenarioConfig):
        await runner.setup_all()
        results = await runner.run_all([scenario])
        assert len(results) == 1
        assert results[0].status == RunStatus.SUCCESS

    async def test_run_all_parallel(self, runner: BenchmarkRunner):
        await runner.setup_all()
        scenarios = [
            ScenarioConfig(name="s1", prompt="A"),
            ScenarioConfig(name="s2", prompt="B"),
        ]
        results = await runner.run_all(scenarios, parallel=True)
        assert len(results) == 2
        assert all(r.status == RunStatus.SUCCESS for r in results)

    async def test_missing_features_skips(self, runner: BenchmarkRunner):
        await runner.setup_all()
        scenario = ScenarioConfig(
            name="needs_sub_agents",
            prompt="Spawn agents",
            params={"required_features": ["sub_agents"]},
        )
        result = await runner.run_scenario("stub", scenario)
        assert result.status == RunStatus.ERROR
        assert "missing required features" in result.error_message


# ------------------------------------------------------------------
# Registry tests
# ------------------------------------------------------------------


class TestRegistry:
    def test_builtins_registered(self):
        names = list_adapters()
        assert "claude" in names
        assert "copilot" in names

    def test_get_adapter(self):
        adapter = get_adapter("claude")
        assert adapter.name == "claude"

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown adapter"):
            get_adapter("nonexistent")

    def test_register_duplicate_raises(self):
        with pytest.raises(ValueError, match="already registered"):
            register_adapter("claude", lambda: StubAdapter())
