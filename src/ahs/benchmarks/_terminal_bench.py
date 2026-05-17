"""Terminal-Bench 2.1 via Meridian's ``inspect_harbor`` adapter.

Exports two Inspect tasks:

* :func:`tb2` — full Terminal-Bench 2.1 pass (89 tasks).
* :func:`tb2_smoke` — small subset for fast iteration / CI smoke runs.

We delegate to ``inspect_harbor.terminal_bench_2_1`` (slug
``terminal-bench/terminal-bench-2-1``) so we get TB tasks as native Inspect
Tasks, complete with per-task scoring, token accounting, and sandbox lifecycle
management.

A defensive runtime check falls back to ``terminal_bench_2`` (slug
``terminal-bench/terminal-bench-2-0``) only if a future ``inspect_harbor``
release ever drops the 2.1 export — we file the follow-up bead in that case.
"""

from __future__ import annotations

import inspect_harbor
from inspect_ai import Task, task


def _resolve_tb_factory() -> tuple[str, object]:
    """Return ``(version_label, factory_callable)`` for the best TB version available."""
    factory = getattr(inspect_harbor, "terminal_bench_2_1", None)
    if factory is not None:
        return "2.1", factory
    factory = getattr(inspect_harbor, "terminal_bench_2", None)
    if factory is not None:
        # If this branch is ever taken, file a follow-up bead and pin to 2.0.
        return "2.0", factory
    raise RuntimeError(
        "inspect_harbor exposes neither terminal_bench_2_1 nor terminal_bench_2; "
        "pin a known-good inspect-harbor version."
    )


def _tb_task(
    *,
    dataset_task_names: list[str] | None = None,
    dataset_exclude_task_names: list[str] | None = None,
    n_tasks: int | None = None,
    ref: str = "latest",
    sandbox_env_name: str = "docker",
) -> Task:
    """Build a Terminal-Bench Inspect ``Task`` via ``inspect_harbor``.

    Args mirror the subset of ``inspect_harbor.terminal_bench_2_1`` we expose;
    ``dataset_task_names`` supports glob patterns and is how callers filter by
    Harbor task ID.
    """
    _, factory = _resolve_tb_factory()
    return factory(  # type: ignore[no-any-return,operator]
        ref=ref,
        dataset_task_names=dataset_task_names,
        dataset_exclude_task_names=dataset_exclude_task_names,
        n_tasks=n_tasks,
        sandbox_env_name=sandbox_env_name,
    )


# Hand-picked easy TB tasks for the smoke profile. Kept small so smoke runs
# complete in <15 min on a single host. Overridable via CLI/config.
DEFAULT_TB_SMOKE_TASK_LIMIT = 5


@task
def tb2(
    dataset_task_names: list[str] | None = None,
    dataset_exclude_task_names: list[str] | None = None,
    n_tasks: int | None = None,
    ref: str = "latest",
    sandbox_env_name: str = "docker",
) -> Task:
    """Terminal-Bench 2.1 — full 89-task pass (by default).

    Set ``n_tasks`` or ``dataset_task_names`` to narrow the dataset.
    """
    return _tb_task(
        dataset_task_names=dataset_task_names,
        dataset_exclude_task_names=dataset_exclude_task_names,
        n_tasks=n_tasks,
        ref=ref,
        sandbox_env_name=sandbox_env_name,
    )


@task
def tb2_smoke(
    dataset_task_names: list[str] | None = None,
    n_tasks: int | None = None,
    ref: str = "latest",
    sandbox_env_name: str = "docker",
) -> Task:
    """Terminal-Bench 2.1 smoke — 5 easy tasks for fast end-to-end verification.

    By default we take the first ``DEFAULT_TB_SMOKE_TASK_LIMIT`` tasks
    deterministically (Harbor orders the dataset). Callers can pin specific
    task IDs via ``dataset_task_names`` (supports glob patterns) — preferred
    once a stable easy-task shortlist is available for TB 2.1.
    """
    if dataset_task_names is None and n_tasks is None:
        n_tasks = DEFAULT_TB_SMOKE_TASK_LIMIT
    return _tb_task(
        dataset_task_names=dataset_task_names,
        n_tasks=n_tasks,
        ref=ref,
        sandbox_env_name=sandbox_env_name,
    )


def tb_version() -> str:
    """Return the Terminal-Bench version label (``"2.1"`` or ``"2.0"``) resolved at runtime."""
    label, _ = _resolve_tb_factory()
    return label
