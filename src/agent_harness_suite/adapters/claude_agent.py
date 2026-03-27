"""Adapter for the Claude Agent SDK (claude_agent_sdk)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from ..adapter import HarnessAdapter
from ..types import (
    EventKind,
    LifecycleEvent,
    RunMetrics,
    RunResult,
    RunStatus,
    ScenarioConfig,
)


class ClaudeAgentAdapter(HarnessAdapter):
    """Drives benchmark scenarios through the Claude Agent SDK.

    Expects ``anthropic`` and ``claude_agent_sdk`` to be installed.
    The adapter translates Claude's streaming message events into the
    normalized :class:`LifecycleEvent` model.
    """

    _client: Any = None
    _model: str = "claude-sonnet-4-6-20250327"

    @property
    def name(self) -> str:
        return "claude"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def setup(self, config: dict[str, Any]) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is required for ClaudeAgentAdapter. "
                "Install with: pip install anthropic"
            ) from exc

        self._model = config.get("model", self._model)
        self._client = anthropic.Anthropic(
            api_key=config.get("api_key"),  # falls back to ANTHROPIC_API_KEY env
        )

    async def teardown(self) -> None:
        self._client = None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(self, scenario: ScenarioConfig) -> RunResult:
        events: list[LifecycleEvent] = []
        metrics = RunMetrics()
        start = time.monotonic()

        events.append(LifecycleEvent(kind=EventKind.RUN_STARTED))

        try:
            result = await asyncio.wait_for(
                self._execute(scenario, events, metrics),
                timeout=scenario.timeout_seconds,
            )
        except asyncio.TimeoutError:
            events.append(LifecycleEvent(kind=EventKind.ERROR, data={"reason": "timeout"}))
            metrics.wall_clock_seconds = time.monotonic() - start
            metrics.errors += 1
            return RunResult(
                status=RunStatus.TIMEOUT,
                metrics=metrics,
                events=events,
                adapter_name=self.name,
                scenario_name=scenario.name,
                error_message=f"Timed out after {scenario.timeout_seconds}s",
            )
        except Exception as exc:
            events.append(LifecycleEvent(kind=EventKind.ERROR, data={"reason": str(exc)}))
            metrics.wall_clock_seconds = time.monotonic() - start
            metrics.errors += 1
            return RunResult(
                status=RunStatus.ERROR,
                metrics=metrics,
                events=events,
                adapter_name=self.name,
                scenario_name=scenario.name,
                error_message=str(exc),
            )

        metrics.wall_clock_seconds = time.monotonic() - start
        events.append(LifecycleEvent(kind=EventKind.RUN_COMPLETED))

        return RunResult(
            status=RunStatus.SUCCESS,
            metrics=metrics,
            events=events,
            output=result,
            adapter_name=self.name,
            scenario_name=scenario.name,
        )

    async def _execute(
        self,
        scenario: ScenarioConfig,
        events: list[LifecycleEvent],
        metrics: RunMetrics,
    ) -> Any:
        """Run a multi-turn agentic loop via the Anthropic messages API."""
        assert self._client is not None, "setup() must be called first"

        system_prompt = scenario.params.get("system_prompt", "You are a helpful assistant.")
        max_turns = scenario.params.get("max_turns", 10)
        tools = scenario.params.get("tools", [])

        messages: list[dict[str, Any]] = [{"role": "user", "content": scenario.prompt}]

        for turn in range(max_turns):
            events.append(LifecycleEvent(kind=EventKind.TURN_STARTED, data={"turn": turn}))

            response = await asyncio.to_thread(
                self._client.messages.create,
                model=self._model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=tools if tools else [],
            )

            # Collect token metrics
            if hasattr(response, "usage") and response.usage:
                metrics.total_input_tokens += response.usage.input_tokens
                metrics.total_output_tokens += response.usage.output_tokens
            metrics.total_turns += 1

            # Check for tool use
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if tool_use_blocks:
                for tool_block in tool_use_blocks:
                    metrics.tool_calls += 1
                    events.append(
                        LifecycleEvent(
                            kind=EventKind.TOOL_CALLED,
                            data={
                                "tool": tool_block.name,
                                "input": tool_block.input,
                            },
                        )
                    )

                # Append assistant message and tool results for next turn
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for tool_block in tool_use_blocks:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": scenario.params.get(
                                "tool_result_stub",
                                "Tool execution not implemented in benchmark mode.",
                            ),
                        }
                    )
                    events.append(
                        LifecycleEvent(
                            kind=EventKind.TOOL_RESULT,
                            data={"tool_use_id": tool_block.id},
                        )
                    )
                messages.append({"role": "user", "content": tool_results})
            else:
                # No tool use — conversation complete
                events.append(
                    LifecycleEvent(kind=EventKind.TURN_COMPLETED, data={"turn": turn})
                )
                return "".join(b.text for b in text_blocks)

            events.append(LifecycleEvent(kind=EventKind.TURN_COMPLETED, data={"turn": turn}))

        return "Max turns reached"

    async def stream_events(  # type: ignore[override]
        self, scenario: ScenarioConfig
    ) -> AsyncIterator[LifecycleEvent]:
        """Stream lifecycle events during scenario execution."""
        events: list[LifecycleEvent] = []
        metrics = RunMetrics()

        yield LifecycleEvent(kind=EventKind.RUN_STARTED)

        try:
            await self._execute(scenario, events, metrics)
        except Exception as exc:
            yield LifecycleEvent(kind=EventKind.ERROR, data={"reason": str(exc)})

        for event in events:
            yield event

        yield LifecycleEvent(kind=EventKind.RUN_COMPLETED, data={"metrics": metrics.__dict__})

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def supported_features(self) -> set[str]:
        return {"streaming", "tool_use", "token_counts"}
