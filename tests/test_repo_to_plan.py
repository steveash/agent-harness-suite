"""Tests for the repo-to-plan scenario orchestration."""

from __future__ import annotations

import json
from typing import Any

import pytest

from agent_harness_suite.config import Settings
from agent_harness_suite.harnesses.base import AgentResult, HarnessAdapter
from agent_harness_suite.scenarios.repo_to_plan import (
    FeatureProposal,
    PlanTask,
    RepoToPlanScenario,
    _extract_json,
    _parse_feature,
    _parse_tasks,
)


class _StubHarness(HarnessAdapter):
    """Harness stub that returns canned outputs keyed by phase.

    The scenario passes ``context={"phase": ...}`` on each invocation; the stub
    dispatches on that field so tests can assert per-phase behavior.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        responses: dict[str, AgentResult],
    ) -> None:
        super().__init__(settings)
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    @property
    def name(self) -> str:
        return "stub"

    async def invoke(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> AgentResult:
        phase = (context or {}).get("phase", "unknown")
        self.calls.append((phase, prompt, context or {}))
        if phase not in self.responses:
            raise AssertionError(f"unexpected phase: {phase}")
        return self.responses[phase]


def _settings() -> Settings:
    return Settings(anthropic_api_key="k", github_token="t")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_direct_object(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_with_prose_prefix(self):
        assert _extract_json('Here you go:\n{"a": 2}\nthanks') == {"a": 2}

    def test_fenced_json_block(self):
        text = 'sure:\n```json\n{"a": 3, "b": [1,2]}\n```\nbye'
        assert _extract_json(text) == {"a": 3, "b": [1, 2]}

    def test_unfenced_array(self):
        assert _extract_json("output: [1, 2, 3]") == [1, 2, 3]

    def test_garbage_returns_none(self):
        assert _extract_json("not json at all") is None

    def test_empty_returns_none(self):
        assert _extract_json("   ") is None


class TestParseFeature:
    def test_well_formed_json(self):
        feat = _parse_feature(
            json.dumps({"title": "Multi-tenant auth", "rationale": "It unlocks the B2B plan."})
        )
        assert feat.title == "Multi-tenant auth"
        assert "B2B" in feat.rationale

    def test_missing_fields_fallback(self):
        feat = _parse_feature("just some freeform suggestion text")
        assert feat.title  # non-empty
        assert feat.rationale  # non-empty

    def test_empty_input_fallback(self):
        feat = _parse_feature("")
        assert feat.title
        assert feat.rationale


class TestParseTasks:
    def test_valid_task_graph(self):
        payload = json.dumps(
            {
                "tasks": [
                    {"id": "T1", "title": "Design schema", "description": "x", "depends_on": []},
                    {
                        "id": "T2",
                        "title": "Build API",
                        "description": "y",
                        "depends_on": ["T1"],
                    },
                ]
            }
        )
        tasks = _parse_tasks(payload)
        assert [t.id for t in tasks] == ["T1", "T2"]
        assert tasks[1].depends_on == ["T1"]

    def test_drops_dangling_dependencies(self):
        payload = json.dumps(
            {
                "tasks": [
                    {"id": "T1", "title": "a", "description": "", "depends_on": ["T99"]},
                ]
            }
        )
        tasks = _parse_tasks(payload)
        assert tasks[0].depends_on == []

    def test_accepts_bare_list(self):
        payload = json.dumps(
            [{"id": "T1", "title": "a", "description": "", "depends_on": []}]
        )
        tasks = _parse_tasks(payload)
        assert len(tasks) == 1

    def test_unparseable_returns_empty(self):
        assert _parse_tasks("no json here") == []


# ---------------------------------------------------------------------------
# Full scenario orchestration
# ---------------------------------------------------------------------------


@pytest.fixture
def happy_responses() -> dict[str, AgentResult]:
    return {
        "research": AgentResult(
            output="# Research\n- Purpose: test project\n- Stack: Python\n",
            total_tokens=100,
            total_turns=1,
        ),
        "feature": AgentResult(
            output=json.dumps(
                {
                    "title": "Streaming CLI progress",
                    "rationale": "Users currently wait blind. Streaming reveals progress.",
                }
            ),
            total_tokens=50,
            total_turns=1,
        ),
        "plan": AgentResult(
            output="## Plan\n1. Add event stream\n2. Wire CLI renderer\n",
            total_tokens=200,
            total_turns=2,
        ),
        "tasks": AgentResult(
            output=json.dumps(
                {
                    "tasks": [
                        {
                            "id": "T1",
                            "title": "Define event schema",
                            "description": "Enumerate event kinds.",
                            "depends_on": [],
                        },
                        {
                            "id": "T2",
                            "title": "Renderer",
                            "description": "Stream events to console.",
                            "depends_on": ["T1"],
                        },
                        {
                            "id": "T3",
                            "title": "Tests",
                            "description": "End-to-end CLI test.",
                            "depends_on": ["T2"],
                        },
                    ]
                }
            ),
            total_tokens=150,
            total_turns=1,
            spawned_agents=2,
        ),
    }


async def test_execute_happy_path(happy_responses):
    scenario = RepoToPlanScenario()
    harness = _StubHarness(_settings(), responses=happy_responses)

    result = await scenario.execute(
        harness, "https://github.com/example/repo", _settings()
    )

    # All four phases invoked in order
    phases = [c[0] for c in harness.calls]
    assert phases == ["research", "feature", "plan", "tasks"]

    # Deliverables present
    assert result["repo_url"] == "https://github.com/example/repo"
    assert result["research"].startswith("# Research")
    assert result["feature"] == {
        "title": "Streaming CLI progress",
        "rationale": "Users currently wait blind. Streaming reveals progress.",
    }
    assert result["plan"].startswith("## Plan")
    assert [t["id"] for t in result["tasks"]] == ["T1", "T2", "T3"]
    assert result["tasks"][1]["depends_on"] == ["T1"]

    # Metrics aggregated across all phases
    assert result["metrics"]["total_tokens"] == 500
    assert result["metrics"]["total_turns"] == 5
    assert result["metrics"]["spawned_agents"] == 2

    # Raw outputs preserved for every phase
    assert set(result["raw_outputs"].keys()) == {"research", "feature", "plan", "tasks"}


async def test_execute_with_unparseable_phases():
    """Scenario still produces the four artifacts even when JSON parsing fails."""
    responses = {
        "research": AgentResult(output="short brief"),
        "feature": AgentResult(output="just a sentence about a feature"),
        "plan": AgentResult(output="one-line plan"),
        "tasks": AgentResult(output="no json whatsoever"),
    }
    scenario = RepoToPlanScenario()
    harness = _StubHarness(_settings(), responses=responses)

    result = await scenario.execute(harness, "https://github.com/x/y", _settings())

    assert result["feature"]["title"]
    assert result["feature"]["rationale"]
    assert result["tasks"] == []
    assert result["research"] == "short brief"


async def test_prompts_include_repo_and_prior_context(happy_responses):
    """Downstream phases must see upstream outputs so agents can build on them."""
    scenario = RepoToPlanScenario()
    harness = _StubHarness(_settings(), responses=happy_responses)

    await scenario.execute(harness, "https://github.com/example/repo", _settings())

    prompts = {phase: prompt for phase, prompt, _ in harness.calls}
    assert "https://github.com/example/repo" in prompts["research"]
    assert "Research" in prompts["feature"]  # research text echoed in feature prompt
    assert "Streaming CLI progress" in prompts["plan"]  # feature title in plan prompt
    assert "Streaming CLI progress" in prompts["tasks"]
    assert "Add event stream" in prompts["tasks"]  # plan text echoed in tasks prompt


def test_dataclass_types_exposed():
    """Public dataclasses are importable and constructable — useful for consumers."""
    feat = FeatureProposal(title="x", rationale="y")
    task = PlanTask(id="T1", title="t", description="d", depends_on=[])
    assert feat.title == "x"
    assert task.id == "T1"
