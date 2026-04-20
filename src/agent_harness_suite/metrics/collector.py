"""Metrics collection and aggregation for benchmark runs.

Wraps :class:`~agent_harness_suite.types.RunResult` instances into a report
that can be serialized for comparison across harnesses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agent_harness_suite.types import RunResult


@dataclass
class BenchmarkReport:
    """Aggregated results from one benchmark invocation across adapters/scenarios."""

    results: list[RunResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, result: RunResult) -> None:
        self.results.append(result)

    def finalize(self) -> None:
        self.finished_at = time.time()

    @property
    def wall_clock_seconds(self) -> float:
        end = self.finished_at or time.time()
        return max(0.0, end - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "wall_clock_seconds": self.wall_clock_seconds,
            "metadata": self.metadata,
            "runs": [_result_to_dict(r) for r in self.results],
        }


def _result_to_dict(result: RunResult) -> dict[str, Any]:
    m = result.metrics
    return {
        "adapter": result.adapter_name,
        "scenario": result.scenario_name,
        "status": result.status.value,
        "error_message": result.error_message,
        "metrics": {
            "wall_clock_seconds": m.wall_clock_seconds,
            "total_turns": m.total_turns,
            "total_input_tokens": m.total_input_tokens,
            "total_output_tokens": m.total_output_tokens,
            "total_tokens": m.total_input_tokens + m.total_output_tokens,
            "total_agents_spawned": m.total_agents_spawned,
            "tool_calls": m.tool_calls,
            "errors": m.errors,
            "custom": m.custom,
        },
        "event_count": len(result.events),
        "output": _truncate(result.output),
    }


def _truncate(value: Any, limit: int = 2000) -> Any:
    """Stringify and truncate free-form output so serialized reports stay small."""
    if value is None:
        return None
    text = value if isinstance(value, str) else repr(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"... <truncated {len(text) - limit} chars>"
