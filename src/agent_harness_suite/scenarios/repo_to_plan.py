"""Repo-to-plan scenario: analyze a repo and produce a feature proposal with implementation plan.

Orchestrates a four-phase pipeline through a single :class:`HarnessAdapter`:

    1. **research**        — summarize repo purpose, stack, direction, gaps
    2. **feature proposal** — pick one strong next feature with rationale
    3. **plan**            — write a detailed implementation plan
    4. **decomposition**   — split plan into a task graph (id, title, description, deps)

Each phase issues a single ``harness.invoke()`` call. Phases that expect
structured output instruct the agent to emit JSON and parse it defensively,
falling back to synthetic records so the pipeline always produces the four
mandatory artifacts (feature recommendation, rationale, plan, task graph).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from agent_harness_suite.config import Settings
from agent_harness_suite.harnesses.base import AgentResult, HarnessAdapter
from agent_harness_suite.scenarios.base import Scenario

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FeatureProposal:
    """A proposed next feature with justification."""

    title: str
    rationale: str


@dataclass
class PlanTask:
    """A single decomposed engineering task.

    ``depends_on`` references the ``id`` of tasks that must complete first.
    """

    id: str
    title: str
    description: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class PhaseMetrics:
    """Per-phase invocation metrics aggregated from the harness AgentResult."""

    total_tokens: int = 0
    total_turns: int = 0
    spawned_agents: int = 0


@dataclass
class RepoToPlanResult:
    """Structured output of the repo-to-plan scenario."""

    repo_url: str
    research: str
    feature: FeatureProposal
    plan: str
    tasks: list[PlanTask]
    raw_outputs: dict[str, str] = field(default_factory=dict)
    metrics: PhaseMetrics = field(default_factory=PhaseMetrics)


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


class RepoToPlanScenario(Scenario):
    """Benchmark scenario: given a repo, research it and produce a feature proposal."""

    @property
    def name(self) -> str:
        return "repo-to-plan"

    @property
    def description(self) -> str:
        return (
            "Analyze a GitHub repo, propose a next feature, "
            "and produce an implementation plan with task decomposition."
        )

    async def execute(
        self,
        harness: HarnessAdapter,
        repo_url: str,
        settings: Settings,
    ) -> dict[str, Any]:
        """Execute the four-phase pipeline and return a structured result dict."""
        metrics = PhaseMetrics()
        raw: dict[str, str] = {}

        research = await self._run_phase(
            harness,
            phase="research",
            prompt=_PROMPT_RESEARCH.format(repo_url=repo_url),
            context={"repo_url": repo_url, "phase": "research"},
            metrics=metrics,
            raw=raw,
        )

        feature_text = await self._run_phase(
            harness,
            phase="feature",
            prompt=_PROMPT_FEATURE.format(repo_url=repo_url, research=research),
            context={"repo_url": repo_url, "phase": "feature"},
            metrics=metrics,
            raw=raw,
        )
        feature = _parse_feature(feature_text)

        plan = await self._run_phase(
            harness,
            phase="plan",
            prompt=_PROMPT_PLAN.format(
                repo_url=repo_url,
                research=research,
                feature_title=feature.title,
                feature_rationale=feature.rationale,
            ),
            context={"repo_url": repo_url, "phase": "plan"},
            metrics=metrics,
            raw=raw,
        )

        tasks_text = await self._run_phase(
            harness,
            phase="tasks",
            prompt=_PROMPT_TASKS.format(
                feature_title=feature.title,
                plan=plan,
            ),
            context={"repo_url": repo_url, "phase": "tasks"},
            metrics=metrics,
            raw=raw,
        )
        tasks = _parse_tasks(tasks_text)

        result = RepoToPlanResult(
            repo_url=repo_url,
            research=research,
            feature=feature,
            plan=plan,
            tasks=tasks,
            raw_outputs=raw,
            metrics=metrics,
        )
        return _result_to_dict(result)

    async def _run_phase(
        self,
        harness: HarnessAdapter,
        *,
        phase: str,
        prompt: str,
        context: dict[str, Any],
        metrics: PhaseMetrics,
        raw: dict[str, str],
    ) -> str:
        """Invoke the harness for one phase and fold metrics into the aggregate."""
        logger.info("repo-to-plan: phase=%s starting", phase)
        agent_result: AgentResult = await harness.invoke(prompt, context)
        raw[phase] = agent_result.output
        if agent_result.total_tokens:
            metrics.total_tokens += agent_result.total_tokens
        if agent_result.total_turns:
            metrics.total_turns += agent_result.total_turns
        if agent_result.spawned_agents:
            metrics.spawned_agents += agent_result.spawned_agents
        logger.info("repo-to-plan: phase=%s complete (%d chars)", phase, len(agent_result.output))
        return agent_result.output


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------


_PROMPT_RESEARCH = """You are a senior engineer evaluating a GitHub repository to recommend
a strong next feature.

Target repo: {repo_url}

Produce a concise research brief (markdown) covering:
- Purpose: what this project does, for whom.
- Stack: primary languages, frameworks, deployment model.
- Architecture: high-level structure and key modules.
- Direction: recent commits, issues, and release notes.
- Gaps: rough edges, missing capabilities, or common user pain.

Keep the brief under 400 words. Use tool access (cloning, reading files,
searching issues) if available. If you cannot fetch the repo, state the
assumptions you are making and proceed.
"""


_PROMPT_FEATURE = """Using the research brief below, propose ONE strong next feature for
{repo_url}. The proposal must be ambitious but tractable in a single sprint.

Research brief:
---
{research}
---

Respond with strict JSON (no prose, no markdown fences) matching:

{{
  "title": "<short feature name>",
  "rationale": "<3-6 sentence justification grounded in the research>"
}}
"""


_PROMPT_PLAN = """Write a detailed implementation plan (markdown, under 500 words) for
the feature below. Cover:
- Affected modules and new components.
- Data model or API changes.
- Testing strategy (unit + integration).
- Rollout / migration considerations.
- Risks and mitigations.

Repo: {repo_url}

Feature: {feature_title}
Rationale: {feature_rationale}

Research brief (for reference):
---
{research}
---
"""


_PROMPT_TASKS = """Decompose the following implementation plan into discrete engineering
tasks suitable for a shared task tracker.

Feature: {feature_title}

Plan:
---
{plan}
---

Respond with strict JSON (no prose, no markdown fences) matching:

{{
  "tasks": [
    {{
      "id": "T1",
      "title": "<short task title>",
      "description": "<1-3 sentence description with exit criteria>",
      "depends_on": []
    }}
  ]
}}

Rules:
- Use sequential IDs: T1, T2, T3, ...
- "depends_on" may only reference earlier task IDs.
- Produce between 3 and 10 tasks.
"""


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _extract_json(text: str) -> Any | None:
    """Best-effort JSON extraction from an agent response.

    Tries, in order: direct json.loads, fenced ```json``` block, first balanced
    JSON object/array in the text. Returns None on any failure.
    """
    stripped = text.strip()
    if not stripped:
        return None

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    m = _JSON_FENCE_RE.search(stripped)
    if m:
        try:
            return json.loads(m.group("body"))
        except json.JSONDecodeError:
            pass

    start_candidates = [i for i, ch in enumerate(stripped) if ch in "{["]
    for start in start_candidates:
        opener = stripped[start]
        closer = "}" if opener == "{" else "]"
        depth = 0
        for end in range(start, len(stripped)):
            ch = stripped[end]
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(stripped[start : end + 1])
                    except json.JSONDecodeError:
                        break
    return None


def _parse_feature(text: str) -> FeatureProposal:
    """Parse a FeatureProposal from agent output, falling back to raw text."""
    data = _extract_json(text)
    if isinstance(data, dict):
        title = str(data.get("title") or "Untitled feature").strip()
        rationale = str(data.get("rationale") or "").strip()
        if rationale:
            return FeatureProposal(title=title, rationale=rationale)

    logger.warning("repo-to-plan: feature JSON parse failed; using raw text fallback")
    raw = text.strip() or "No feature proposal produced."
    first_line, _, rest = raw.partition("\n")
    return FeatureProposal(
        title=first_line.strip()[:120] or "Untitled feature",
        rationale=(rest.strip() or raw),
    )


def _parse_tasks(text: str) -> list[PlanTask]:
    """Parse a task graph from agent output; return [] if unrecoverable.

    Filters out dangling ``depends_on`` references so callers can trust the graph.
    """
    data = _extract_json(text)
    raw_tasks: list[dict[str, Any]] = []
    if isinstance(data, dict) and isinstance(data.get("tasks"), list):
        raw_tasks = [t for t in data["tasks"] if isinstance(t, dict)]
    elif isinstance(data, list):
        raw_tasks = [t for t in data if isinstance(t, dict)]

    if not raw_tasks:
        logger.warning("repo-to-plan: task JSON parse failed; returning empty task graph")
        return []

    seen_ids: set[str] = set()
    tasks: list[PlanTask] = []
    for idx, item in enumerate(raw_tasks, start=1):
        task_id = str(item.get("id") or f"T{idx}").strip() or f"T{idx}"
        title = str(item.get("title") or f"Task {idx}").strip()
        description = str(item.get("description") or "").strip()
        deps_raw = item.get("depends_on") or []
        deps = [str(d).strip() for d in deps_raw if isinstance(d, (str, int))]
        deps = [d for d in deps if d in seen_ids]
        tasks.append(
            PlanTask(id=task_id, title=title, description=description, depends_on=deps)
        )
        seen_ids.add(task_id)
    return tasks


def _result_to_dict(result: RepoToPlanResult) -> dict[str, Any]:
    """Serialize the dataclass tree to a plain dict (stable JSON-friendly shape)."""
    return {
        "repo_url": result.repo_url,
        "research": result.research,
        "feature": asdict(result.feature),
        "plan": result.plan,
        "tasks": [asdict(t) for t in result.tasks],
        "raw_outputs": dict(result.raw_outputs),
        "metrics": asdict(result.metrics),
    }
