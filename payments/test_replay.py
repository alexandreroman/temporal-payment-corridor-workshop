"""Replay test: guards workflow code against accidental non-determinism.

Temporal recovers a running workflow by *replaying* its recorded event
history against the current workflow code, re-executing every step and
checking the outcome still matches what the history says happened. If a
code change alters the sequence of decisions a workflow makes (e.g.
reordering awaited calls, adding one conditionally, changing what a child
workflow is passed), replay diverges from history and the workflow instance
gets stuck. A replay test catches that class of bug at test time instead of
in a running deployment.

This test does not run the workflow — it feeds a PREVIOUSLY CAPTURED
history (``payments/testdata/coordinator-history.json``, produced by
``tools/capture_history.py``; see that module's docstring for the
regeneration procedure) to :class:`temporalio.worker.Replayer`, which
re-executes it against whatever ``PaymentCorrectionCoordinator`` and its
child workflows look like right now. As long as nobody has made a
determinism-breaking change since the fixture was captured, replay
succeeds.

No ``pytest-asyncio`` dependency is configured in this project (see
``pyproject.toml``), so the async replay is driven with ``asyncio.run``
inside a plain, synchronous test function — the same style as
``payments/test_workflows.py``.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

from payments.workflows import (
    ComplianceAgentWorkflow,
    InstructionAgentWorkflow,
    PaymentCorrectionCoordinator,
)

FIXTURE_PATH = Path(__file__).parent / "testdata" / "coordinator-history.json"


def _load_fixture_history() -> WorkflowHistory:
    """Read the captured history fixture written by tools/capture_history.py."""
    fixture = json.loads(FIXTURE_PATH.read_text())
    return WorkflowHistory.from_json(fixture["workflow_id"], fixture["history"])


def test_coordinator_replays_captured_history():
    """The current workflow code replays a real, previously recorded history.

    All three workflow types that can appear in the coordinator's execution
    (parent + two agent children) are registered. Replayer validates every
    registered workflow's determinism, not just the ones a given history
    happens to touch.

    ``PydanticAIPlugin`` must be passed explicitly, exactly like every real
    ``Client``/``Worker`` in this project (see ``payments/main_worker.py``,
    ``payments/test_workflows.py``). ``Replayer`` never connects to a server,
    so nothing installs the plugin for it automatically. Two things depend
    on it here: the Pydantic data converter (needed to decode the recorded
    ``PaymentAnomaly`` / ``CorrectionOutcome`` payloads), and the sandbox
    passthrough list the plugin adds for ``pydantic_ai`` and its
    dependencies (notably ``beartype``) — without it, the sandbox tries to
    re-import those packages a second time and crashes with a circular-
    import error before replay even starts.
    """

    async def scenario() -> None:
        replayer = Replayer(
            workflows=[
                PaymentCorrectionCoordinator,
                InstructionAgentWorkflow,
                ComplianceAgentWorkflow,
            ],
            plugins=[PydanticAIPlugin()],
        )
        # raise_on_replay_failure defaults to True: any determinism
        # violation raises instead of being silently reported, which is
        # exactly what a test wants.
        await replayer.replay_workflow(_load_fixture_history())

    asyncio.run(scenario())
