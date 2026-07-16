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

# --- FEATURE: search-attributes ---
# from temporalio.common import SearchAttributeKey
# --- END FEATURE: search-attributes ---

with workflow.unsafe.imports_passed_through():
    from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow

    from worker.activities import apply_correction
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

# --- FEATURE: search-attributes ---
# # Typed Search Attribute keys used by PaymentCorrectionCoordinator below to
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
# --- END FEATURE: search-attributes ---


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
        # --- FEATURE: saga-compensation ---
        # self._compensations: list[CorrectionProposal] = []
        # --- END FEATURE: saga-compensation ---

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> CorrectionOutcome:
        # --- FEATURE: search-attributes ---
        # # Tag this execution with typed Search Attributes so it can be
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
        # --- END FEATURE: search-attributes ---

        # Fan out to the specialized agents, each as its own child workflow.
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
            # --- FEATURE: human-approval-signal ---
            # workflow.logger.info("Low confidence, awaiting human approval")
            # await workflow.wait_condition(lambda: self._decision is not None)
            # assert self._decision is not None
            # if not self._decision.approved:
            #     return CorrectionOutcome(
            #         payment_id=anomaly.payment_id,
            #         applied=False,
            #         proposal=best,
            #         decision=self._decision,
            #         message="Correction rejected by reviewer.",
            #     )
            # --- END FEATURE: human-approval-signal ---

            # Starting point (no oversight wired yet): refuse low-confidence
            # fixes outright.
            return CorrectionOutcome(
                payment_id=anomaly.payment_id,
                applied=False,
                proposal=best,
                message="Confidence below threshold; human approval required.",
            )

        reference = await workflow.execute_activity(
            apply_correction,
            best,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        # --- FEATURE: saga-compensation ---
        # self._compensations.append(best)
        # --- END FEATURE: saga-compensation ---

        return CorrectionOutcome(
            payment_id=anomaly.payment_id,
            applied=True,
            proposal=best,
            decision=self._decision,
            message=f"Correction applied (reference {reference}).",
        )

    # --- FEATURE: human-approval-signal ---
    # @workflow.signal
    # async def approve_correction(self, decision: ApprovalDecision) -> None:
    #     """Human reviewer's verdict on a low-confidence proposal."""
    #     self._decision = decision
    #
    # @workflow.query
    # def decision(self) -> ApprovalDecision | None:
    #     return self._decision
    #
    # --- END FEATURE: human-approval-signal ---

    # --- FEATURE: human-approval-update ---
    # # Update is the request/response alternative to a fire-and-forget
    # # Signal: the caller gets a validated, synchronous acknowledgement.
    # @workflow.update
    # async def submit_decision(self, decision: ApprovalDecision) -> str:
    #     self._decision = decision
    #     return "accepted" if decision.approved else "rejected"
    #
    # @submit_decision.validator
    # def _validate(self, decision: ApprovalDecision) -> None:
    #     if not decision.approver:
    #         raise ValueError("approver is required")
    # --- END FEATURE: human-approval-update ---
