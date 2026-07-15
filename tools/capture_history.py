"""Capture a real Temporal execution history as a replay-test fixture.

``worker/test_replay.py`` proves that the *current* workflow code can still
replay a *previously recorded* execution history — the standard guard
against accidentally introducing non-determinism. That test needs a
concrete history to replay against, and this module produces it.

Regeneration procedure
-----------------------
Run this whenever the fixture needs to be (re)created, e.g. after a
deliberate, versioning-safe change to a workflow's call sequence::

    uv run python -m tools.capture_history

What it does, step by step:

1. Starts a local, ephemeral Temporal server with
   ``temporalio.testing.WorkflowEnvironment.start_local()``.
2. Builds the real worker (``worker.worker.build_worker``), registering the
   actual ``PaymentCorrectionCoordinator``, ``InstructionAgentWorkflow``,
   ``ComplianceAgentWorkflow`` and ``CorridorMemoryWorkflow`` — no test
   doubles.
3. Executes ``PaymentCorrectionCoordinator`` against the SEEDED corridor-
   memory anomaly (corridor ``"US->IN"``, anomaly type ``WRONG_IBAN`` — see
   ``worker/memory.py``). That anomaly is a guaranteed memory hit, so the
   capture never calls a model and needs no API key.
4. Fetches the resulting execution history from the server and overwrites
   ``worker/testdata/coordinator-history.json`` with it.

The fixture is committed to version control like any other test data. After
regenerating it, re-run ``uv run pytest worker/test_replay.py`` to confirm
the checked-out workflow code can still replay it.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing worker.worker: that import chain reaches
# worker.agents, which reads CORRIDOR_MODEL at import time. Mirrors the
# import order worker/main.py uses for the same reason. The seeded anomaly
# captured below never actually calls a model, so the value doesn't matter
# here, but keeping the same order avoids a surprise if that ever changes.
load_dotenv()

from temporalio.client import Client, WorkflowHistory  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin  # noqa: E402

from shared.models import AnomalyType, PaymentAnomaly  # noqa: E402
from worker.worker import build_worker  # noqa: E402
from worker.workflows import PaymentCorrectionCoordinator  # noqa: E402

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "worker"
    / "testdata"
    / "coordinator-history.json"
)

WORKFLOW_ID = "capture-coordinator-history"

# The seeded corridor-memory pattern (worker/memory.py's `_MEMORY`): this
# exact (corridor, anomaly_type) pair is a guaranteed hit, so capturing it
# never reaches a model — no API key required to run this tool.
SEEDED_ANOMALY = PaymentAnomaly(
    payment_id="pay-capture-1",
    corridor="US->IN",
    amount=500.0,
    currency="INR",
    anomaly_type=AnomalyType.WRONG_IBAN,
    details={"iban": "WRONG"},
)


async def _capture() -> WorkflowHistory:
    """Run the real coordinator once on a local server and return its history."""
    async with await WorkflowEnvironment.start_local() as env:
        # env.client uses the default data converter, which cannot serialize
        # the Pydantic models crossing the Temporal boundary here (same
        # reasoning as worker/test_workflows.py). Connect a fresh client
        # with PydanticAIPlugin, exactly like worker/main.py does.
        client = await Client.connect(
            env.client.service_client.config.target_host,
            plugins=[PydanticAIPlugin()],
        )
        worker = build_worker(client)
        async with worker:
            handle = await client.start_workflow(
                PaymentCorrectionCoordinator.run,
                SEEDED_ANOMALY,
                id=WORKFLOW_ID,
                task_queue=worker.task_queue,
            )
            await handle.result()
            return await handle.fetch_history()


def main() -> None:
    history = asyncio.run(_capture())
    # WorkflowHistory.to_json_dict() doesn't include the workflow ID, so the
    # fixture stores it alongside the history for worker/test_replay.py.
    fixture = {"workflow_id": WORKFLOW_ID, "history": history.to_json_dict()}
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(fixture, indent=2) + "\n")
    print(f"Captured {len(history.events)} events -> {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
