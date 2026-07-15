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

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow

    from activities import apply_correction
    from agents import (
        AgentCorrection,
        compliance_temporal_agent,
        instruction_temporal_agent,
    )
    from memory import read_corridor_memory
    from models import (
        ApprovalDecision,
        CorrectionOutcome,
        CorrectionProposal,
        CorrectionSource,
        PaymentAnomaly,
    )

# Confidence at or above which a fix is trusted without human sign-off.
CONFIDENCE_THRESHOLD = 0.75

TASK_QUEUE = "payment-corridor"


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

    # --- STEP: agent-resilience ---
    # Tune how the durable agent's model/tool activities retry and time out
    # by passing config to `agent.run(...)`, e.g.:
    #   from pydantic_ai.durable_exec.temporal import AgentRunConfig
    #   result = await agent.run(_prompt(anomaly), ...)
    # --- END STEP: agent-resilience ---
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
        # --- STEP: saga-compensation ---
        # self._compensations: list[CorrectionProposal] = []
        # --- END STEP: saga-compensation ---

    @workflow.run
    async def run(self, anomaly: PaymentAnomaly) -> CorrectionOutcome:
        # --- STEP: search-attributes ---
        # workflow.upsert_search_attributes(
        #     {"corridor": [anomaly.corridor], "anomalyType": [anomaly.anomaly_type]}
        # )
        # --- END STEP: search-attributes ---

        # Fan out to the specialized agents, each as its own child workflow.
        base_id = workflow.info().workflow_id
        instruction, compliance = await asyncio.gather(
            workflow.execute_child_workflow(
                InstructionAgentWorkflow.run, anomaly, id=f"{base_id}-instruction"
            ),
            workflow.execute_child_workflow(
                ComplianceAgentWorkflow.run, anomaly, id=f"{base_id}-compliance"
            ),
        )
        best = max([instruction, compliance], key=lambda p: p.confidence)

        # Human oversight when confidence is low.
        if best.confidence < CONFIDENCE_THRESHOLD:
            # --- STEP: human-approval-signal ---
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
            # --- END STEP: human-approval-signal ---

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
        # --- STEP: saga-compensation ---
        # self._compensations.append(best)
        # --- END STEP: saga-compensation ---

        return CorrectionOutcome(
            payment_id=anomaly.payment_id,
            applied=True,
            proposal=best,
            decision=self._decision,
            message=f"Correction applied (reference {reference}).",
        )

    # --- STEP: human-approval-signal ---
    # @workflow.signal
    # async def approve_correction(self, decision: ApprovalDecision) -> None:
    #     """Human reviewer's verdict on a low-confidence proposal."""
    #     self._decision = decision
    #
    # @workflow.query
    # def decision(self) -> ApprovalDecision | None:
    #     return self._decision
    # --- END STEP: human-approval-signal ---

    # --- STEP: human-approval-update ---
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
    # --- END STEP: human-approval-update ---
