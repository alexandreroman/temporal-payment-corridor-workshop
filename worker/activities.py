"""Non-agent activities: applying the fix.

Activities are where side effects live. They also emit the *application*
metrics (memory hit rate, corrections applied, confidence). Those go
through :func:`temporalio.activity.metric_meter`, which is backed by the
same runtime as the Temporal SDK metrics — so they surface on the one
Prometheus endpoint configured in ``worker/main.py``, next to the built-in
``temporal_*`` series but under their own ``corridor_*`` names.
"""

from __future__ import annotations

# region FEATURE-ON: retry-alerting
# import os
# endregion FEATURE-ON: retry-alerting

# region FEATURE-ON: settlement-confirmation
# import asyncio
# import os
# endregion FEATURE-ON: settlement-confirmation

from temporalio import activity

# region FEATURE-ON: non-retryable-validation
# from temporalio.exceptions import ApplicationError
# endregion FEATURE-ON: non-retryable-validation

from shared.models import CorrectionProposal

# region FEATURE-ON: settlement-confirmation
# from shared.models import SettlementConfirmation, SettlementStatus
# endregion FEATURE-ON: settlement-confirmation


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


# region FEATURE-ON: non-retryable-validation
# # NOTE: Hand-operated fault switch for the workshop. Flip to True to force the
# # non-retryable path without touching the seeded (valid) correction; a learner
# # does this by hand. Default False keeps the happy path green.
# _SIMULATE_INVALID_CORRECTION = False
#
#
# def _is_valid_iban(value: str) -> bool:
#     """Cheap structural check that ``value`` looks like an IBAN.
#
#     NOTE: This is a lightweight FORMAT screen (length + coarse layout), NOT a
#     full ISO 13616 mod-97 checksum validation. It is kept deliberately simple
#     and readable for the workshop; a production system must verify the checksum.
#     Source: https://en.wikipedia.org/wiki/International_Bank_Account_Number
#     """
#     compact = value.replace(" ", "").upper()
#     # An IBAN is 15-34 characters: a 2-letter country code, 2 check digits, then
#     # a country-specific account number (BBAN).
#     if not 15 <= len(compact) <= 34:
#         return False
#     if not (compact[:2].isalpha() and compact[2:4].isdigit()):
#         return False
#     return compact[4:].isalnum()
#
#
# endregion FEATURE-ON: non-retryable-validation

# region FEATURE-ON: retry-alerting
# # NOTE: Hand-operated fault switch for the workshop. Flip to True to make
# # apply_correction fail with a RETRYABLE error on its first attempts and then
# # succeed, so a learner can watch the alert counter climb before the correction
# # completes. Default False keeps the happy path green (success on attempt 1).
# _SIMULATE_TRANSIENT_RAIL_OUTAGE = False
# # Attempt number at or above which the retry-alert metric is emitted. Read from
# # the environment (with a safe default) so it can be tuned without a code change.
# # Configuration reads are side effects, so they belong in an activity's module,
# # never in deterministic workflow code.
# _RETRY_ALERT_THRESHOLD = int(os.environ.get("CORRIDOR_RETRY_ALERT_THRESHOLD", "2"))
# endregion FEATURE-ON: retry-alerting


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

    # region FEATURE-ON: non-retryable-validation
    # # A malformed correction is a PERMANENT error: retrying it wastes time and
    # # can never self-heal, so we stop immediately instead of burning the retry
    # # budget. This deliberately contrasts with the RetryPolicy(maximum_attempts=3)
    # # the coordinator attaches to this activity, which only helps for TRANSIENT
    # # failures.
    # if _SIMULATE_INVALID_CORRECTION or not _is_valid_iban(proposal.proposed_value):
    #     # NOTE: non_retryable=True tells Temporal to fail the activity at once and
    #     # skip the remaining retry attempts. Use it for errors that can never
    #     # succeed on a retry (bad input, validation failures), as opposed to
    #     # transient ones (a network blip) that the RetryPolicy is meant to absorb.
    #     # Source: https://docs.temporal.io/references/failures#non-retryable-errors
    #     raise ApplicationError(
    #         f"Malformed correction, refusing to apply: {proposal.proposed_value!r}",
    #         non_retryable=True,
    #     )
    # endregion FEATURE-ON: non-retryable-validation

    # region FEATURE-ON: retry-alerting
    # # NOTE: activity.info().attempt is the current attempt number; it starts at 1
    # # and the server increments it on every retry. It lets an activity notice it
    # # is being retried and react — here, raise an operational alert once retries
    # # pile up. Source: https://docs.temporal.io/references/failures#activity-retries
    # attempt = activity.info().attempt
    # if attempt >= _RETRY_ALERT_THRESHOLD:
    #     # Retry Alerting via Metrics: surface persistent failures to operators
    #     # through the same meter that backs the Prometheus endpoint, so a climbing
    #     # counter can drive a dashboard or an alert rule.
    #     alerted = meter.create_counter(
    #         "corridor_correction_retries_alerted",
    #         "Corrections whose retries crossed the alert threshold",
    #     )
    #     # NOTE: corridor / anomaly type are not carried on CorrectionProposal, so
    #     # we tag with the same identifying attributes as the sibling corridor_*
    #     # counters above (field + source) to keep the metric series consistent.
    #     alerted.add(1, {"field": proposal.field_to_fix, "source": proposal.source})
    # if _SIMULATE_TRANSIENT_RAIL_OUTAGE and attempt < _RETRY_ALERT_THRESHOLD + 1:
    #     # NOTE: A plain exception is RETRYABLE by default in Temporal (only
    #     # ApplicationError(non_retryable=True) or exceeding the RetryPolicy stops
    #     # the retries), so Temporal retries per the coordinator's policy. Bounding
    #     # the failure to attempt < _RETRY_ALERT_THRESHOLD + 1 lets the correction
    #     # still succeed within maximum_attempts=3, after the alert has fired.
    #     # Source: https://docs.temporal.io/references/failures#retryable-vs-non-retryable
    #     raise RuntimeError(f"Simulated transient rail outage (attempt {attempt})")
    # endregion FEATURE-ON: retry-alerting

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


# region FEATURE-ON: settlement-confirmation
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
# endregion FEATURE-ON: settlement-confirmation
