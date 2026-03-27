"""Abstract base class for benchmark scenarios."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agent_harness_suite.config import Settings
from agent_harness_suite.harnesses.base import HarnessAdapter


class Scenario(ABC):
    """A benchmark scenario defines the task agents must perform.

    Scenarios orchestrate one or more agent invocations and produce
    structured output that can be compared across harnesses.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this scenario."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this scenario tests."""

    @abstractmethod
    def execute(
        self,
        harness: HarnessAdapter,
        repo_url: str,
        settings: Settings,
    ) -> dict[str, Any]:
        """Run the scenario using the given harness.

        Args:
            harness: The agent harness adapter to use.
            repo_url: Target GitHub repository URL.
            settings: Application settings.

        Returns:
            Dict of scenario-specific results.
        """
