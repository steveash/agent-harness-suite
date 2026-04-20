"""Adapter for the GitHub Copilot SDK (copilot-sdk)."""

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


class CopilotAdapter(HarnessAdapter):
    """Drives benchmark scenarios through the GitHub Copilot SDK.

    This adapter wraps the ``copilot-sdk`` Python package, translating
    Copilot's agent execution model into the normalized lifecycle events
    and metrics the benchmark runner expects.
    """

    _config: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "copilot"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def setup(self, config: dict[str, Any]) -> None:
        try:
            from copilot_sdk import CopilotClient  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "copilot-sdk package is required for CopilotAdapter. "
                "Install with: pip install copilot-sdk"
            ) from exc

        self._config = config

    async def teardown(self) -> None:
        self._config = {}

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
        except TimeoutError:
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
        """Run the scenario through the Copilot SDK agent loop."""
        from copilot_sdk import CopilotClient

        token = self._config.get("github_token")
        if not token:
            import os

            token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN is required for CopilotAdapter")

        client = CopilotClient(token=token)

        max_turns = scenario.params.get("max_turns", 10)
        messages: list[dict[str, str]] = [{"role": "user", "content": scenario.prompt}]

        for turn in range(max_turns):
            events.append(LifecycleEvent(kind=EventKind.TURN_STARTED, data={"turn": turn}))

            response = await asyncio.to_thread(
                client.chat,
                messages=messages,
                **scenario.params.get("copilot_kwargs", {}),
            )

            metrics.total_turns += 1

            # Extract token usage if available
            if hasattr(response, "usage"):
                usage = response.usage
                metrics.total_input_tokens += getattr(usage, "prompt_tokens", 0)
                metrics.total_output_tokens += getattr(usage, "completion_tokens", 0)

            # Check for function/tool calls
            choice = response.choices[0] if response.choices else None
            if choice and hasattr(choice, "message"):
                msg = choice.message

                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        metrics.tool_calls += 1
                        events.append(
                            LifecycleEvent(
                                kind=EventKind.TOOL_CALLED,
                                data={
                                    "tool": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            )
                        )
                        events.append(
                            LifecycleEvent(
                                kind=EventKind.TOOL_RESULT,
                                data={"tool_call_id": tc.id},
                            )
                        )

                    # Append for next turn
                    messages.append({"role": "assistant", "content": msg.content or ""})
                    for tc in msg.tool_calls:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": scenario.params.get(
                                    "tool_result_stub",
                                    "Tool execution not implemented in benchmark mode.",
                                ),
                            }
                        )
                elif msg.content:
                    events.append(
                        LifecycleEvent(kind=EventKind.TURN_COMPLETED, data={"turn": turn})
                    )
                    return msg.content
                else:
                    events.append(
                        LifecycleEvent(kind=EventKind.TURN_COMPLETED, data={"turn": turn})
                    )
                    return None

            events.append(LifecycleEvent(kind=EventKind.TURN_COMPLETED, data={"turn": turn}))

        return "Max turns reached"

    async def stream_events(  # type: ignore[override]
        self, scenario: ScenarioConfig
    ) -> AsyncIterator[LifecycleEvent]:
        """Stream lifecycle events. Copilot SDK does not support true streaming."""
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
        return {"tool_use"}
