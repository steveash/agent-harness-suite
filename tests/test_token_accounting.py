"""Smoke test #2 — token accounting.

The load-bearing verification for cost gating. If token usage is not recorded
when an opaque harness drives the model through the bridge, every downstream
cost calculation silently produces zeros. We assert ``total_tokens > 0`` on the
sample's ``model_usage`` after the bridge call.
"""

from __future__ import annotations

from inspect_ai.log import EvalLog


def test_total_tokens_greater_than_zero(smoke_log: EvalLog) -> None:
    assert smoke_log.samples is not None
    sample = smoke_log.samples[0]
    assert sample.model_usage, (
        "model_usage is empty — the bridge did not record any tokens, which "
        "means cost gating will silently produce zeros for this harness."
    )

    total = sum(usage.total_tokens for usage in sample.model_usage.values())
    assert total > 0, (
        f"sum(total_tokens) across models was {total}; model_usage={sample.model_usage}"
    )


def test_input_and_output_tokens_recorded(smoke_log: EvalLog) -> None:
    """Both input and output token counts must be present — a sum > 0 alone
    could mean the bridge only recorded one side of the call."""
    assert smoke_log.samples is not None
    sample = smoke_log.samples[0]
    usages = list(sample.model_usage.values())
    assert usages, "no model_usage entries at all"
    assert sum(u.input_tokens for u in usages) > 0, "no input tokens recorded"
    assert sum(u.output_tokens for u in usages) > 0, "no output tokens recorded"
