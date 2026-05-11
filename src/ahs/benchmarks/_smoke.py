"""Trivial smoke benchmark.

The task asks the agent to write ``hello`` to ``/tmp/out`` inside the sandbox. A
"no-op fake harness" — a tiny shell script — is what actually runs inside the
sandbox: it prints the configured Anthropic base URL, issues one ``/v1/messages``
call through the bridge so the model proxy sees real traffic and token usage gets
recorded, then writes ``hello`` to ``/tmp/out``.

This is the smallest end-to-end shape that exercises the load-bearing primitives
of the Inspect AI backbone: sandbox + agent bridge + token accounting + scorer.
"""

from __future__ import annotations

from inspect_ai import Task, task
from inspect_ai.agent import AgentState, sandbox_agent_bridge
from inspect_ai.dataset import Sample
from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import sandbox

FAKE_HARNESS_SCRIPT = r"""#!/bin/sh
set -u

# Echo the configured base URL so the host-side test can verify the redirect.
printf 'ANTHROPIC_BASE_URL=%s\n' "$ANTHROPIC_BASE_URL"

# Make one round-trip through the bridge so model usage gets recorded. The proxy
# may need a moment to bind its port — retry until curl successfully connects.
# The bridge accepts the standard Anthropic /v1/messages endpoint and routes to
# whichever Inspect model is configured (use "inspect" to mean "current model").
payload='{"model":"inspect","max_tokens":32,"messages":[{"role":"user","content":"say hello"}]}'
attempt=0
http_code=000
while [ "$attempt" -lt 60 ]; do
    attempt=$((attempt + 1))
    if curl --silent --show-error \
        --max-time 10 \
        --connect-timeout 1 \
        --output /tmp/bridge_response.json \
        --write-out '%{http_code}' \
        -X POST "$ANTHROPIC_BASE_URL/v1/messages" \
        -H 'content-type: application/json' \
        -H 'anthropic-version: 2023-06-01' \
        -H 'x-api-key: bridge-no-auth' \
        -d "$payload" \
        > /tmp/curl_code 2>/tmp/curl_err
    then
        http_code=$(cat /tmp/curl_code)
        break
    fi
    sleep 0.25
done
printf 'HTTP_CODE=%s\n' "$http_code"
printf 'ATTEMPTS=%s\n' "$attempt"

# Trivial deliverable for the scorer.
printf 'hello' > /tmp/out
"""


@scorer(metrics=[accuracy()])
def file_equals_target() -> Scorer:
    """Score 1.0 iff /tmp/out exactly matches the target string."""

    async def score(state: TaskState, target: Target) -> Score:
        try:
            contents = await sandbox().read_file("/tmp/out")
        except FileNotFoundError:
            return Score(value=0.0, answer="<missing>")
        if isinstance(contents, bytes):
            contents = contents.decode()
        answer = contents.strip()
        return Score(value=1.0 if answer == target.text else 0.0, answer=answer)

    return score


@solver
def run_fake_harness() -> Solver:
    """Solver that runs the no-op fake harness inside the sandbox under the bridge."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        async with sandbox_agent_bridge(
            state=AgentState(messages=state.messages),
        ) as bridge:
            base_url = f"http://localhost:{bridge.port}"
            sb = sandbox()
            await sb.write_file("/tmp/fake_harness.sh", FAKE_HARNESS_SCRIPT)
            await sb.exec(["chmod", "+x", "/tmp/fake_harness.sh"])

            result = await sb.exec(
                ["/tmp/fake_harness.sh"],
                env={"ANTHROPIC_BASE_URL": base_url},
            )

            state.metadata["bridge_port"] = bridge.port
            state.metadata["bridge_base_url"] = base_url
            state.metadata["harness_stdout"] = result.stdout
            state.metadata["harness_stderr"] = result.stderr
            state.metadata["harness_returncode"] = result.returncode

        return state

    return solve


@task
def smoke() -> Task:
    """Smoke benchmark: fake harness writes 'hello' through the agent bridge."""
    return Task(
        dataset=[
            Sample(
                input="Run the fake harness so it writes 'hello' to /tmp/out.",
                target="hello",
            ),
        ],
        solver=run_fake_harness(),
        scorer=file_equals_target(),
        sandbox="local",
    )
