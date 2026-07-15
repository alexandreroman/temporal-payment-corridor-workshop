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

    WRONG_IBAN = "wrong_iban"
    MISSING_INTERMEDIARY_BANK = "missing_intermediary_bank"
    CURRENCY_MISMATCH = "currency_mismatch"


class CorrectionSource(StrEnum):
    """Where a proposed correction came from."""

    MEMORY = "memory"  # matched a known pattern in passive corridor memory
    LLM = "llm"  # produced by an agent calling a model


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
    # Free-form fields describing the payment as received. Kept loose on
    # purpose: this is exactly the messy input the agents reason about.
    details: dict[str, str] = Field(default_factory=dict)


class CorrectionProposal(BaseModel):
    """A single agent's proposed fix for one anomaly."""

    agent_name: str
    field_to_fix: str = Field(description="Payment field to change, e.g. 'iban'.")
    proposed_value: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: CorrectionSource


class ApprovalDecision(BaseModel):
    """A human's verdict on a low-confidence proposal."""

    approved: bool
    approver: str
    comment: str = ""


class CorridorPattern(BaseModel):
    """A known, reusable correction for a (corridor, anomaly_type) pair.

    This is the unit stored in the passive corridor memory. A high-
    confidence pattern lets an agent short-circuit the LLM entirely.
    """

    corridor: str
    anomaly_type: AnomalyType
    field_to_fix: str
    proposed_value: str
    confidence: float = Field(ge=0.0, le=1.0)
    hit_count: int = 0


class CorrectionOutcome(BaseModel):
    """The final result of the coordinator workflow."""

    payment_id: str
    applied: bool
    proposal: CorrectionProposal | None = None
    decision: ApprovalDecision | None = None
    message: str = ""
