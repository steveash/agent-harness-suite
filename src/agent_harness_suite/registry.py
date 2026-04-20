"""Adapter registry for discoverable harness backends.

New adapters register via :func:`register_adapter` or by adding an entry
to :data:`BUILTIN_ADAPTERS`.  The benchmark runner resolves adapters by
name through this registry.
"""

from __future__ import annotations

from collections.abc import Callable

from .adapter import HarnessAdapter

# adapter name → factory callable (no-arg, returns HarnessAdapter instance)
_REGISTRY: dict[str, Callable[[], HarnessAdapter]] = {}


def register_adapter(name: str, factory: Callable[[], HarnessAdapter]) -> None:
    """Register an adapter factory under *name*.

    Raises :class:`ValueError` if the name is already taken.
    """
    if name in _REGISTRY:
        raise ValueError(f"Adapter '{name}' is already registered")
    _REGISTRY[name] = factory


def get_adapter(name: str) -> HarnessAdapter:
    """Instantiate and return the adapter registered under *name*."""
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown adapter '{name}'. Available: {available}")
    return _REGISTRY[name]()


def list_adapters() -> list[str]:
    """Return sorted list of registered adapter names."""
    return sorted(_REGISTRY)


def _register_builtins() -> None:
    """Lazily register built-in adapters."""
    from .adapters.claude_agent import ClaudeAgentAdapter
    from .adapters.copilot import CopilotAdapter

    for cls in (ClaudeAgentAdapter, CopilotAdapter):
        adapter = cls()
        if adapter.name not in _REGISTRY:
            register_adapter(adapter.name, cls)


_register_builtins()
