"""Corridor-memory service application definition.

A small FastAPI application that exposes the passive corridor memory over
HTTP: look up a known correction pattern for a (corridor, anomaly_type) pair,
and remember a newly learned one. In the baseline the backing store is the
intentionally-naive in-memory implementation in ``memory/store.py``; the
``memory-workflow`` FEATURE swaps it for a durable Temporal workflow
(``memory/workflow.py``) reached through an embedded worker wired up below.

The server startup lives in ``memory/main.py``; this module defines the
``app`` object, imported as ``memory.app:app`` by uvicorn. Logfire is
configured here (not in ``main.py``) because uvicorn's reload runs the app in
a fresh subprocess that imports this module directly, never ``main.py``. For
the same reason the ``memory-workflow`` FEATURE wires its Temporal client and
embedded worker here, in a FastAPI lifespan.
"""

from __future__ import annotations

import logfire
from dotenv import load_dotenv
from fastapi import FastAPI, status

from shared.models import AnomalyType, CorridorPattern

# NOTE: Import the store as a module (not its functions) so a later FEATURE
# toggle can swap the whole backing implementation — in-memory now, a durable
# Temporal workflow later — behind these same handlers by changing only what
# ``store`` resolves to, without touching the route code below.
from memory import store

# region FEATURE-ON: memory-workflow
# import asyncio
# import os
# from contextlib import asynccontextmanager
#
# from temporalio.client import Client
# from temporalio.common import WorkflowIDConflictPolicy
# from temporalio.contrib.pydantic import pydantic_data_converter
# from temporalio.worker import Worker
#
# from memory.workflow import MemoryWorkflow
#
# endregion FEATURE-ON: memory-workflow
# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before configuring Logfire so
# its environment is visible in this (serving) process.
load_dotenv()


def setup_logfire() -> logfire.Logfire:
    """Configure Logfire the same local-only way payments and the web UI do.

    ``send_to_logfire=False`` keeps Logfire local-only: spans are produced
    locally for instrumentation but nothing is shipped to any backend.
    """
    return logfire.configure(
        service_name="payment-corridor",
        send_to_logfire=False,
    )


# NOTE: Configure Logfire before instrumenting the app, in the process that serves
# requests (the uvicorn reload subprocess imports this module, not main.py).
setup_logfire()


# region FEATURE-ON: memory-workflow
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Run an embedded Temporal worker hosting the singleton MemoryWorkflow.
#
#     On startup: connect a client to the memory namespace, start the embedded
#     worker as a background task, and ensure the singleton entity workflow is
#     running and seeded. On shutdown: stop the worker. The wiring lives here in
#     a FastAPI lifespan (not main.py) because uvicorn's reload imports this
#     module in a subprocess, never main.py — the same reason Logfire is
#     configured in this module.
#     """
#     temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
#     namespace = os.getenv("MEMORY_TEMPORAL_NAMESPACE", "memory")
#
#     # NOTE: The workflow exchanges CorridorPattern (a pydantic model) across the
#     # Temporal boundary, so the client MUST use the pydantic data converter.
#     # Source: https://docs.temporal.io/develop/python/temporal-clients
#     client = await Client.connect(
#         temporal_address,
#         namespace=namespace,
#         data_converter=pydantic_data_converter,
#     )
#     app.state.temporal_client = client
#
#     # Run the memory worker in-process as a background task for the app's
#     # lifetime; it polls the `memory` task queue and hosts MemoryWorkflow.
#     worker = Worker(
#         client,
#         task_queue=MemoryWorkflow.TASK_QUEUE,
#         workflows=[MemoryWorkflow],
#     )
#     worker_task = asyncio.create_task(worker.run())
#
#     # NOTE: Ensure the singleton entity workflow is running and seeded.
#     # USE_EXISTING makes startup idempotent: if the workflow is already running
#     # (after a reload or restart) reuse it and keep its accumulated state,
#     # instead of failing or starting a duplicate.
#     # Source: https://docs.temporal.io/develop/python/temporal-clients#start-workflow-execution
#     await client.start_workflow(
#         MemoryWorkflow.run,
#         args=[store.seed()],
#         id=MemoryWorkflow.WORKFLOW_ID,
#         task_queue=MemoryWorkflow.TASK_QUEUE,
#         id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
#     )
#
#     yield
#
#     # Shutdown: stop the embedded worker and wait for it to unwind.
#     worker_task.cancel()
#     try:
#         await worker_task
#     except asyncio.CancelledError:
#         pass
#
#
# endregion FEATURE-ON: memory-workflow
# region FEATURE-OFF: memory-workflow
app = FastAPI(title="Corridor Memory")
# endregion FEATURE-OFF: memory-workflow
# region FEATURE-ON: memory-workflow
# app = FastAPI(title="Corridor Memory", lifespan=lifespan)
# endregion FEATURE-ON: memory-workflow

# Trace incoming requests through Logfire (a no-op export when offline).
logfire.instrument_fastapi(app)


@app.get("/api/memory/v1/lookup")
async def lookup(corridor: str, anomaly_type: AnomalyType) -> CorridorPattern | None:
    """Look up a known correction pattern for a corridor + anomaly type.

    A miss returns ``null`` with HTTP 200 (not 404): "no pattern known yet" is
    an expected, ordinary answer for a lookup, not a client error.

    NOTE: This HTTP contract is deliberately independent of the storage backend.
    Today it delegates to the in-memory ``store``; the ``memory-workflow`` FEATURE
    swaps that for a durable Temporal workflow query, leaving this endpoint
    unchanged.
    """
    # region FEATURE-OFF: memory-workflow
    pattern = store.lookup(corridor, anomaly_type)
    # endregion FEATURE-OFF: memory-workflow
    # region FEATURE-ON: memory-workflow
    # # NOTE: Serve the read from the durable workflow with a Temporal query —
    # # read-only and never recorded in history, so lookups add no audit events.
    # # Source: https://docs.temporal.io/develop/python/message-passing#send-query
    # handle = app.state.temporal_client.get_workflow_handle(MemoryWorkflow.WORKFLOW_ID)
    # pattern = await handle.query(MemoryWorkflow.lookup, args=[corridor, anomaly_type])
    # endregion FEATURE-ON: memory-workflow
    return pattern


@app.post("/api/memory/v1/remember", status_code=status.HTTP_204_NO_CONTENT)
async def remember(pattern: CorridorPattern) -> None:
    """Remember a newly learned correction pattern (returns HTTP 204).

    NOTE: This HTTP contract is deliberately independent of the storage backend.
    Today it delegates to the in-memory ``store``; the ``memory-workflow`` FEATURE
    swaps that for a durable Temporal workflow update, leaving this endpoint
    unchanged.
    """
    # region FEATURE-OFF: memory-workflow
    store.remember(pattern)
    # endregion FEATURE-OFF: memory-workflow
    # region FEATURE-ON: memory-workflow
    # # NOTE: Persist the pattern with a Temporal update, not a signal. execute_update
    # # returns only after the write is validated and durably accepted, so the HTTP
    # # 204 is a genuine acknowledgement — the caller knows the pattern is recorded.
    # # Source: https://docs.temporal.io/develop/python/message-passing#send-update-from-client
    # handle = app.state.temporal_client.get_workflow_handle(MemoryWorkflow.WORKFLOW_ID)
    # await handle.execute_update(MemoryWorkflow.remember, pattern)
    # endregion FEATURE-ON: memory-workflow


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
