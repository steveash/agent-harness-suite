"""End-to-end tests for the primary repo-to-plan benchmark flow.

These tests exercise the full wiring — CLI → settings → registry → runner →
adapter → metrics — using a stub harness so the suite can be validated offline
without API keys or network access. Real harness adapters (Claude, Copilot)
still require their respective SDKs and credentials; those paths are covered
by manual verification documented in README.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from click.testing import CliRunner

from agent_harness_suite.adapter import HarnessAdapter
from agent_harness_suite.cli import main
from agent_harness_suite.config import Settings
from agent_harness_suite.harnesses import get_harness
from agent_harness_suite.harnesses.base import AgentResult
from agent_harness_suite.harnesses.base import HarnessAdapter as SettingsHarness
from agent_harness_suite.runner import BenchmarkRunner
from agent_harness_suite.scenarios import get_scenario
from agent_harness_suite.types import (
    EventKind,
    LifecycleEvent,
    RunMetrics,
    RunResult,
    RunStatus,
    ScenarioConfig,
)

# ------------------------------------------------------------------
# Stub adapters — exercise the wiring without hitting external SDKs
# ------------------------------------------------------------------


class _StubSettingsHarness(SettingsHarness):
    """Settings-based harness stub. Used to exercise the CLI → runner flow."""

    _expected_prompt: str | None = None
    _invoke_calls: int = 0
    _last_context: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return "stub-settings"

    async def invoke(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> AgentResult:
        type(self)._invoke_calls += 1
        type(self)._last_context = context
        return AgentResult(
            output=f"stubbed-plan-for:{prompt[:20]}",
            total_tokens=123,
            total_turns=4,
            spawned_agents=2,
        )


class _RawAdapter(HarnessAdapter):
    """Core protocol adapter that records setup/teardown for the runner test."""

    def __init__(self) -> None:
        self.setup_called = False
        self.teardown_called = False

    @property
    def name(self) -> str:
        return "raw-stub"

    async def setup(self, config: dict[str, Any]) -> None:
        self.setup_called = True

    async def teardown(self) -> None:
        self.teardown_called = True

    async def run(self, scenario: ScenarioConfig) -> RunResult:
        return RunResult(
            status=RunStatus.SUCCESS,
            metrics=RunMetrics(wall_clock_seconds=0.5, total_turns=1),
            events=[LifecycleEvent(kind=EventKind.RUN_COMPLETED)],
            output="ok",
            adapter_name=self.name,
            scenario_name=scenario.name,
        )

    async def stream_events(  # type: ignore[override]
        self, scenario: ScenarioConfig
    ) -> AsyncIterator[LifecycleEvent]:
        yield LifecycleEvent(kind=EventKind.RUN_STARTED)
        yield LifecycleEvent(kind=EventKind.RUN_COMPLETED)

    def supported_features(self) -> set[str]:
        return set()


# ------------------------------------------------------------------
# End-to-end: Settings-based harness through the scenario + runner
# ------------------------------------------------------------------


class TestSettingsHarnessFlow:
    """Exercise the full path: registry → scenario → runner → metrics."""

    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(anthropic_api_key="stub", github_token="stub")

    @pytest.fixture(autouse=True)
    def _register_stub(self) -> None:
        # Force built-in registration (lazy-load triggers on first get),
        # then register the stub alongside them.
        from agent_harness_suite.harnesses import _REGISTRY, _load_builtins

        if "claude" not in _REGISTRY:
            _load_builtins()
        _REGISTRY["stub-settings"] = _StubSettingsHarness
        _StubSettingsHarness._invoke_calls = 0
        _StubSettingsHarness._last_context = None

    async def test_repo_to_plan_scenario_is_discoverable(self) -> None:
        scenario = get_scenario("repo-to-plan")
        assert scenario.name == "repo-to-plan"
        assert "repo" in scenario.description.lower()

    async def test_full_flow_produces_success_result(
        self, settings: Settings
    ) -> None:
        adapter = get_harness("stub-settings", settings)
        scenario = get_scenario("repo-to-plan")

        runner = BenchmarkRunner()
        runner.register(adapter)
        await runner.setup_all()
        try:
            scenario_cfg = ScenarioConfig(
                name=scenario.name,
                prompt=scenario.description,
                repo_url="https://github.com/example/repo",
            )
            results = await runner.run_all([scenario_cfg])
        finally:
            await runner.teardown_all()

        assert len(results) == 1
        result = results[0]
        assert result.status == RunStatus.SUCCESS
        assert result.adapter_name == "stub-settings"
        assert result.scenario_name == "repo-to-plan"
        assert result.output and "stubbed-plan-for" in result.output
        # Metrics propagate from AgentResult.
        assert result.metrics.total_turns == 4
        assert result.metrics.total_input_tokens == 123
        assert result.metrics.total_agents_spawned == 2
        assert result.metrics.wall_clock_seconds > 0

    async def test_repo_url_reaches_adapter_context(
        self, settings: Settings
    ) -> None:
        adapter = get_harness("stub-settings", settings)
        scenario_cfg = ScenarioConfig(
            name="repo-to-plan",
            prompt="analyze",
            repo_url="https://github.com/owner/target",
        )
        runner = BenchmarkRunner()
        runner.register(adapter)
        await runner.setup_all()
        try:
            await runner.run_all([scenario_cfg])
        finally:
            await runner.teardown_all()

        assert _StubSettingsHarness._last_context is not None
        assert (
            _StubSettingsHarness._last_context["repo_url"]
            == "https://github.com/owner/target"
        )

    async def test_unimplemented_harness_surfaces_as_error_result(
        self, settings: Settings
    ) -> None:
        # Built-in Claude/Copilot harnesses raise NotImplementedError until
        # ahs-3hn.2 lands; the runner must still produce a structured result.
        adapter = get_harness("claude", settings)
        scenario_cfg = ScenarioConfig(
            name="repo-to-plan",
            prompt="x",
            repo_url="https://github.com/example/repo",
        )
        runner = BenchmarkRunner()
        runner.register(adapter)
        await runner.setup_all()
        try:
            results = await runner.run_all([scenario_cfg])
        finally:
            await runner.teardown_all()

        assert results[0].status == RunStatus.ERROR
        assert results[0].error_message is not None
        assert results[0].metrics.errors == 1


# ------------------------------------------------------------------
# End-to-end: core-adapter protocol through the runner
# ------------------------------------------------------------------


class TestRunnerLifecycle:
    async def test_setup_run_teardown_sequence(self) -> None:
        adapter = _RawAdapter()
        runner = BenchmarkRunner()
        runner.register(adapter)

        await runner.setup_all()
        assert adapter.setup_called

        results = await runner.run_all(
            [ScenarioConfig(name="demo", prompt="hi")],
        )
        assert [r.status for r in results] == [RunStatus.SUCCESS]

        await runner.teardown_all()
        assert adapter.teardown_called


# ------------------------------------------------------------------
# End-to-end: CLI surface
# ------------------------------------------------------------------


class TestCli:
    def test_info_command_lists_harnesses(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["info"], env={"ANTHROPIC_API_KEY": "x", "GITHUB_TOKEN": "y"})
        assert result.exit_code == 0, result.output
        assert "Claude" in result.output
        assert "Copilot" in result.output

    def test_info_warns_when_keys_missing(self) -> None:
        runner = CliRunner()
        # Explicit empty env overrides any real shell exports.
        result = runner.invoke(main, ["info"], env={"ANTHROPIC_API_KEY": "", "GITHUB_TOKEN": ""})
        assert result.exit_code == 0
        assert "Missing API keys" in result.output

    def test_run_fails_fast_without_keys(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", "https://github.com/example/repo"],
            env={"ANTHROPIC_API_KEY": "", "GITHUB_TOKEN": ""},
        )
        assert result.exit_code == 1
        assert "Missing API keys" in result.output

    def test_run_unknown_harness_raises(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", "https://github.com/example/repo", "--harness", "bogus"],
            env={"ANTHROPIC_API_KEY": "x", "GITHUB_TOKEN": "y"},
        )
        # Unknown harness causes an exception before run_all is reached.
        assert result.exit_code != 0
        assert result.exception is not None
