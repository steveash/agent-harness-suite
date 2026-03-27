"""Claude Agent SDK harness adapter."""

from __future__ import annotations

import logging
from typing import Any

from agent_harness_suite.config import Settings
from agent_harness_suite.harnesses.base import AgentResult, HarnessAdapter

logger = logging.getLogger(__name__)


class ClaudeHarness(HarnessAdapter):
    """Harness adapter for the Claude Agent SDK."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._model = settings.claude.model

    @property
    def name(self) -> str:
        return "claude"

    async def invoke(self, prompt: str, context: dict[str, Any] | None = None) -> AgentResult:
        """Invoke Claude Agent SDK with the given prompt.

        Implementation will be completed in ahs-3hn.2.
        """
        raise NotImplementedError(
            "Claude harness invoke() not yet implemented. See ahs-3hn.2."
        )
