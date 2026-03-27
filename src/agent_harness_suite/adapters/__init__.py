"""Harness adapter implementations."""

from .claude_agent import ClaudeAgentAdapter
from .copilot import CopilotAdapter

__all__ = ["ClaudeAgentAdapter", "CopilotAdapter"]
