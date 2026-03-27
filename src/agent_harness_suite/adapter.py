"""Abstract harness adapter protocol.

Every agent harness backend (Claude Agent SDK, GitHub Copilot SDK, etc.)
implements this protocol so the benchmark runner can drive them uniformly.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from typing import Any

from .types import LifecycleEvent, RunResult, ScenarioConfig


class HarnessAdapter(abc.ABC):
    """Contract that every harness backend must satisfy.

    The benchmark runner interacts exclusively through this interface.
    Implementations translate between the generic contract and the
    SDK-specific APIs.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short, unique identifier for this adapter (e.g. ``"claude"``)."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def setup(self, config: dict[str, Any]) -> None:
        """One-time initialization (validate credentials, warm caches).

        Called once before any scenarios are run.  Raise on fatal
        misconfiguration so the runner can fail fast.
        """

    @abc.abstractmethod
    async def teardown(self) -> None:
        """Release resources acquired during :meth:`setup`."""

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @abc.abstractmethod
    async def run(self, scenario: ScenarioConfig) -> RunResult:
        """Execute *scenario* and return a normalized result.

        The adapter is responsible for:
        * translating the scenario prompt into SDK-specific API calls,
        * collecting metrics throughout execution,
        * catching SDK-level errors and mapping them to :class:`RunStatus`,
        * respecting ``scenario.timeout_seconds``.
        """

    @abc.abstractmethod
    def stream_events(self, scenario: ScenarioConfig) -> AsyncIterator[LifecycleEvent]:
        """Yield lifecycle events as the scenario executes.

        This is the *streaming* counterpart of :meth:`run`.  Not every
        adapter can support true streaming; those that cannot may yield a
        single ``RUN_COMPLETED`` event after the run finishes.
        """

    # ------------------------------------------------------------------
    # Capability introspection
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def supported_features(self) -> set[str]:
        """Return feature tags this adapter supports.

        Standard tags (adapters add what applies):
        * ``"streaming"``   – true streaming of lifecycle events
        * ``"sub_agents"``  – the harness can spawn child agents
        * ``"tool_use"``    – the harness exposes tool-calling
        * ``"token_counts"``– the SDK reports token usage

        The benchmark runner uses these to skip scenarios that require
        features a given adapter does not support.
        """
