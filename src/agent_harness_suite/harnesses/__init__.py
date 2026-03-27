"""Harness adapters — pluggable backends for different agent SDKs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_harness_suite.config import Settings
    from agent_harness_suite.harnesses.base import HarnessAdapter

_REGISTRY: dict[str, type[HarnessAdapter]] = {}


def register_harness(name: str, cls: type[HarnessAdapter]) -> None:
    """Register a harness adapter class by name."""
    _REGISTRY[name] = cls


def get_harness(name: str, settings: Settings) -> HarnessAdapter:
    """Instantiate a harness adapter by name."""
    if not _REGISTRY:
        _load_builtins()
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise ValueError(f"Unknown harness: {name!r}. Available: {available}")
    return _REGISTRY[name](settings=settings)


def _load_builtins() -> None:
    """Lazily load built-in harness adapters."""
    from agent_harness_suite.harnesses.claude_harness import ClaudeHarness
    from agent_harness_suite.harnesses.copilot_harness import CopilotHarness

    register_harness("claude", ClaudeHarness)
    register_harness("copilot", CopilotHarness)
