"""Named model presets used across benchmarks."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

MODEL_PRESETS: Mapping[str, str] = MappingProxyType(
    {
        "opus47": "anthropic/claude-opus-4-7",
        "sonnet46": "anthropic/claude-sonnet-4-6",
        "haiku45": "anthropic/claude-haiku-4-5",
        "gpt55": "openai/gpt-5.5-2026-04-23",
        "gpt54mini": "openai/gpt-5.4-mini-2026-03-17",
        "gemini25pro": "google/gemini-2.5-pro",
        "gemini25flash": "google/gemini-2.5-flash",
    }
)


def resolve_model(name: str) -> str:
    """Map a preset name (e.g. ``haiku45``) to a fully qualified Inspect model spec.

    Falls through unchanged if ``name`` is already a fully qualified spec (contains ``/``),
    which lets callers pass things like ``mockllm/model`` or ``anthropic/claude-haiku-4-5``
    directly without registering a preset.
    """
    if name in MODEL_PRESETS:
        return MODEL_PRESETS[name]
    if "/" in name:
        return name
    raise KeyError(
        f"Unknown model preset {name!r}; known presets: {sorted(MODEL_PRESETS)}"
    )
