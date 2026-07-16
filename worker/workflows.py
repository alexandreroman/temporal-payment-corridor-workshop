"""Workflows: the coordinator and the agent child workflows.

Determinism rules apply here — no wall-clock, no network, no randomness in
workflow code. All I/O happens in activities or inside the durable agents.
Non-workflow modules are imported through ``imports_passed_through`` so the
Temporal sandbox uses the real objects (notably the ``TemporalAgent``
instances) instead of re-importing them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# region FEATURE-ON: search-attributes
# from temporalio.common import SearchAttributeKey
# endregion FEATURE-ON: search-attributes

with workflow.unsafe.imports_passed_through():
    from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow

    from worker.activities import apply_correction

    # region FEATURE-ON: settlement-confirmation
    # from worker.activities import confirm_settlement
    # endregion FEATURE-ON: settlement-confirmation

    from worker.agents import (
        AgentCorrection,
        compliance_temporal_agent,
        instruction_temporal_agent,
    )
    from worker.memory import read_corridor_memory

    from shared.models import (
        ApprovalDecision,
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
# # list` CLI, or the SDK) without scanning payloads.
# # Source: https://docs.temporal.io/develop/python/observability#search-attributes
# #
# # These custom attributes must be registered on the dev server first:
# #   temporal operator search-attribute create --name corridor --type Keyword
# #   temporal operator search-attribute create --name anomalyType --type Keyword
# _CORRIDOR_SA = SearchAttributeKey.for_keyword("corridor")
# _ANOMALY_TYPE_SA = SearchAttributeKey.for_keyword("anomalyType")
# endregion FEATURE-ON: search-attributes


def _select_best(
    results: Sequence[CorrectionProposal | BaseException],
) -> CorrectionProposal | None:
    """Pick the highest-confidence proposal, tolerating agent failures.

    The coordinator fans out to agent child workflows concurrently. One agent
    failing must not sink the whole correction, so we gather with
    ``return_exceptions=True`` and select among the proposals that DID come
    back. Returns ``None`` only if every agent failed.
    Source: https://docs.temporal.io/develop/python/child-workflows
    """
    proposals = [r for r in results if isinstance(r, CorrectionProposal)]
    if not proposals:
        return None
    return max(proposals, key=lambda p: p.confidence)


def _prompt(anomaly: PaymentAnomaly) -> str:
    """Render an anomaly into a prompt for a correction agent."""
    return (
        f"Corridor: {anomaly.corridor}\n"
        f"Anomaly: {anomaly.anomaly_type}\n"
        f"Amount: {anomaly.amount} {anomaly.currency}\n"
        f"Details: {anomaly.details}\n"
        "Propose the single best correction."
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
    async def run(self, anomaly: PaymentAnomaly) -> CorrectionProposal:
        return await _propose(compliance_temporal_agent, "compliance_agent", anomaly)


@workflow.defn
class PaymentCorrectionCoordinator:
    """Parent workflow: fan out to agents, decide, apply — with oversight."""

    def __init__(self) -> None:
        self._decision: ApprovalDecision | None = None

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> CorrectionOutcome:
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
        best = _select_best(results)
        if best is None:
            return CorrectionOutcome(
                payment_id=anomaly.payment_id,
                applied=False,
                message="All correction agents failed; no proposal to apply.",
            )

        # Human oversight when confidence is low.
        if best.confidence < CONFIDENCE_THRESHOLD:
            # region FEATURE-ON: human-approval-signal
            # workflow.logger.info("Low confidence, awaiting human approval")
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
            #         proposal=best,
            #         message="No decision within the approval window; auto-rejected.",
            #     )
            # assert self._decision is not None
            # if not self._decision.approved:
            #     return CorrectionOutcome(
            #         payment_id=anomaly.payment_id,
            #         applied=False,
            #         proposal=best,
            #         decision=self._decision,
            #         message="Correction rejected by reviewer.",
            #     )
            # endregion FEATURE-ON: human-approval-signal

            # region FEATURE-OFF: human-approval-signal
            # Starting point (no oversight wired yet): refuse low-confidence
            # fixes outright.
            return CorrectionOutcome(
                payment_id=anomaly.payment_id,
                applied=False,
                proposal=best,
                message="Confidence below threshold; human approval required.",
            )
            # endregion FEATURE-OFF: human-approval-signal

        reference = await workflow.execute_activity(
            apply_correction,
            best,
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
        # # (worker/test_replay.py) replays worker/testdata/coordinator-history.json,
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
        #     proposal=best,
        #     decision=self._decision,
        #     settlement=settlement,
        #     message=f"Correction applied (reference {reference}).",
        # )
        # endregion FEATURE-ON: settlement-confirmation

        # region FEATURE-OFF: settlement-confirmation
        return CorrectionOutcome(
            payment_id=anomaly.payment_id,
            applied=True,
            proposal=best,
            decision=self._decision,
            message=f"Correction applied (reference {reference}).",
        )
        # endregion FEATURE-OFF: settlement-confirmation

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
    # endregion FEATURE-ON: human-approval-signal
