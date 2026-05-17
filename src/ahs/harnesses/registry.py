"""Named harness presets — coding agents that drive a benchmark's sandbox.

Each preset is a zero-arg factory returning an Inspect ``Agent``. The runner
passes the resulting agent to ``inspect_ai.eval(solver=...)``, which overrides
the benchmark Task's default solver — so the same TB Task can be driven by any
harness here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any


def _mini_swe_agent() -> Any:
    from inspect_swe import mini_swe_agent

    return mini_swe_agent()


HARNESS_PRESETS: Mapping[str, Callable[[], Any]] = MappingProxyType(
    {
        # Cheapest reasonable real agent — bash-only, ~100 LOC.
        # Pinned default version per `inspect_swe.mini_swe_agent(version="stable")`.
        "mini-swe": _mini_swe_agent,
    }
)


def resolve_harness(name: str) -> Any:
    """Map a harness preset name (e.g. ``mini-swe``) to an Inspect ``Agent``.

    Raises ``KeyError`` with the list of known presets on miss. There's no
    fall-through to a "fully qualified" form — harnesses are too varied for a
    simple string spec.
    """
    if name in HARNESS_PRESETS:
        return HARNESS_PRESETS[name]()
    raise KeyError(
        f"Unknown harness preset {name!r}; known presets: {sorted(HARNESS_PRESETS)}"
    )
