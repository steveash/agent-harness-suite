"""Shared pytest fixtures.

The smoke eval is expensive (sandbox + bridge proxy) and both smoke tests need
the same EvalLog, so we run it once per session and share the resulting log.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import EvalLog

from ahs.benchmarks import smoke


@pytest.fixture(scope="session")
def smoke_log(tmp_path_factory: pytest.TempPathFactory) -> EvalLog:
    """Run the smoke benchmark once through the bridge and yield the eval log.

    We pin the model to ``mockllm/model`` so the test does not need network or
    API keys — the bridge still translates Anthropic-format requests through
    the proxy and the mock provider produces real token-usage numbers.
    """
    log_dir: Path = tmp_path_factory.mktemp("ahs-smoke-eval")
    logs = inspect_eval(smoke(), model="mockllm/model", log_dir=str(log_dir))
    assert len(logs) == 1, f"expected one EvalLog, got {len(logs)}"
    log = logs[0]
    assert log.status == "success", f"smoke eval failed: {log.error}"
    assert log.samples and len(log.samples) == 1
    return log
