"""Metrics collector for benchmark runs.

Collects per-run metrics including tokens, turns, agents spawned, wall-clock time,
and harness-specific metadata. Full implementation in ahs-3hn.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkMetrics:
    """Collected metrics for a single benchmark run."""

    harness: str
    scenario: str
    repo_url: str
    wall_clock_seconds: float = 0.0
    total_tokens: int | None = None
    total_turns: int | None = None
    spawned_agents: int | None = None
    status: str = "pending"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics to a dict."""
        return {
            "harness": self.harness,
            "scenario": self.scenario,
            "repo_url": self.repo_url,
            "wall_clock_seconds": self.wall_clock_seconds,
            "total_tokens": self.total_tokens,
            "total_turns": self.total_turns,
            "spawned_agents": self.spawned_agents,
            "status": self.status,
            **self.extra,
        }
