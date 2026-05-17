"""Unit tests for Terminal-Bench wiring.

Verifies the inspect_harbor delegation, kwarg forwarding (notably
``dataset_task_names`` filtering), version resolution, and the CLI wiring of
``--harness mini-swe`` / ``--task-names``. We do not run a real TB sample here:
that requires Docker and Harbor Hub pulls; the bead's acceptance run is
covered by ``ahs run --benchmark tb-smoke ...`` outside the unit suite.
"""

from __future__ import annotations

from typing import Any

import inspect_harbor
import pytest
from click.testing import CliRunner
from inspect_ai import Task
from inspect_ai.dataset import Sample

import ahs.benchmarks._terminal_bench as tb_mod
from ahs.benchmarks import tb_version
from ahs.runner import cli


def _empty_task() -> Task:
    """Minimal real Task — the @task decorator on our wrappers requires a real Task back."""
    return Task(dataset=[Sample(input="x", target="x")])


class _CapturedKwargs:
    """Sentinel factory: records kwargs and returns a real Task placeholder."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.task = _empty_task()

    def __call__(self, **kwargs: Any) -> Task:
        self.calls.append(kwargs)
        return self.task


@pytest.fixture
def fake_tb_factory(monkeypatch: pytest.MonkeyPatch) -> _CapturedKwargs:
    """Replace inspect_harbor.terminal_bench_2_1 with a kwarg-capturing fake.

    This lets us test that our wrappers forward filter args correctly without
    talking to Docker / Harbor Hub.
    """
    fake = _CapturedKwargs()
    monkeypatch.setattr(inspect_harbor, "terminal_bench_2_1", fake, raising=True)
    return fake


def test_tb_version_is_2_1() -> None:
    assert tb_version() == "2.1"


def test_resolve_falls_back_to_2_0_when_2_1_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_20 = _CapturedKwargs()
    monkeypatch.delattr(inspect_harbor, "terminal_bench_2_1", raising=False)
    monkeypatch.setattr(inspect_harbor, "terminal_bench_2", fake_20, raising=False)
    label, factory = tb_mod._resolve_tb_factory()
    assert label == "2.0"
    assert factory is fake_20


def test_resolve_raises_when_neither_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(inspect_harbor, "terminal_bench_2_1", raising=False)
    monkeypatch.delattr(inspect_harbor, "terminal_bench_2", raising=False)
    with pytest.raises(RuntimeError, match="inspect_harbor"):
        tb_mod._resolve_tb_factory()


def test_tb_task_forwards_filter_args(fake_tb_factory: _CapturedKwargs) -> None:
    """The internal _tb_task helper passes all filter args through to inspect_harbor."""
    tb_mod._tb_task(
        dataset_task_names=["hello-world", "fs-*"],
        dataset_exclude_task_names=["broken-task"],
        n_tasks=10,
        ref="v2.1.0",
        sandbox_env_name="docker",
    )
    assert len(fake_tb_factory.calls) == 1
    call = fake_tb_factory.calls[0]
    assert call["dataset_task_names"] == ["hello-world", "fs-*"]
    assert call["dataset_exclude_task_names"] == ["broken-task"]
    assert call["n_tasks"] == 10
    assert call["ref"] == "v2.1.0"
    assert call["sandbox_env_name"] == "docker"


def test_tb2_smoke_defaults_to_n_tasks_5(fake_tb_factory: _CapturedKwargs) -> None:
    # Call the underlying helper as tb2_smoke would, to inspect kwarg behavior.
    tb_mod._tb_task(n_tasks=tb_mod.DEFAULT_TB_SMOKE_TASK_LIMIT)
    assert len(fake_tb_factory.calls) == 1
    assert fake_tb_factory.calls[0]["n_tasks"] == 5


def test_cli_run_command_lists_tb_smoke_and_tb() -> None:
    """Both new benchmarks must be selectable from the CLI's --benchmark choices."""
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0, result.output
    assert "tb-smoke" in result.output
    assert " tb" in result.output or "[smoke|tb|tb-smoke]" in result.output
    assert "mini-swe" in result.output


def test_cli_rejects_task_names_for_non_harbor_benchmark(
    fake_tb_factory: _CapturedKwargs,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--benchmark",
            "smoke",
            "--model",
            "mockllm/model",
            "--task-names",
            "anything",
        ],
    )
    assert result.exit_code != 0
    assert "--task-names" in result.output


def test_cli_wires_harness_and_task_names_into_eval(
    fake_tb_factory: _CapturedKwargs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end CLI wiring: --benchmark tb-smoke + --harness mini-swe + --task-names
    must call our task factory with the right kwargs and pass a solver to inspect_eval.
    """
    eval_calls: list[dict[str, Any]] = []

    class _FakeLog:
        status = "success"

    def fake_eval(task: Any, **kwargs: Any) -> list[Any]:
        eval_calls.append({"task": task, **kwargs})
        return [_FakeLog()]

    monkeypatch.setattr("inspect_ai.eval", fake_eval)

    sentinel_agent = object()
    monkeypatch.setattr("ahs.runner.resolve_harness", lambda name: sentinel_agent)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--benchmark",
            "tb-smoke",
            "--model",
            "haiku45",
            "--harness",
            "mini-swe",
            "--task-names",
            "hello-world",
            "--task-names",
            "fs-*",
        ],
    )
    assert result.exit_code == 0, result.output

    # task factory got our filter args
    assert len(fake_tb_factory.calls) == 1
    assert fake_tb_factory.calls[0]["dataset_task_names"] == ["hello-world", "fs-*"]
    # smoke default n_tasks is suppressed once explicit task names are passed
    assert fake_tb_factory.calls[0]["n_tasks"] is None

    # inspect_eval got the resolved model, solver, and our fake task object
    assert len(eval_calls) == 1
    call = eval_calls[0]
    assert call["model"] == "anthropic/claude-haiku-4-5"
    assert call["solver"] is sentinel_agent
    assert isinstance(call["task"], Task)
