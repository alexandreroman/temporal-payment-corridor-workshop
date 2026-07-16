"""Integration tests for the coordinator and agent child workflows.

These tests run real workflow code against
``temporalio.testing.WorkflowEnvironment.start_local()``, a full local
Temporal server started for the duration of the test. That is heavier than
a unit test, but it is the only way to exercise the actual `workflow.defn`
classes (child workflows, activities, the sandbox, the data converter)
rather than the plain Python functions already covered by
``worker/test_worker.py``.

No ``pytest-asyncio`` dependency is configured in this project (see
``pyproject.toml``), so async scenarios are driven with ``asyncio.run``
inside plain, synchronous test functions — the same style as
``shared/test_encryption.py``.

Mocking the model
------------------
The two production agents (``worker.agents.instruction_agent`` and
``compliance_agent``) call a real hosted model. Pydantic AI offers
``Agent.override(model=...)`` to swap the model for the duration of a call,
which is the documented way to test an agent without a network call.
That does **not** work here, though: under ``TemporalAgent``, a model
request is not a plain Python call but a Temporal *activity*, dispatched
through the server and picked up by the worker's activity poller as an
independent task. The contextvar ``override()`` sets around the workflow
call never reaches that separate activity task. This was verified
empirically — wrapping ``client.execute_workflow(...)`` in
``instruction_agent.override(model=TestModel())`` still made a real,
failing call to the Anthropic API (401, invalid key) instead of using the
test model.

The reliable alternative, used below for
``test_instruction_agent_returns_llm_proposal_on_memory_miss``, is to build
a *different* agent — constructed with
``pydantic_ai.models.test.TestModel`` from the start — and register a
stand-in workflow that runs it under the SAME workflow type name
(``"InstructionAgentWorkflow"``) on the test worker. The coordinator (and,
here, the test client) only ever addresses child workflows by type name, so
swapping the implementation registered under that name is enough; no
production code changes hands.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.client import Client
from temporalio.common import SearchAttributeKey
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

# Mirrors the passthrough convention in worker/workflows.py and
# worker/agents.py: these modules are imported normally (not re-executed by
# the sandbox on every workflow task) because they hold objects — the
# TemporalAgent instances below — whose identity and internal state must be
# shared between workflow invocations. cryptography's Fernet also needs to
# be here: its Rust extension module cannot survive being re-imported inside
# the sandbox (it crashes with a low-level SystemError).
with workflow.unsafe.imports_passed_through():
    from cryptography.fernet import Fernet
    from pydantic_ai import Agent
    from pydantic_ai.durable_exec.temporal import PydanticAIPlugin, TemporalAgent
    from pydantic_ai.models.test import TestModel

    from shared.encryption import EncryptionCodec, build_data_converter
    from shared.models import (
        AnomalyType,
        CorrectionOutcome,
        CorrectionProposal,
        CorrectionSource,
        PaymentAnomaly,
    )
    from worker.activities import apply_correction

    # --- FEATURE: settlement-confirmation ---
    # from worker.activities import confirm_settlement
    # --- END FEATURE: settlement-confirmation ---

    from worker.agents import AgentCorrection
    from worker.memory import read_corridor_memory, write_corridor_memory
    from worker.workflows import (
        ComplianceAgentWorkflow,
        PaymentCorrectionCoordinator,
        _propose,
    )

TASK_QUEUE = "payment-corridor-test"


# --- Test doubles registered in place of InstructionAgentWorkflow --------
#
# Both stand-ins below are registered under the real workflow's type name
# ("InstructionAgentWorkflow") so that PaymentCorrectionCoordinator — which
# addresses its children by that name — needs no changes to run against
# them.

# A TestModel-backed agent: deterministic, offline, and still routed through
# a real Temporal model-request activity, so it exercises the same code path
# a live model would (just without the network call).
_test_instruction_agent = Agent(
    TestModel(),
    name="instruction_agent",
    output_type=AgentCorrection,
    instructions="Test double; TestModel never reads this.",
)
_test_instruction_temporal_agent = TemporalAgent(_test_instruction_agent)


@workflow.defn(name="InstructionAgentWorkflow")
class _FakeInstructionAgentWorkflow:
    """Runs the real memory-first flow, but against a TestModel agent."""

    __pydantic_ai_agents__ = [_test_instruction_temporal_agent]

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> CorrectionProposal:
        return await _propose(
            _test_instruction_temporal_agent, "instruction_agent", anomaly
        )


@workflow.defn(name="InstructionAgentWorkflow")
class _FailingInstructionAgentWorkflow:
    """Always fails, to exercise the coordinator's resilient fan-out."""

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> CorrectionProposal:
        raise ApplicationError("Simulated instruction-agent outage")


async def _local_env_client(env: WorkflowEnvironment) -> Client:
    """Connect a fresh client to the given local test server.

    ``env.client`` uses the default data converter, which cannot serialize
    the Pydantic models crossing the Temporal boundary here. Every test
    below instead connects its own client with ``PydanticAIPlugin``, exactly
    like ``worker/main.py`` does — the plugin installs the Pydantic data
    converter and also wires the sandbox passthrough that TemporalAgent-
    based workflows need to pass validation at ``Worker`` construction.
    """
    return await Client.connect(
        env.client.service_client.config.target_host,
        plugins=[PydanticAIPlugin()],
    )


def test_instruction_agent_returns_llm_proposal_on_memory_miss():
    """A memory MISS falls through to the agent, using TestModel output."""

    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local() as env:
            client = await _local_env_client(env)
            async with Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[_FakeInstructionAgentWorkflow],
                activities=[read_corridor_memory, write_corridor_memory],
            ):
                # "US->GB" / WRONG_IBAN is not in worker.memory._MEMORY, so
                # this is a guaranteed miss that falls through to the agent.
                anomaly = PaymentAnomaly(
                    payment_id="pay-miss-1",
                    corridor="US->GB",
                    amount=250.0,
                    currency="GBP",
                    anomaly_type=AnomalyType.WRONG_IBAN,
                    details={"iban": "NOT-A-REAL-IBAN"},
                )
                # Started by workflow type name (a plain string), since the
                # class registered under that name here is a test double,
                # not the real InstructionAgentWorkflow. result_type is
                # required in that case: without a typed method reference,
                # the data converter has no type to reconstruct and would
                # otherwise hand back a plain dict.
                proposal: CorrectionProposal = await client.execute_workflow(
                    "InstructionAgentWorkflow",
                    anomaly,
                    id="test-instruction-agent-memory-miss",
                    task_queue=TASK_QUEUE,
                    result_type=CorrectionProposal,
                    execution_timeout=timedelta(seconds=30),
                )

        assert proposal.source == CorrectionSource.LLM
        # Values come straight from TestModel's generated example output;
        # the point is that the LLM path actually ran and populated them.
        assert proposal.field_to_fix
        assert proposal.proposed_value
        assert proposal.rationale

    asyncio.run(scenario())


def test_coordinator_survives_one_failing_agent():
    """The coordinator still applies a correction when one agent fails.

    The instruction agent is replaced with a stand-in that always raises.
    The compliance agent runs unmodified, but the anomaly is the seeded
    memory hit (US->IN / WRONG_IBAN), so it also never calls a model — the
    whole scenario stays offline while still exercising the real
    PaymentCorrectionCoordinator, its fan-out, and _select_best.
    """

    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local(
            search_attributes=[
                SearchAttributeKey.for_keyword("corridor"),
                SearchAttributeKey.for_keyword("anomalyType"),
            ],
        ) as env:
            client = await _local_env_client(env)
            async with Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[
                    PaymentCorrectionCoordinator,
                    _FailingInstructionAgentWorkflow,
                    ComplianceAgentWorkflow,
                ],
                activities=[
                    read_corridor_memory,
                    write_corridor_memory,
                    apply_correction,
                    # --- FEATURE: settlement-confirmation ---
                    # confirm_settlement,
                    # --- END FEATURE: settlement-confirmation ---
                ],
            ):
                anomaly = PaymentAnomaly(
                    payment_id="pay-resilience-1",
                    corridor="US->IN",
                    amount=500.0,
                    currency="INR",
                    anomaly_type=AnomalyType.WRONG_IBAN,
                    details={"iban": "WRONG"},
                )
                outcome: CorrectionOutcome = await client.execute_workflow(
                    PaymentCorrectionCoordinator.run,
                    anomaly,
                    id="test-coordinator-survives-failure",
                    task_queue=TASK_QUEUE,
                    execution_timeout=timedelta(seconds=30),
                )

        assert outcome.applied is True
        assert outcome.proposal is not None
        # The surviving proposal came from the compliance agent's memory hit,
        # not from the failed instruction agent.
        assert outcome.proposal.agent_name == "compliance_agent"
        assert outcome.proposal.source == CorrectionSource.MEMORY

    asyncio.run(scenario())


def test_payload_encryption_encrypts_history():
    """Payloads written by an encrypted client are ciphertext on the wire.

    Two clients talk to the same local server: one plain, one built with
    ``build_data_converter(EncryptionCodec(...))`` alongside
    ``PydanticAIPlugin`` (proven in a prior task to coexist: the plugin only
    installs its own data converter when the caller supplies none). The
    coordinator runs on the encrypted client against the seeded memory-hit
    anomaly (US->IN / WRONG_IBAN, no LLM call needed), then the PLAIN client
    reads back the raw event history and finds a payload marked
    ``encoding: binary/encrypted`` — proof that ciphertext, not plaintext,
    is what is actually stored. The encrypted client is used to confirm the
    outcome still decodes back to a correct, plaintext CorrectionOutcome.
    """

    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local(
            search_attributes=[
                SearchAttributeKey.for_keyword("corridor"),
                SearchAttributeKey.for_keyword("anomalyType"),
            ],
        ) as env:
            plain_client = await _local_env_client(env)
            encrypted_client = await Client.connect(
                env.client.service_client.config.target_host,
                data_converter=build_data_converter(
                    EncryptionCodec(Fernet.generate_key())
                ),
                plugins=[PydanticAIPlugin()],
            )

            async with Worker(
                encrypted_client,
                task_queue=TASK_QUEUE,
                workflows=[
                    PaymentCorrectionCoordinator,
                    ComplianceAgentWorkflow,
                    _FailingInstructionAgentWorkflow,
                ],
                activities=[
                    read_corridor_memory,
                    write_corridor_memory,
                    apply_correction,
                    # --- FEATURE: settlement-confirmation ---
                    # confirm_settlement,
                    # --- END FEATURE: settlement-confirmation ---
                ],
            ):
                anomaly = PaymentAnomaly(
                    payment_id="pay-encryption-1",
                    corridor="US->IN",
                    amount=750.0,
                    currency="INR",
                    anomaly_type=AnomalyType.WRONG_IBAN,
                    details={"iban": "WRONG"},
                )
                workflow_id = "test-payload-encryption"
                outcome: CorrectionOutcome = await encrypted_client.execute_workflow(
                    PaymentCorrectionCoordinator.run,
                    anomaly,
                    id=workflow_id,
                    task_queue=TASK_QUEUE,
                    execution_timeout=timedelta(seconds=30),
                )

            # Read the raw event history through the PLAIN client: it cannot
            # decode the encrypted payloads, so the WorkflowExecutionStarted
            # event's input (the PaymentAnomaly argument) surfaces here
            # exactly as it is stored on the server — still ciphertext.
            handle = plain_client.get_workflow_handle(workflow_id)
            started_input_payloads = []
            async for event in handle.fetch_history_events():
                if event.HasField("workflow_execution_started_event_attributes"):
                    started_input_payloads = list(
                        event.workflow_execution_started_event_attributes.input.payloads
                    )
            found_encrypted_payload = any(
                p.metadata.get("encoding") == b"binary/encrypted"
                for p in started_input_payloads
            )

        assert found_encrypted_payload
        assert outcome.applied is True
        assert outcome.proposal is not None
        assert outcome.proposal.field_to_fix == "iban"

    asyncio.run(scenario())
