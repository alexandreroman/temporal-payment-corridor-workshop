"""Non-agent activities: applying the fix.

Activities are where side effects live. They also emit the *application*
metrics (memory hit rate, corrections applied, confidence). Those go
through :func:`temporalio.activity.metric_meter`, which is backed by the
same runtime as the Temporal SDK metrics — so they surface on the one
Prometheus endpoint configured in ``worker/main.py``, next to the built-in
``temporal_*`` series but under their own ``corridor_*`` names.
"""

from __future__ import annotations

# --- FEATURE: settlement-confirmation ---
# import asyncio
# import os
# --- END FEATURE: settlement-confirmation ---

from temporalio import activity

from shared.models import CorrectionProposal

# --- FEATURE: settlement-confirmation ---
# from shared.models import SettlementConfirmation, SettlementStatus
# --- END FEATURE: settlement-confirmation ---


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


# --- FEATURE: settlement-confirmation ---
# # Poll cadence is read from the environment (with safe defaults) INSIDE the
# # activity. Reading configuration and waiting on wall-clock time are side
# # effects, so they belong in an activity, never in deterministic workflow code.
# # Source: https://docs.temporal.io/activities
# _SETTLEMENT_POLL_CYCLES = int(os.environ.get("CORRIDOR_SETTLEMENT_POLL_CYCLES", "3"))
# _SETTLEMENT_POLL_INTERVAL_SECONDS = float(
#     os.environ.get("CORRIDOR_SETTLEMENT_POLL_INTERVAL_SECONDS", "0.5")
# )
#
#
# @activity.defn
# async def confirm_settlement(reference: str) -> SettlementConfirmation:
#     """Poll a downstream payment rail until the applied correction settles.
#
#     This is a *long-running activity*: it stays alive across several poll
#     cycles and reports progress with ``activity.heartbeat(...)``. The
#     coordinator bounds it with a ``heartbeat_timeout`` so a stalled poll is
#     detected, retried, and resumed from where it stopped. No real network call
#     is made; the poll is simulated so the workshop stays fast and offline.
#     Source: https://docs.temporal.io/encyclopedia/detecting-activity-failures#activity-heartbeat
#     """
#     # NOTE: Resume from the last reported cycle. heartbeat_details carries the
#     # payload from the most recent heartbeat of the PREVIOUS attempt, so a
#     # retried execution continues instead of restarting from zero.
#     # Source: https://docs.temporal.io/encyclopedia/detecting-activity-failures#activity-heartbeat
#     info = activity.info()
#     completed_cycles = int(info.heartbeat_details[0]) if info.heartbeat_details else 0
#
#     try:
#         while completed_cycles < _SETTLEMENT_POLL_CYCLES:
#             # Simulate one poll of the rail. A real implementation would issue a
#             # status request here; the wait is short so the demo stays green.
#             await asyncio.sleep(_SETTLEMENT_POLL_INTERVAL_SECONDS)
#             completed_cycles += 1
#             # NOTE: Heartbeat after each completed cycle. This checkpoints
#             # progress (so a retry resumes here) AND is how cancellation is
#             # delivered: once the workflow is cancelled this call raises
#             # asyncio.CancelledError.
#             # Source: https://docs.temporal.io/develop/python/cancellation
#             activity.heartbeat(completed_cycles)
#     except asyncio.CancelledError:
#         # NOTE: Cancellation arrives through the heartbeat above; re-raise it so
#         # Temporal records the activity as cancelled. Real cleanup (releasing any
#         # rail-side resources) would happen here before re-raising.
#         activity.logger.info("Settlement polling cancelled for %s", reference)
#         raise
#
#     activity.logger.info(
#         "Settlement confirmed for %s after %d poll cycle(s)",
#         reference,
#         completed_cycles,
#     )
#     return SettlementConfirmation(
#         reference=reference,
#         status=SettlementStatus.SETTLED,
#         poll_count=completed_cycles,
#     )
#
#
# --- END FEATURE: settlement-confirmation ---
