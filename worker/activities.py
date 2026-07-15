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

    reference = (
        f"corr-{proposal.field_to_fix}-{abs(hash(proposal.proposed_value)) % 100000}"
    )
    activity.logger.info(
        "Applied %s=%s (ref %s)",
        proposal.field_to_fix,
        proposal.proposed_value,
        reference,
    )
    return reference


# --- STEP: saga-compensation ---
# @activity.defn
# async def revert_correction(reference: str) -> None:
#     """Undo a previously applied correction (saga compensation)."""
#     activity.logger.warning("Reverting correction %s", reference)
# --- END STEP: saga-compensation ---
