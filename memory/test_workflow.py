"""Integration tests for MemoryWorkflow (the ``memory-workflow`` FEATURE backend).

These run the real ``@workflow.defn`` class against
``temporalio.testing.WorkflowEnvironment.start_local()`` — a full local
Temporal server for the test's duration — exactly like
``payments/test_workflows.py``. That is the only way to exercise the actual
query, update, update-validator and continue-as-new behaviour rather than
plain Python method calls.

CorridorPattern (a Pydantic model) crosses the Temporal boundary as a workflow
argument, query result and update argument, so every client here is built with
``pydantic_data_converter`` from ``temporalio.contrib.pydantic`` (its canonical
public module).

No ``pytest-asyncio`` dependency is configured (see ``pyproject.toml``), so the
async scenarios run via ``asyncio.run`` inside plain synchronous test
functions, matching the rest of the suite.
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client, WorkflowUpdateFailedError
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from memory import store
from memory.workflow import MemoryWorkflow
from shared.models import AnomalyType, CorridorPattern


async def _client(env: WorkflowEnvironment) -> Client:
    """Connect a client that can serialize the Pydantic models on the wire.

    ``env.client`` uses the default data converter, which cannot round-trip
    CorridorPattern; connecting a fresh client with ``pydantic_data_converter``
    is the same pattern ``memory/app.py`` uses for its embedded client.
    """
    return await Client.connect(
        env.client.service_client.config.target_host,
        data_converter=pydantic_data_converter,
    )


def _worker(client: Client) -> Worker:
    """Build the MemoryWorkflow worker used by every test here.

    NOTE: it runs under ``UnsandboxedWorkflowRunner`` on purpose. MemoryWorkflow
    holds only in-memory state and imports nothing nondeterministic, so the
    sandbox buys no safety here; meanwhile running unsandboxed (a) isolates
    these tests from the sandbox-importer state left behind by other
    sandboxed-workflow tests in the same process — which otherwise fails
    MemoryWorkflow's sandbox validation — and (b) lets the continue-as-new
    test's monkeypatched class attribute reach the running workflow (the sandbox
    re-imports the module, giving the workflow a fresh, unpatched class).
    """
    return Worker(
        client,
        task_queue=MemoryWorkflow.TASK_QUEUE,
        workflows=[MemoryWorkflow],
        workflow_runner=UnsandboxedWorkflowRunner(),
    )


async def _start_seeded(client: Client) -> object:
    """Start the singleton MemoryWorkflow seeded from the shared ``store.seed()``.

    Seeding happens in ``MemoryWorkflow.__init__`` (``@workflow.init``), which is
    guaranteed to run before any update handler, so an ``execute_update`` fired
    immediately after ``start_workflow`` cannot be lost — no barrier query needed.
    """
    handle = await client.start_workflow(
        MemoryWorkflow.run,
        args=[store.seed()],
        id=MemoryWorkflow.WORKFLOW_ID,
        task_queue=MemoryWorkflow.TASK_QUEUE,
    )
    return handle


def _new_pattern() -> CorridorPattern:
    return CorridorPattern(
        corridor="US->GB",
        anomaly_type=AnomalyType.CURRENCY_MISMATCH,
        field_to_fix="currency",
        proposed_value="GBP",
        confidence=0.8,
    )


def test_query_returns_seeded_pattern_on_hit():
    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local() as env:
            client = await _client(env)
            async with _worker(client):
                handle = await _start_seeded(client)
                pattern = await handle.query(
                    MemoryWorkflow.lookup, args=["US->IN", AnomalyType.WRONG_BIC]
                )

        assert pattern is not None
        assert pattern.field_to_fix == "bic"
        assert pattern.proposed_value == "HDFCINBBXXX"

    asyncio.run(scenario())


def test_query_returns_none_on_miss():
    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local() as env:
            client = await _client(env)
            async with _worker(client):
                handle = await _start_seeded(client)
                pattern = await handle.query(
                    MemoryWorkflow.lookup, args=["US->GB", AnomalyType.WRONG_BIC]
                )

        assert pattern is None

    asyncio.run(scenario())


def test_update_remember_is_a_durable_acked_write():
    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local() as env:
            client = await _client(env)
            async with _worker(client):
                handle = await _start_seeded(client)
                new = _new_pattern()

                # execute_update returns only after the write is durably
                # accepted, so the follow-up query must observe it.
                await handle.execute_update(MemoryWorkflow.remember, new)
                stored = await handle.query(
                    MemoryWorkflow.lookup,
                    args=["US->GB", AnomalyType.CURRENCY_MISMATCH],
                )

        assert stored == new

    asyncio.run(scenario())


def test_update_validator_rejects_an_invalid_pattern():
    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local() as env:
            client = await _client(env)
            async with _worker(client):
                handle = await _start_seeded(client)
                # corridor="" fails the update validator, so the write is
                # rejected before it is ever admitted to history.
                invalid = _new_pattern().model_copy(update={"corridor": ""})

                try:
                    await handle.execute_update(MemoryWorkflow.remember, invalid)
                    raised = False
                except WorkflowUpdateFailedError:
                    raised = True

        assert raised

    asyncio.run(scenario())


def test_continue_as_new_preserves_accumulated_patterns():
    """Crossing the update bound continues-as-new without losing state.

    NOTE: ``MAX_UPDATES_BEFORE_CONTINUE`` is monkeypatched to a small number so
    the boundary is reachable in a test. This relies on the unsandboxed worker
    (see ``_worker``): the default sandbox re-imports the workflow module and
    would give the running workflow a fresh, unpatched class.
    """

    async def scenario() -> None:
        MemoryWorkflow.MAX_UPDATES_BEFORE_CONTINUE = 3
        try:
            async with await WorkflowEnvironment.start_local() as env:
                client = await _client(env)
                async with _worker(client):
                    handle = await _start_seeded(client)
                    first_run_id = (await handle.describe()).run_id

                    # Enough writes to cross the bound and trigger continue-as-new.
                    patterns = [
                        CorridorPattern(
                            corridor=f"US->C{i}",
                            anomaly_type=AnomalyType.WRONG_BIC,
                            field_to_fix="bic",
                            proposed_value=f"BIC{i}",
                            confidence=0.5,
                        )
                        for i in range(MemoryWorkflow.MAX_UPDATES_BEFORE_CONTINUE)
                    ]
                    for pattern in patterns:
                        await handle.execute_update(MemoryWorkflow.remember, pattern)

                    # The singleton keeps its workflow id but is now a new run:
                    # continue-as-new started a fresh execution carrying state.
                    async def continued() -> bool:
                        return (await handle.describe()).run_id != first_run_id

                    await _eventually(continued)

                    # No accepted write was lost across the boundary: every
                    # pattern is still queryable on the carried-over state.
                    for pattern in patterns:
                        stored = await handle.query(
                            MemoryWorkflow.lookup,
                            args=[pattern.corridor, pattern.anomaly_type],
                        )
                        assert stored == pattern
                    seeded = await handle.query(
                        MemoryWorkflow.lookup,
                        args=["US->IN", AnomalyType.WRONG_BIC],
                    )
                    assert seeded is not None
        finally:
            MemoryWorkflow.MAX_UPDATES_BEFORE_CONTINUE = 100

    asyncio.run(scenario())


def test_query_with_bank_id_keys_a_distinct_pattern():
    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local() as env:
            client = await _client(env)
            async with _worker(client):
                handle = await _start_seeded(client)
                specific = CorridorPattern(
                    corridor="US->GB",
                    anomaly_type=AnomalyType.WRONG_BIC,
                    beneficiary_bank_id="BARCGB22",
                    field_to_fix="bic",
                    proposed_value="BARCGB22XXX",
                    confidence=0.9,
                )
                await handle.execute_update(MemoryWorkflow.remember, specific)

                hit = await handle.query(
                    MemoryWorkflow.lookup,
                    args=["US->GB", AnomalyType.WRONG_BIC, "BARCGB22"],
                )
                miss = await handle.query(
                    MemoryWorkflow.lookup, args=["US->GB", AnomalyType.WRONG_BIC]
                )

        assert hit == specific
        assert miss is None

    asyncio.run(scenario())


async def _eventually(condition, *, attempts: int = 50, delay: float = 0.1) -> None:
    """Poll an async predicate until it holds, to absorb continue-as-new lag."""
    for _ in range(attempts):
        if await condition():
            return
        await asyncio.sleep(delay)
    raise AssertionError("condition never became true")
