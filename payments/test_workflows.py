"""Integration tests for the coordinator and agent child workflows.

These tests run real workflow code against
``temporalio.testing.WorkflowEnvironment.start_local()``, a full local
Temporal server started for the duration of the test. That is heavier than
a unit test, but it is the only way to exercise the actual `workflow.defn`
classes (child workflows, activities, the sandbox, the data converter)
rather than the plain Python functions already covered by
``payments/test_worker.py``.

No ``pytest-asyncio`` dependency is configured in this project (see
``pyproject.toml``), so async scenarios are driven with ``asyncio.run``
inside plain, synchronous test functions — the same style as
``shared/test_encryption.py``.

Mocking the model
------------------
The two production agents (``payments.agents.instruction_agent`` and
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

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import SearchAttributeKey
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

# Mirrors the passthrough convention in payments/workflows.py and
# payments/agents.py: these modules are imported normally (not re-executed by
# the sandbox on every workflow task) because they hold objects — the
# TemporalAgent instances below — whose identity and internal state must be
# shared between workflow invocations. cryptography's Fernet also needs to
# be here: its Rust extension module cannot survive being re-imported inside
# the sandbox (it crashes with a low-level SystemError).
with workflow.unsafe.imports_passed_through():
    # NOTE: pydantic imports annotated_types lazily when it validates a
    # constrained model, so it must be passed through too (see
    # payments/workflows.py).
    import annotated_types  # noqa: F401

    from cryptography.fernet import Fernet
    from pydantic_ai import Agent
    from pydantic_ai.durable_exec.temporal import PydanticAIPlugin, TemporalAgent
    from pydantic_ai.models.test import TestModel

    from shared.encryption import EncryptionCodec, build_data_converter
    from shared.models import (
        AnomalyType,
        Beneficiary,
        ComplianceVerdict,
        CorrectionOutcome,
        CorrectionProposal,
        CorrectionSource,
        CorridorPattern,
        PaymentAnomaly,
    )

    # region FEATURE-ON: human-approval-signal
    # from shared.models import ApprovalDecision
    #
    # endregion FEATURE-ON: human-approval-signal
    from memory import store as memory_store
    from payments.activities import apply_correction

    # region FEATURE-ON: settlement-confirmation
    # from payments.activities import confirm_settlement
    # endregion FEATURE-ON: settlement-confirmation

    from payments.agents import AgentCorrection
    from payments.workflows import (
        ComplianceAgentWorkflow,
        InstructionAgentWorkflow,
        PaymentCorrectionCoordinator,
        _propose,
        _verify_compliance,
    )

TASK_QUEUE = "payment-corridor-test"


# --- In-process corridor-memory activity doubles -------------------------
#
# In production these two activities are HTTP clients to the corridor-memory
# service (see payments/memory.py). Starting that service is unnecessary for
# these workflow-orchestration tests, so we register doubles under the same
# activity names that run the service's own store logic (memory/store.py)
# directly, in-process. That keeps the scenarios hermetic and offline while
# preserving the exact hit/miss behaviour the coordinator depends on (the
# store is pre-seeded with the US->IN / WRONG_BIC pattern).


@activity.defn(name="read_corridor_memory")
async def read_corridor_memory(
    corridor: str,
    anomaly_type: AnomalyType,
    beneficiary_bank_id: str | None = None,
) -> CorridorPattern | None:
    return memory_store.lookup(corridor, anomaly_type, beneficiary_bank_id)


@activity.defn(name="write_corridor_memory")
async def write_corridor_memory(pattern: CorridorPattern) -> None:
    memory_store.remember(pattern)


# --- Test doubles registered in place of InstructionAgentWorkflow --------
#
# Both stand-ins below are registered under the real workflow's type name
# ("InstructionAgentWorkflow") so that PaymentCorrectionCoordinator — which
# addresses its children by that name — needs no changes to run against
# them.

# A TestModel-backed agent: deterministic, offline, and still routed through
# a real Temporal model-request activity, so it exercises the same code path
# a live model would (just without the network call). The output is a fixed,
# valid BIC proposal (via custom_output_args) rather than TestModel's
# auto-generated example, so downstream BIC validation accepts it.
_test_instruction_agent = Agent(
    TestModel(
        custom_output_args={
            "field_to_fix": "bic",
            "proposed_value": "HDFCINBBXXX",
            "rationale": "Test double proposal.",
            "confidence": 0.0,
        }
    ),
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


# A TestModel-backed compliance double, registered under the real compliance
# workflow's type name. Paired with the instruction double, it lets the
# coordinator reach a genuine low-confidence outcome (TestModel returns
# confidence 0.0) entirely offline.
_test_compliance_agent = Agent(
    TestModel(),
    name="compliance_agent",
    output_type=ComplianceVerdict,
    instructions="Test double; TestModel never reads this.",
)
_test_compliance_temporal_agent = TemporalAgent(_test_compliance_agent)


# NOTE: This and _FailingComplianceAgentWorkflow below both register under the
# real "ComplianceAgentWorkflow" type name; they are mutually exclusive -- each
# test's Worker registers exactly one of them.
@workflow.defn(name="ComplianceAgentWorkflow")
class _FakeComplianceAgentWorkflow:
    """Runs the real memory-first compliance flow, but against a TestModel."""

    __pydantic_ai_agents__ = [_test_compliance_temporal_agent]

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> ComplianceVerdict:
        return await _verify_compliance(_test_compliance_temporal_agent, anomaly)


@workflow.defn(name="ComplianceAgentWorkflow")
class _FailingComplianceAgentWorkflow:
    """Always fails, to exercise the fail-closed compliance gate."""

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> ComplianceVerdict:
        raise ApplicationError("Simulated compliance-agent outage")


async def _local_env_client(env: WorkflowEnvironment) -> Client:
    """Connect a fresh client to the given local test server.

    ``env.client`` uses the default data converter, which cannot serialize
    the Pydantic models crossing the Temporal boundary here. Every test
    below instead connects its own client with ``PydanticAIPlugin``, exactly
    like ``payments/main_worker.py`` does — the plugin installs the Pydantic data
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
                # "US->GB" / WRONG_BIC is not in the corridor-memory store's
                # seed, so this is a guaranteed miss that falls through to the
                # agent.
                anomaly = PaymentAnomaly(
                    payment_id="pay-miss-1",
                    corridor="US->GB",
                    amount=250.0,
                    currency="GBP",
                    anomaly_type=AnomalyType.WRONG_BIC,
                    beneficiary=Beneficiary(
                        name="Globex Trading Ltd", bank_id="BARCGB22"
                    ),
                    details={"bic": "NOT-A-REAL-BIC"},
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
        # The fake returns a fixed, valid BIC proposal; the point is that the
        # LLM path actually ran and populated them.
        assert proposal.field_to_fix
        assert proposal.proposed_value
        assert proposal.rationale

    asyncio.run(scenario())


def test_coordinator_holds_when_compliance_fails():
    """Fail-closed: a failed compliance agent never lets a fix auto-apply.

    The instruction agent hits the seeded memory (US->IN / WRONG_BIC), so it
    returns a confident proposal offline. The compliance agent fails, so there
    is no clearance -- the coordinator holds instead of applying. In the
    baseline, a held correction is refused outright; with human-approval-signal
    on, the coordinator awaits a human who rejects it.
    """

    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local(
            search_attributes=[
                SearchAttributeKey.for_keyword("corridor"),
                SearchAttributeKey.for_keyword("anomalyType"),
                SearchAttributeKey.for_keyword("status"),
            ],
        ) as env:
            client = await _local_env_client(env)
            async with Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[
                    PaymentCorrectionCoordinator,
                    InstructionAgentWorkflow,
                    _FailingComplianceAgentWorkflow,
                ],
                activities=[
                    read_corridor_memory,
                    write_corridor_memory,
                    apply_correction,
                ],
            ):
                anomaly = PaymentAnomaly(
                    payment_id="pay-holds-1",
                    corridor="US->IN",
                    amount=500.0,
                    currency="INR",
                    anomaly_type=AnomalyType.WRONG_BIC,
                    beneficiary=Beneficiary(
                        name="Acme Textiles Pvt Ltd", bank_id="HDFCINBB"
                    ),
                    details={"bic": "WRONG"},
                )
                # region FEATURE-OFF: human-approval-signal
                # Baseline: no oversight wired, so a fail-closed hold (no
                # verdict) is refused outright, surfacing the gate's reason.
                outcome: CorrectionOutcome = await client.execute_workflow(
                    PaymentCorrectionCoordinator.run,
                    anomaly,
                    id="test-coordinator-holds-when-compliance-fails",
                    task_queue=TASK_QUEUE,
                    execution_timeout=timedelta(seconds=30),
                )
                assert outcome.applied is False
                assert outcome.proposal is not None
                assert outcome.proposal.agent_name == "instruction_agent"
                assert outcome.verdict is None
                # endregion FEATURE-OFF: human-approval-signal

                # region FEATURE-ON: human-approval-signal
                # # With oversight wired, a fail-closed hold no longer refuses on
                # # its own: it waits for a human. awaiting_approval() reports True
                # # until a decision arrives; the reviewer REJECTS, so the
                # # correction is refused and never applied.
                # handle = await client.start_workflow(
                #     PaymentCorrectionCoordinator.run,
                #     anomaly,
                #     id="test-coordinator-holds-when-compliance-fails",
                #     task_queue=TASK_QUEUE,
                #     execution_timeout=timedelta(seconds=30),
                # )
                # awaiting = False
                # for _ in range(50):
                #     awaiting = await handle.query(
                #         PaymentCorrectionCoordinator.awaiting_approval
                #     )
                #     if awaiting:
                #         break
                #     await asyncio.sleep(0.1)
                # assert awaiting
                # await handle.signal(
                #     PaymentCorrectionCoordinator.approve_correction,
                #     ApprovalDecision(approved=False, approver="tester"),
                # )
                # outcome: CorrectionOutcome = await handle.result()
                # assert outcome.applied is False
                # assert outcome.proposal is not None
                # assert outcome.proposal.agent_name == "instruction_agent"
                # assert outcome.verdict is None  # compliance failed -> no verdict
                # assert outcome.decision is not None
                # assert outcome.decision.approved is False
                # endregion FEATURE-ON: human-approval-signal

    asyncio.run(scenario())


def test_coordinator_applies_when_compliant_and_confident():
    """Happy path: both agents hit the seeded memory, offline, and apply.

    Instruction returns a confident memory proposal; compliance returns a
    memory-derived compliant verdict. The gate clears and the correction is
    applied without any human oversight.
    """

    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local(
            search_attributes=[
                SearchAttributeKey.for_keyword("corridor"),
                SearchAttributeKey.for_keyword("anomalyType"),
                SearchAttributeKey.for_keyword("status"),
            ],
        ) as env:
            client = await _local_env_client(env)
            async with Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[
                    PaymentCorrectionCoordinator,
                    InstructionAgentWorkflow,
                    ComplianceAgentWorkflow,
                ],
                activities=[
                    read_corridor_memory,
                    write_corridor_memory,
                    apply_correction,
                    # region FEATURE-ON: settlement-confirmation
                    # confirm_settlement,
                    # endregion FEATURE-ON: settlement-confirmation
                ],
            ):
                anomaly = PaymentAnomaly(
                    payment_id="pay-applies-1",
                    corridor="US->IN",
                    amount=500.0,
                    currency="INR",
                    anomaly_type=AnomalyType.WRONG_BIC,
                    beneficiary=Beneficiary(
                        name="Acme Textiles Pvt Ltd", bank_id="HDFCINBB"
                    ),
                    details={"bic": "WRONG"},
                )
                outcome: CorrectionOutcome = await client.execute_workflow(
                    PaymentCorrectionCoordinator.run,
                    anomaly,
                    id="test-coordinator-applies-when-compliant",
                    task_queue=TASK_QUEUE,
                    execution_timeout=timedelta(seconds=30),
                )

                # region FEATURE-ON: search-attributes
                # # NOTE: The coordinator must publish a terminal status
                # # ("applied") before returning, so a completed execution never
                # # lingers at "processing" in Visibility. Read it back through
                # # describe() rather than trusting the returned outcome.
                # handle = client.get_workflow_handle(
                #     "test-coordinator-applies-when-compliant"
                # )
                # desc = await handle.describe()
                # status = desc.typed_search_attributes.get(
                #     SearchAttributeKey.for_keyword("status")
                # )
                # assert status == "applied"
                # endregion FEATURE-ON: search-attributes

        assert outcome.applied is True
        assert outcome.proposal is not None
        assert outcome.proposal.agent_name == "instruction_agent"
        assert outcome.proposal.field_to_fix == "bic"
        assert outcome.verdict is not None
        assert outcome.verdict.compliant is True

    asyncio.run(scenario())


def test_payload_encryption_encrypts_history():
    """Payloads written by an encrypted client are ciphertext on the wire.

    Two clients talk to the same local server: one plain, one built with
    ``build_data_converter(EncryptionCodec(...))`` alongside
    ``PydanticAIPlugin`` (proven in a prior task to coexist: the plugin only
    installs its own data converter when the caller supplies none). The
    coordinator runs on the encrypted client against the seeded memory-hit
    anomaly (US->IN / WRONG_BIC, no LLM call needed), then the PLAIN client
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
                SearchAttributeKey.for_keyword("status"),
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
                    InstructionAgentWorkflow,
                ],
                activities=[
                    read_corridor_memory,
                    write_corridor_memory,
                    apply_correction,
                    # region FEATURE-ON: settlement-confirmation
                    # confirm_settlement,
                    # endregion FEATURE-ON: settlement-confirmation
                ],
            ):
                anomaly = PaymentAnomaly(
                    payment_id="pay-encryption-1",
                    corridor="US->IN",
                    amount=750.0,
                    currency="INR",
                    anomaly_type=AnomalyType.WRONG_BIC,
                    beneficiary=Beneficiary(
                        name="Acme Textiles Pvt Ltd", bank_id="HDFCINBB"
                    ),
                    details={"bic": "WRONG"},
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
        assert outcome.proposal.field_to_fix == "bic"

    asyncio.run(scenario())


def test_coordinator_exposes_listing_query_surface():
    """The coordinator exposes the payments API's listing/detail query surface.

    ``describe_anomaly`` (the search-attributes OFF baseline) always returns
    the anomaly under correction — the per-workflow read the client-side
    listing path relies on. With human oversight wired
    (``human-approval-signal`` enabled), a low-confidence correction blocks and
    ``awaiting_approval`` reports True until a decision is signalled, then flips
    back to False.
    """

    async def scenario() -> None:
        async with await WorkflowEnvironment.start_local(
            search_attributes=[
                SearchAttributeKey.for_keyword("corridor"),
                SearchAttributeKey.for_keyword("anomalyType"),
                SearchAttributeKey.for_keyword("status"),
            ],
        ) as env:
            client = await _local_env_client(env)
            async with Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[
                    PaymentCorrectionCoordinator,
                    _FakeInstructionAgentWorkflow,
                    _FakeComplianceAgentWorkflow,
                ],
                activities=[
                    read_corridor_memory,
                    write_corridor_memory,
                    apply_correction,
                    # region FEATURE-ON: settlement-confirmation
                    # confirm_settlement,
                    # endregion FEATURE-ON: settlement-confirmation
                ],
            ):
                # "US->GB" / WRONG_BIC misses the seeded memory, so both doubles
                # fall through to TestModel. The compliance verdict comes back
                # compliant=False (TestModel's generated bool), so the gate holds
                # for review -- the awaiting state the API listing surfaces.
                anomaly = PaymentAnomaly(
                    payment_id="pay-query-surface-1",
                    corridor="US->GB",
                    amount=100.0,
                    currency="GBP",
                    anomaly_type=AnomalyType.WRONG_BIC,
                    beneficiary=Beneficiary(
                        name="Globex Trading Ltd", bank_id="BARCGB22"
                    ),
                    details={"bic": "NOT-A-REAL-BIC"},
                )
                handle = await client.start_workflow(
                    PaymentCorrectionCoordinator.run,
                    anomaly,
                    id="test-coordinator-query-surface",
                    task_queue=TASK_QUEUE,
                    execution_timeout=timedelta(seconds=30),
                )
                # NOTE: Consume the handle outside any FEATURE block so it is
                # never left unused. Its other uses live in FEATURE regions --
                # describe_anomaly (search-attributes off) and the approval
                # queries (human-approval-signal on) -- so a lone toggle state
                # would otherwise trip ruff F841.
                assert handle.id == "test-coordinator-query-surface"

                # region FEATURE-OFF: search-attributes
                # Baseline query surface (search-attributes OFF): describe_anomaly
                # is REPLACE-removed when search-attributes is enabled, so this
                # assertion pairs with the workflow's own FEATURE-OFF region.
                described = await handle.query(
                    PaymentCorrectionCoordinator.describe_anomaly
                )
                assert described.payment_id == anomaly.payment_id
                assert described.corridor == anomaly.corridor
                assert described.anomaly_type == anomaly.anomaly_type
                # endregion FEATURE-OFF: search-attributes

                # region FEATURE-ON: human-approval-signal
                # # With human oversight wired, the low-confidence correction
                # # blocks on a decision: awaiting_approval() stays True until a
                # # verdict arrives, then flips back to False.
                # awaiting = False
                # for _ in range(50):
                #     awaiting = await handle.query(
                #         PaymentCorrectionCoordinator.awaiting_approval
                #     )
                #     if awaiting:
                #         break
                #     await asyncio.sleep(0.1)
                # assert awaiting
                # # pending_review() carries the same proposal+verdict the approval
                # # panel needs to render, populated for exactly as long as the
                # # coordinator is blocked on a decision.
                # review = await handle.query(
                #     PaymentCorrectionCoordinator.pending_review,
                # )
                # assert review is not None
                # assert review.proposal.agent_name == "instruction_agent"
                # assert review.verdict is not None
                # await handle.signal(
                #     PaymentCorrectionCoordinator.approve_correction,
                #     ApprovalDecision(approved=True, approver="tester"),
                # )
                # outcome: CorrectionOutcome = await handle.result()
                # assert outcome.applied is True
                # assert not await handle.query(
                #     PaymentCorrectionCoordinator.awaiting_approval
                # )
                # assert (
                #     await handle.query(PaymentCorrectionCoordinator.pending_review)
                #     is None
                # )
                # endregion FEATURE-ON: human-approval-signal

    asyncio.run(scenario())


def test_instruction_agent_is_beneficiary_specific_on_wrong_bic():
    """Same corridor + anomaly, different beneficiary bank: only the seeded
    bank short-circuits the model; an unknown bank falls through to the LLM."""

    async def scenario() -> tuple[CorrectionSource, CorrectionSource]:
        async with await WorkflowEnvironment.start_local() as env:
            client = await _local_env_client(env)
            async with Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=[_FakeInstructionAgentWorkflow],
                activities=[read_corridor_memory, write_corridor_memory],
            ):
                seeded = PaymentAnomaly(
                    payment_id="pay-benef-seeded",
                    corridor="US->IN",
                    amount=500.0,
                    currency="INR",
                    anomaly_type=AnomalyType.WRONG_BIC,
                    beneficiary=Beneficiary(
                        name="Acme Textiles Pvt Ltd", bank_id="HDFCINBB"
                    ),
                    details={"bic": "WRONG"},
                )
                unknown = seeded.model_copy(
                    update={
                        "payment_id": "pay-benef-unknown",
                        "beneficiary": Beneficiary(
                            name="Other Traders", bank_id="OTHRINBB"
                        ),
                    }
                )
                seeded_proposal: CorrectionProposal = await client.execute_workflow(
                    "InstructionAgentWorkflow",
                    seeded,
                    id="test-benef-seeded",
                    task_queue=TASK_QUEUE,
                    result_type=CorrectionProposal,
                    execution_timeout=timedelta(seconds=30),
                )
                unknown_proposal: CorrectionProposal = await client.execute_workflow(
                    "InstructionAgentWorkflow",
                    unknown,
                    id="test-benef-unknown",
                    task_queue=TASK_QUEUE,
                    result_type=CorrectionProposal,
                    execution_timeout=timedelta(seconds=30),
                )
        return seeded_proposal.source, unknown_proposal.source

    seeded_source, unknown_source = asyncio.run(scenario())
    assert seeded_source == CorrectionSource.MEMORY
    assert unknown_source == CorrectionSource.LLM
