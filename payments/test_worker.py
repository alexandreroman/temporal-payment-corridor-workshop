from shared.models import (
    AnomalyType,
    ComplianceVerdict,
    CorrectionOutcome,
    CorrectionProposal,
    CorrectionSource,
    PaymentAnomaly,
)
from payments.activities import _correction_reference
from payments.workflows import GateDecision, _gate, _learned_pattern


def test_correction_reference_is_stable_for_same_inputs():
    a = _correction_reference("bic", "coordinator-abc")
    b = _correction_reference("bic", "coordinator-abc")
    assert a == b  # a retry of the activity must produce the same reference


def test_correction_reference_varies_by_workflow_and_field():
    assert _correction_reference("bic", "wf-1") != _correction_reference("bic", "wf-2")
    assert _correction_reference("bic", "wf-1") != _correction_reference("iban", "wf-1")


def _p(
    name: str, conf: float, source: CorrectionSource = CorrectionSource.MEMORY
) -> CorrectionProposal:
    return CorrectionProposal(
        agent_name=name,
        field_to_fix="bic",
        proposed_value="HDFCINBBXXX",
        rationale="test",
        confidence=conf,
        source=source,
    )


def _v(
    compliant: bool, conf: float = 0.9, violations: list[str] | None = None
) -> ComplianceVerdict:
    return ComplianceVerdict(
        compliant=compliant,
        violations=violations or ([] if compliant else ["currency mismatch"]),
        confidence=conf,
        source=CorrectionSource.LLM,
    )


def test_gate_applies_when_compliant_and_confident():
    decision, _ = _gate(_p("instruction_agent", 0.9), _v(True))
    assert decision is GateDecision.APPLY


def test_gate_reviews_when_not_compliant_even_if_confident():
    decision, message = _gate(_p("instruction_agent", 0.99), _v(False))
    assert decision is GateDecision.REVIEW
    assert "currency mismatch" in message


def test_gate_reviews_when_verdict_missing_fail_closed():
    decision, _ = _gate(_p("instruction_agent", 0.99), None)
    assert decision is GateDecision.REVIEW


def test_gate_reviews_when_compliant_but_low_confidence():
    decision, _ = _gate(_p("instruction_agent", 0.10), _v(True))
    assert decision is GateDecision.REVIEW


def test_gate_no_proposal_when_instruction_missing():
    decision, _ = _gate(None, _v(True))
    assert decision is GateDecision.NO_PROPOSAL


def test_compliance_verdict_and_outcome_carry_a_verdict():
    verdict = ComplianceVerdict(
        compliant=False,
        violations=["currency mismatch"],
        confidence=0.9,
        source=CorrectionSource.LLM,
    )
    assert verdict.violations == ["currency mismatch"]
    outcome = CorrectionOutcome(payment_id="pay-1", applied=False, verdict=verdict)
    assert outcome.verdict is verdict
    # Default is None so existing callers are unaffected.
    assert CorrectionOutcome(payment_id="pay-2", applied=True).verdict is None


def test_learned_pattern_captures_an_llm_reasoned_fix():
    anomaly = PaymentAnomaly(
        payment_id="pay-1",
        corridor="US->GB",
        amount=100.0,
        currency="GBP",
        anomaly_type=AnomalyType.WRONG_BIC,
    )
    pattern = _learned_pattern(
        anomaly, _p("instruction_agent", 0.9, CorrectionSource.LLM)
    )
    assert pattern is not None
    assert pattern.corridor == "US->GB"
    assert pattern.anomaly_type is AnomalyType.WRONG_BIC
    assert pattern.field_to_fix == "bic"
    assert pattern.proposed_value == "HDFCINBBXXX"
    assert pattern.confidence == 0.9


def test_learned_pattern_skips_memory_sourced_proposals():
    anomaly = PaymentAnomaly(
        payment_id="pay-2",
        corridor="US->IN",
        amount=500.0,
        currency="INR",
        anomaly_type=AnomalyType.WRONG_BIC,
    )
    assert _learned_pattern(anomaly, _p("instruction_agent", 0.95)) is None
