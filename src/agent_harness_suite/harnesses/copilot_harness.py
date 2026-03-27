"""GitHub Copilot SDK harness adapter."""

from __future__ import annotations

import logging
from typing import Any

from agent_harness_suite.config import Settings
from agent_harness_suite.harnesses.base import AgentResult, HarnessAdapter

logger = logging.getLogger(__name__)


class CopilotHarness(HarnessAdapter):
    """Harness adapter for the GitHub Copilot SDK."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._model = settings.copilot.model

    @property
    def name(self) -> str:
        return "copilot"

    async def invoke(self, prompt: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Invoke Copilot SDK with the given prompt.

        Implementation will be completed in ahs-3hn.2.
        """
        raise NotImplementedError(
            "Copilot harness invoke() not yet implemented. See ahs-3hn.2."
        )
