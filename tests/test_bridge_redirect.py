"""Smoke test #1 — bridge redirect.

Asserts that when ``sandbox_agent_bridge()`` is active, the harness's HTTP
requests to ``ANTHROPIC_BASE_URL`` hit ``localhost:{bridge.port}`` and NOT
``api.anthropic.com``. The fake harness binary in ``_smoke.py`` records both the
configured base URL and the HTTP status code from a real round-trip; this test
inspects those metadata fields.
"""

from __future__ import annotations

from inspect_ai.log import EvalLog


def test_anthropic_base_url_points_at_bridge(smoke_log: EvalLog) -> None:
    assert smoke_log.samples is not None
    sample = smoke_log.samples[0]
    base_url = sample.metadata["bridge_base_url"]
    port = sample.metadata["bridge_port"]

    assert base_url == f"http://localhost:{port}", (
        f"expected base_url=http://localhost:{port}, got {base_url}"
    )

    stdout = sample.metadata["harness_stdout"]
    assert f"ANTHROPIC_BASE_URL=http://localhost:{port}" in stdout, (
        f"fake harness did not see localhost base_url; stdout={stdout!r}"
    )
    assert "api.anthropic.com" not in stdout, (
        f"fake harness saw api.anthropic.com; stdout={stdout!r}"
    )


def test_bridge_actually_served_the_request(smoke_log: EvalLog) -> None:
    """The bridge proxy must accept and respond to the request — otherwise the
    'redirect' is vacuous (it could be pointing at localhost with nothing
    listening). Require HTTP_CODE=200 from the fake harness.
    """
    assert smoke_log.samples is not None
    sample = smoke_log.samples[0]
    stdout = sample.metadata["harness_stdout"]
    assert "HTTP_CODE=200" in stdout, (
        f"bridge did not return 200 to the fake harness; stdout={stdout!r} "
        f"stderr={sample.metadata.get('harness_stderr')!r}"
    )
