"""Shared Pydantic models for the payment-corridor correction demo.

These models are the contract between the coordinator workflow, the agent
child workflows, the activities and the client. They are intentionally
plain Pydantic models so they serialize cleanly across the Temporal
boundary (workflow args, activity args, signals and query results).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AnomalyType(StrEnum):
    """The kinds of anomaly a cross-border payment can carry."""

    WRONG_BIC = "wrong_bic"
    MISSING_INTERMEDIARY_BANK = "missing_intermediary_bank"
    CURRENCY_MISMATCH = "currency_mismatch"


class CorrectionSource(StrEnum):
    """Where a proposed correction came from."""

    MEMORY = "memory"  # matched a known pattern in passive corridor memory
    LLM = "llm"  # produced by an agent calling a model


class Beneficiary(BaseModel):
    """The party being paid, and the bank that holds their account.

    NOTE: ``bank_id`` is a normalized institution identifier (e.g. the 8-char
    institution BIC ``HDFCINBB``). It is the discriminator that makes a
    remembered ``wrong_bic`` correction beneficiary-specific instead of
    corridor-wide. Left ``None`` when the anomaly's correction is genuinely
    corridor-wide (e.g. a currency mismatch), so the memory key degrades to
    ``corridor|anomaly_type``.
    """

    name: str
    bank_id: str | None = None


class PaymentAnomaly(BaseModel):
    """An incoming payment flagged with a single anomaly on a corridor.

    A ``corridor`` is the ordered pair of ISO country codes the money
    travels between, e.g. ``"US->IN"`` for a US-to-India transfer.
    """

    payment_id: str
    corridor: str = Field(description="Ordered country pair, e.g. 'US->IN'.")
    amount: float
    currency: str = Field(description="ISO-4217 currency code, e.g. 'EUR'.")
    anomaly_type: AnomalyType
    beneficiary: Beneficiary
    # Free-form fields describing the payment as received. Kept loose on
    # purpose: this is exactly the messy input the agents reason about.
    details: dict[str, str] = Field(default_factory=dict)


class CorrectionProposal(BaseModel):
    """A single agent's proposed fix for one anomaly."""

    agent_name: str
    field_to_fix: str = Field(description="Payment field to change, e.g. 'bic'.")
    proposed_value: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: CorrectionSource


class ComplianceVerdict(BaseModel):
    """A compliance agent's assessment of an anomaly on a corridor.

    NOTE: The compliance agent does not propose a correction. It validates
    whether a compliant correction is possible and reports any violations, so
    the coordinator can treat it as a gate/veto over the instruction agent's
    fix instead of a competing proposal outvoted by confidence.
    """

    compliant: bool = Field(description="True when no violation blocks a fix.")
    violations: list[str] = Field(
        default_factory=list,
        description="Human-readable violations; empty when compliant.",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    source: CorrectionSource


class ApprovalDecision(BaseModel):
    """A human's verdict on a low-confidence proposal."""

    approved: bool
    approver: str
    comment: str = ""


# region FEATURE-ON: human-approval-signal
# class ReviewState(BaseModel):
#     """Pending proposal + verdict shown to a human reviewer while a
#     correction is held for approval."""
#
#     proposal: CorrectionProposal
#     verdict: ComplianceVerdict | None = None
#
#
# endregion FEATURE-ON: human-approval-signal


class CorridorPattern(BaseModel):
    """A known, reusable correction for a (corridor, anomaly_type) pair.

    This is the unit stored in the passive corridor memory. A high-
    confidence pattern lets an agent short-circuit the LLM entirely.
    """

    corridor: str
    anomaly_type: AnomalyType
    beneficiary_bank_id: str | None = None
    field_to_fix: str
    proposed_value: str
    confidence: float = Field(ge=0.0, le=1.0)
    hit_count: int = 0


# region FEATURE-ON: settlement-confirmation
# # A downstream payment rail confirms settlement asynchronously: applying a
# # correction is not the end of the story, because the money still has to
# # settle on the rail. These models carry that confirmation outcome back
# # across the Temporal boundary (activity result to coordinator to outcome).
# class SettlementStatus(StrEnum):
#     """Lifecycle of a settlement on the downstream payment rail."""
#
#     PENDING = "pending"  # accepted by the rail, not yet settled
#     SETTLED = "settled"  # the rail has confirmed the funds settled
#
#
# class SettlementConfirmation(BaseModel):
#     """Result of polling the rail until the applied correction settles."""
#
#     reference: str  # opaque reference returned by apply_correction
#     status: SettlementStatus
#     poll_count: int  # number of poll cycles observed before settlement
#
#
# endregion FEATURE-ON: settlement-confirmation


class CorrectionOutcome(BaseModel):
    """The final result of the coordinator workflow."""

    payment_id: str
    applied: bool
    proposal: CorrectionProposal | None = None
    decision: ApprovalDecision | None = None
    # NOTE: The compliance verdict that gated this outcome, recorded so a held
    # correction can explain *why* (violations) and an applied one records the
    # verdict it was gated against -- which a human reviewer may have overridden
    # when approving a non-compliant hold. Optional: a failed-instruction
    # outcome has no verdict.
    verdict: ComplianceVerdict | None = None
    message: str = ""
    # region FEATURE-ON: settlement-confirmation
    # # NOTE: Downstream settlement confirmation, populated only after the
    # # long-running confirm_settlement activity reports SETTLED. Optional so the
    # # baseline outcome (with no settlement step) still validates unchanged.
    # settlement: SettlementConfirmation | None = None
    # endregion FEATURE-ON: settlement-confirmation
