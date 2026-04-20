"""Core types for the agent harness suite."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventKind(StrEnum):
    """Normalized lifecycle events emitted by any harness adapter."""

    RUN_STARTED = "run_started"
    TURN_STARTED = "turn_started"
    TURN_COMPLETED = "turn_completed"
    AGENT_SPAWNED = "agent_spawned"
    AGENT_COMPLETED = "agent_completed"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    RUN_COMPLETED = "run_completed"


class RunStatus(StrEnum):
    """Terminal status of a harness run."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class LifecycleEvent:
    """A single normalized lifecycle event from a harness run.

    All adapters emit these regardless of the underlying SDK's native event
    model, giving the benchmark runner a uniform stream to observe.
    """

    kind: EventKind
    timestamp: float = field(default_factory=time.time)
    agent_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunMetrics:
    """Aggregated metrics collected during a single benchmark run.

    Adapters populate whichever fields their SDK exposes. Fields left at
    their defaults indicate the SDK does not provide that metric.
    """

    wall_clock_seconds: float = 0.0
    total_turns: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_agents_spawned: int = 0
    tool_calls: int = 0
    errors: int = 0
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """The normalized output of a single harness run."""

    status: RunStatus
    metrics: RunMetrics
    events: list[LifecycleEvent]
    output: Any = None
    error_message: str | None = None
    adapter_name: str = ""
    scenario_name: str = ""


@dataclass
class ScenarioConfig:
    """Configuration for a single benchmark scenario.

    A scenario defines *what* to execute; the adapter defines *how* to
    execute it via a particular agent harness.
    """

    name: str
    prompt: str
    repo_url: str | None = None
    repo_path: str | None = None
    timeout_seconds: float = 300.0
    params: dict[str, Any] = field(default_factory=dict)
