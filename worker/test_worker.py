from worker.activities import _correction_reference


def test_correction_reference_is_stable_for_same_inputs():
    a = _correction_reference("iban", "coordinator-abc")
    b = _correction_reference("iban", "coordinator-abc")
    assert a == b  # a retry of the activity must produce the same reference


def test_correction_reference_varies_by_workflow_and_field():
    assert _correction_reference("iban", "wf-1") != _correction_reference(
        "iban", "wf-2"
    )
    assert _correction_reference("iban", "wf-1") != _correction_reference("bic", "wf-1")
