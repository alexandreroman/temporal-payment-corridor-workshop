from shared.models import CorrectionProposal, CorrectionSource
from payments.activities import _correction_reference
from payments.workflows import _select_best


def test_correction_reference_is_stable_for_same_inputs():
    a = _correction_reference("bic", "coordinator-abc")
    b = _correction_reference("bic", "coordinator-abc")
    assert a == b  # a retry of the activity must produce the same reference


def test_correction_reference_varies_by_workflow_and_field():
    assert _correction_reference("bic", "wf-1") != _correction_reference("bic", "wf-2")
    assert _correction_reference("bic", "wf-1") != _correction_reference("iban", "wf-1")


def _p(name: str, conf: float) -> CorrectionProposal:
    return CorrectionProposal(
        agent_name=name,
        field_to_fix="bic",
        proposed_value="HDFCINBBXXX",
        rationale="test",
        confidence=conf,
        source=CorrectionSource.MEMORY,
    )


def test_select_best_picks_highest_confidence():
    best = _select_best([_p("a", 0.6), _p("b", 0.9)])
    assert best is not None and best.agent_name == "b"


def test_select_best_ignores_a_failed_agent():
    best = _select_best([_p("a", 0.7), RuntimeError("agent b crashed")])
    assert best is not None and best.agent_name == "a"


def test_select_best_returns_none_when_all_agents_fail():
    assert _select_best([RuntimeError("x"), ValueError("y")]) is None


def test_compliance_verdict_and_outcome_carry_a_verdict():
    from shared.models import ComplianceVerdict, CorrectionOutcome, CorrectionSource

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
