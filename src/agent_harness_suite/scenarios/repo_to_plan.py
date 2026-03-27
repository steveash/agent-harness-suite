"""Repo-to-plan scenario: analyze a repo and produce a feature proposal with implementation plan."""

from __future__ import annotations

from typing import Any

from agent_harness_suite.config import Settings
from agent_harness_suite.harnesses.base import HarnessAdapter
from agent_harness_suite.scenarios.base import Scenario


class RepoToPlanScenario(Scenario):
    """Benchmark scenario: given a repo, research it and produce a feature proposal.

    This is the primary v1 benchmark use case. The agent must:
    1. Analyze the repository structure and code.
    2. Propose a strong next feature.
    3. Produce a detailed implementation plan with task decomposition.

    Full implementation in ahs-3hn.3.
    """

    @property
    def name(self) -> str:
        return "repo-to-plan"

    @property
    def description(self) -> str:
        return (
            "Analyze a GitHub repo, propose a next feature, "
            "and produce an implementation plan with task decomposition."
        )

    def execute(
        self,
        harness: HarnessAdapter,
        repo_url: str,
        settings: Settings,
    ) -> dict[str, Any]:
        """Execute the repo-to-plan scenario.

        Full implementation will be completed in ahs-3hn.3.
        """
        raise NotImplementedError(
            "repo-to-plan scenario not yet implemented. See ahs-3hn.3."
        )
