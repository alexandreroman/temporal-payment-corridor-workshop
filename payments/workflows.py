"""Workflows: the coordinator and the agent child workflows.

Determinism rules apply here — no wall-clock, no network, no randomness in
workflow code. All I/O happens in activities or inside the durable agents.
Non-workflow modules are imported through ``imports_passed_through`` so the
Temporal sandbox uses the real objects (notably the ``TemporalAgent``
instances) instead of re-importing them.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from enum import StrEnum

from temporalio import workflow
from temporalio.common import RetryPolicy

# region FEATURE-ON: search-attributes
# from temporalio.common import SearchAttributeKey
# endregion FEATURE-ON: search-attributes

with workflow.unsafe.imports_passed_through():
    from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow

    from payments.activities import apply_correction

    # region FEATURE-ON: settlement-confirmation
    # from payments.activities import confirm_settlement
    # endregion FEATURE-ON: settlement-confirmation

    from payments.agents import (
        AgentCorrection,
        compliance_temporal_agent,
        instruction_temporal_agent,
    )
    from payments.memory import read_corridor_memory

    from shared.models import (
        ApprovalDecision,
        ComplianceVerdict,
        CorrectionOutcome,
        CorrectionProposal,
        CorrectionSource,
        PaymentAnomaly,
    )

# Confidence at or above which a fix is trusted without human sign-off.
CONFIDENCE_THRESHOLD = 0.75

TASK_QUEUE = "payment-corridor"

# region FEATURE-OFF: approval-timeout
# How long the coordinator waits for a human decision. None = wait forever.
_APPROVAL_TIMEOUT: timedelta | None = None
# endregion FEATURE-OFF: approval-timeout
# region FEATURE-ON: approval-timeout
# # NOTE: Bounded human-in-the-loop: if no decision arrives within this window the
# # coordinator stops waiting and auto-rejects. This is a *durable timer* —
# # workflow.wait_condition(timeout=...) raises asyncio.TimeoutError when the
# # deadline elapses, and the timer survives worker restarts like any other
# # workflow state. Source: https://docs.temporal.io/develop/python/timers
# _APPROVAL_TIMEOUT: timedelta | None = timedelta(minutes=5)
# endregion FEATURE-ON: approval-timeout


# region FEATURE-ON: search-attributes
# # NOTE: Typed Search Attribute keys used by PaymentCorrectionCoordinator below to
# # tag each workflow execution with its corridor and anomaly type. This makes
# # executions filterable and listable (in the Web UI, the `temporal workflow
# # list` CLI, or the SDK) without scanning payloads. Registered on the dev
# # server via compose.yaml, so no manual
# # `temporal operator search-attribute create` step is needed.
# # Source: https://docs.temporal.io/develop/python/observability#search-attributes
# _CORRIDOR_SA = SearchAttributeKey.for_keyword("corridor")
# _ANOMALY_TYPE_SA = SearchAttributeKey.for_keyword("anomalyType")
# # NOTE: status carries the correction lifecycle ("processing" ->
# # "awaiting-approval") so the payments API can list and filter executions
# # server-side. Registered on the dev server via compose.yaml.
# _STATUS_SA = SearchAttributeKey.for_keyword("status")
#
#
# def _set_status(value: str) -> None:
#     """Publish the correction lifecycle through the status Search Attribute."""
#     workflow.upsert_search_attributes([_STATUS_SA.value_set(value)])
#
#
# endregion FEATURE-ON: search-attributes
# region FEATURE-OFF: search-attributes
def _set_status(value: str) -> None:
    """No-op until the search-attributes feature is enabled."""


# endregion FEATURE-OFF: search-attributes


class GateDecision(StrEnum):
    """What the coordinator should do once both agents have reported."""

    APPLY = "apply"  # compliant and confident -> apply the instruction fix
    REVIEW = (
        "review"  # hold for human oversight (violation / low confidence / no verdict)
    )
    NO_PROPOSAL = "no_proposal"  # instruction agent produced nothing to apply


def _gate(
    proposal: CorrectionProposal | None,
    verdict: ComplianceVerdict | None,
) -> tuple[GateDecision, str]:
    """Combine the instruction proposal with the compliance verdict.

    NOTE: Compliance is a gate, not a competing proposer. A fix is applied
    only when the verdict clears it AND the proposal is confident enough.
    Absence of a clearance -- the compliance agent failed, or it reported a
    violation -- never auto-applies (fail-closed); it holds for a human. This
    replaces the old max(confidence) merge, where a confident instruction fix
    could silently outvote a compliance violation.
    """
    if proposal is None:
        return (
            GateDecision.NO_PROPOSAL,
            "All correction agents failed; no proposal to apply.",
        )
    if verdict is None:
        return (
            GateDecision.REVIEW,
            "Compliance check unavailable; holding for human review.",
        )
    if not verdict.compliant:
        joined = "; ".join(verdict.violations) or "unspecified"
        return GateDecision.REVIEW, f"Compliance violation(s): {joined}."
    if proposal.confidence < CONFIDENCE_THRESHOLD:
        return (
            GateDecision.REVIEW,
            "Confidence below threshold; human approval required.",
        )
    return GateDecision.APPLY, ""


def _anomaly_context(anomaly: PaymentAnomaly) -> str:
    """Render the shared anomaly context both agent prompts start from."""
    return (
        f"Corridor: {anomaly.corridor}\n"
        f"Anomaly: {anomaly.anomaly_type}\n"
        f"Amount: {anomaly.amount} {anomaly.currency}\n"
        f"Details: {anomaly.details}\n"
    )


def _prompt(anomaly: PaymentAnomaly) -> str:
    """Prompt the instruction agent to propose a correction."""
    return _anomaly_context(anomaly) + "Propose the single best correction."


def _compliance_prompt(anomaly: PaymentAnomaly) -> str:
    """Prompt the compliance agent to return a verdict, not a correction."""
    return _anomaly_context(anomaly) + (
        "Validate whether a compliant correction is possible and return a verdict."
    )


async def _propose(
    agent, agent_name: str, anomaly: PaymentAnomaly
) -> CorrectionProposal:
    """Memory-first proposal flow shared by the agent child workflows.

    Check passive memory before spending a model call; fall back to the
    durable agent only when no confident pattern is known.
    """
    pattern = await workflow.execute_activity(
        read_corridor_memory,
        args=[anomaly.corridor, anomaly.anomaly_type],
        start_to_close_timeout=timedelta(seconds=10),
    )
    if pattern is not None and pattern.confidence >= CONFIDENCE_THRESHOLD:
        return CorrectionProposal(
            agent_name=agent_name,
            field_to_fix=pattern.field_to_fix,
            proposed_value=pattern.proposed_value,
            rationale="Matched a known corridor pattern in passive memory.",
            confidence=pattern.confidence,
            source=CorrectionSource.MEMORY,
        )

    result = await agent.run(_prompt(anomaly))
    correction: AgentCorrection = result.output
    return CorrectionProposal(
        agent_name=agent_name,
        field_to_fix=correction.field_to_fix,
        proposed_value=correction.proposed_value,
        rationale=correction.rationale,
        confidence=correction.confidence,
        source=CorrectionSource.LLM,
    )


async def _verify_compliance(agent, anomaly: PaymentAnomaly) -> ComplianceVerdict:
    """Memory-first compliance check for the compliance child workflow.

    NOTE: A known high-confidence corridor pattern is presumed compliant
    without a model call, mirroring _propose. This is what keeps the seeded
    happy path (US->IN / WRONG_BIC) fully offline: neither agent calls the
    model. On a miss, the durable compliance agent produces the verdict.
    """
    pattern = await workflow.execute_activity(
        read_corridor_memory,
        args=[anomaly.corridor, anomaly.anomaly_type],
        start_to_close_timeout=timedelta(seconds=10),
    )
    if pattern is not None and pattern.confidence >= CONFIDENCE_THRESHOLD:
        return ComplianceVerdict(
            compliant=True,
            violations=[],
            confidence=pattern.confidence,
            source=CorrectionSource.MEMORY,
        )

    result = await agent.run(_compliance_prompt(anomaly))
    verdict: ComplianceVerdict = result.output
    return ComplianceVerdict(
        compliant=verdict.compliant,
        violations=verdict.violations,
        confidence=verdict.confidence,
        source=CorrectionSource.LLM,
    )


@workflow.defn
class InstructionAgentWorkflow(PydanticAIWorkflow):
    """Child workflow driving the instruction-fixing agent."""

    __pydantic_ai_agents__ = [instruction_temporal_agent]

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> CorrectionProposal:
        return await _propose(instruction_temporal_agent, "instruction_agent", anomaly)


@workflow.defn
class ComplianceAgentWorkflow(PydanticAIWorkflow):
    """Child workflow driving the compliance-checking agent."""

    __pydantic_ai_agents__ = [compliance_temporal_agent]

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> ComplianceVerdict:
        return await _verify_compliance(compliance_temporal_agent, anomaly)


@workflow.defn
class PaymentCorrectionCoordinator:
    """Parent workflow: fan out to agents, decide, apply — with oversight."""

    def __init__(self) -> None:
        self._decision: ApprovalDecision | None = None
        # Stored so the search-attributes OFF listing can read it back via the
        # describe_anomaly() query; harmless when unused.
        self._anomaly: PaymentAnomaly | None = None
        # True only while the coordinator is blocked on a human decision; read by
        # the awaiting_approval() query on the client-side listing path.
        self._awaiting: bool = False

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> CorrectionOutcome:
        self._anomaly = anomaly
        # region FEATURE-ON: search-attributes
        # # NOTE: Tag this execution with typed Search Attributes so it can be
        # # filtered/listed by corridor and anomaly type. This replaces the
        # # deprecated dict form of upsert_search_attributes. anomaly.anomaly_type
        # # is an AnomalyType StrEnum, so it is converted with str(...) because
        # # value_set expects a plain str for a keyword key. The call is
        # # deterministic and workflow-safe, so it belongs here in workflow code.
        # # Source: https://docs.temporal.io/develop/python/observability#search-attributes
        # workflow.upsert_search_attributes(
        #     [
        #         _CORRIDOR_SA.value_set(anomaly.corridor),
        #         _ANOMALY_TYPE_SA.value_set(str(anomaly.anomaly_type)),
        #         _STATUS_SA.value_set("processing"),
        #     ]
        # )
        # endregion FEATURE-ON: search-attributes

        # NOTE: Fan out to the specialized agents, each as its own child workflow.
        # gather(return_exceptions=True) makes the fan-out resilient: a single
        # agent failing degrades gracefully instead of failing the whole
        # correction. Each child gets an explicit execution timeout so a hung
        # agent cannot stall the coordinator indefinitely.
        # Source: https://docs.temporal.io/develop/python/child-workflows
        base_id = workflow.info().workflow_id
        results = await asyncio.gather(
            workflow.execute_child_workflow(
                InstructionAgentWorkflow.run,
                anomaly,
                id=f"{base_id}-instruction",
                execution_timeout=timedelta(minutes=2),
            ),
            workflow.execute_child_workflow(
                ComplianceAgentWorkflow.run,
                anomaly,
                id=f"{base_id}-compliance",
                execution_timeout=timedelta(minutes=2),
            ),
            return_exceptions=True,
        )
        # NOTE: Compliance is now a gate over the instruction fix, not a rival
        # proposal. results[0] is the instruction child, results[1] the
        # compliance child (gather preserves order); either may be an exception.
        proposal = results[0] if isinstance(results[0], CorrectionProposal) else None
        verdict = results[1] if isinstance(results[1], ComplianceVerdict) else None
        decision, message = _gate(proposal, verdict)

        if decision is GateDecision.NO_PROPOSAL:
            return CorrectionOutcome(
                payment_id=anomaly.payment_id,
                applied=False,
                verdict=verdict,
                message=message,
            )

        # Human oversight when the gate withholds automatic apply: a compliance
        # violation, a missing verdict (fail-closed), or low confidence.
        if decision is GateDecision.REVIEW:
            # region FEATURE-ON: human-approval-signal
            # workflow.logger.info("Low confidence, awaiting human approval")
            # # NOTE: Publish the awaiting state through both listing seams: the
            # # in-memory flag feeds the awaiting_approval() query (client-side
            # # listing), and _set_status(...) upserts the status search attribute
            # # (server-side filtering) when that feature is enabled. The finally
            # # block resets both once the wait resolves, so an approved-and-
            # # resuming correction no longer lists as awaiting.
            # self._awaiting = True
            # _set_status("awaiting-approval")
            # # _APPROVAL_TIMEOUT defaults to None (wait forever); enabling the
            # # `approval-timeout` feature turns this into a real auto-reject deadline.
            # try:
            #     await workflow.wait_condition(
            #         lambda: self._decision is not None, timeout=_APPROVAL_TIMEOUT
            #     )
            # except asyncio.TimeoutError:
            #     return CorrectionOutcome(
            #         payment_id=anomaly.payment_id,
            #         applied=False,
            #         proposal=proposal,
            #         verdict=verdict,
            #         message="No decision within the approval window; auto-rejected.",
            #     )
            # finally:
            #     self._awaiting = False
            #     _set_status("processing")
            # assert self._decision is not None
            # if not self._decision.approved:
            #     return CorrectionOutcome(
            #         payment_id=anomaly.payment_id,
            #         applied=False,
            #         proposal=proposal,
            #         verdict=verdict,
            #         decision=self._decision,
            #         message="Correction rejected by reviewer.",
            #     )
            # endregion FEATURE-ON: human-approval-signal

            # region FEATURE-OFF: human-approval-signal
            # Starting point (no oversight wired yet): refuse a held correction
            # outright, surfacing the gate's reason.
            return CorrectionOutcome(
                payment_id=anomaly.payment_id,
                applied=False,
                proposal=proposal,
                verdict=verdict,
                message=message,
            )
            # endregion FEATURE-OFF: human-approval-signal

        reference = await workflow.execute_activity(
            apply_correction,
            proposal,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # region FEATURE-ON: settlement-confirmation
        # # Once the correction is applied, wait for the downstream rail to
        # # actually settle. confirm_settlement is a long-running, heartbeating
        # # activity that polls the rail; from the workflow's point of view it is
        # # just another activity to await, so determinism is preserved.
        # # Source: https://docs.temporal.io/encyclopedia/detecting-activity-failures#activity-heartbeat
        # #
        # # NOTE: Enabling this feature adds a workflow step (this activity call),
        # # so the coordinator's event history changes. The committed replay test
        # # (payments/test_replay.py) replays payments/testdata/coordinator-history.json,
        # # captured with the feature DISABLED, so it diverges and fails here BY
        # # DESIGN -- that is expected, not a bug. In production the safe way to add
        # # a step to already-running workflows is versioning/patching
        # # (workflow.patched(...)); the workshop deliberately does not regenerate
        # # the baseline history for the enabled state.
        # # Source: https://docs.temporal.io/develop/python/versioning
        # settlement = await workflow.execute_activity(
        #     confirm_settlement,
        #     reference,
        #     start_to_close_timeout=timedelta(seconds=30),
        #     # NOTE: heartbeat_timeout is what makes a stalled poll detectable: if
        #     # no heartbeat arrives within this window the attempt fails and is
        #     # retried per the policy below, resuming from the last reported cycle.
        #     # Source: https://docs.temporal.io/encyclopedia/detecting-activity-failures#heartbeat-timeout
        #     heartbeat_timeout=timedelta(seconds=5),
        #     retry_policy=RetryPolicy(maximum_attempts=3),
        # )
        # return CorrectionOutcome(
        #     payment_id=anomaly.payment_id,
        #     applied=True,
        #     proposal=proposal,
        #     verdict=verdict,
        #     decision=self._decision,
        #     settlement=settlement,
        #     message=f"Correction applied (reference {reference}).",
        # )
        # endregion FEATURE-ON: settlement-confirmation

        # region FEATURE-OFF: settlement-confirmation
        return CorrectionOutcome(
            payment_id=anomaly.payment_id,
            applied=True,
            proposal=proposal,
            verdict=verdict,
            decision=self._decision,
            message=f"Correction applied (reference {reference}).",
        )
        # endregion FEATURE-OFF: settlement-confirmation

    # region FEATURE-OFF: search-attributes
    @workflow.query
    def describe_anomaly(self) -> PaymentAnomaly:
        """Return the anomaly under correction.

        NOTE: The client-side listing path (search-attributes disabled) reads
        corridor/anomaly-type per running workflow through this query — one query
        per execution, the N+1 cost that search attributes exist to remove.
        """
        assert self._anomaly is not None
        return self._anomaly

    # endregion FEATURE-OFF: search-attributes

    # region FEATURE-ON: human-approval-signal
    # @workflow.signal
    # async def approve_correction(self, decision: ApprovalDecision) -> None:
    #     """Human reviewer's verdict on a low-confidence proposal."""
    #     self._decision = decision
    #
    # @workflow.query
    # def decision(self) -> ApprovalDecision | None:
    #     return self._decision
    #
    # @workflow.query
    # def awaiting_approval(self) -> bool:
    #     return self._awaiting
    #
    # endregion FEATURE-ON: human-approval-signal
