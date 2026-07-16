"""Non-agent activities: applying the fix.

Activities are where side effects live. They also emit the *application*
metrics (memory hit rate, corrections applied, confidence). Those go
through :func:`temporalio.activity.metric_meter`, which is backed by the
same runtime as the Temporal SDK metrics — so they surface on the one
Prometheus endpoint configured in ``worker/main.py``, next to the built-in
``temporal_*`` series but under their own ``corridor_*`` names.
"""

from __future__ import annotations

from temporalio import activity

from shared.models import CorrectionProposal


def _correction_reference(field_to_fix: str, workflow_id: str) -> str:
    """Build a stable, idempotent reference for an applied correction.

    Derived from the coordinator's workflow id (unique per correction) and the
    field, so a retried or replayed activity yields the SAME reference and the
    downstream payment system can dedupe instead of double-applying. Activities
    can run more than once (worker crash, transient failure, retry), so their
    external effects must be idempotent.
    Source: https://docs.temporal.io/activities#idempotency
    """
    return f"corr-{field_to_fix}-{workflow_id}"


@activity.defn
async def apply_correction(proposal: CorrectionProposal) -> str:
    """Apply the approved correction to the downstream payment system.

    Returns an opaque reference for the applied change. In a real system
    this would call the core banking / payment rail; here it is simulated.
    """
    meter = activity.metric_meter()
    applied = meter.create_counter(
        "corridor_corrections_applied", "Corrections applied to payments"
    )
    confidence = meter.create_histogram_float(
        "corridor_correction_confidence", "Confidence of applied corrections"
    )
    applied.add(1, {"field": proposal.field_to_fix, "source": proposal.source})
    confidence.record(proposal.confidence, {"source": proposal.source})

    # NOTE: Idempotency key from the (unique) coordinator workflow id, NOT hash():
    # a retry of this activity must not apply a second, differently-referenced
    # correction. Source: https://docs.temporal.io/activities#idempotency
    #
    # workflow_id is always populated inside an activity execution; assert it
    # so the type checker knows the idempotency key can never be None.
    workflow_id = activity.info().workflow_id
    assert workflow_id is not None
    reference = _correction_reference(proposal.field_to_fix, workflow_id)
    activity.logger.info(
        "Applied %s=%s (ref %s)",
        proposal.field_to_fix,
        proposal.proposed_value,
        reference,
    )
    return reference
