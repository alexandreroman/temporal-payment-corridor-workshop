"""Non-agent activities: passive corridor memory and applying the fix.

Activities are where side effects live. They also emit the *application*
metrics (memory hit rate, corrections applied, confidence). Those go
through :func:`temporalio.activity.metric_meter`, which is backed by the
same runtime as the Temporal SDK metrics — so they surface on the one
Prometheus endpoint configured in ``worker.py``, next to the built-in
``temporal_*`` series but under their own ``corridor_*`` names.
"""

from __future__ import annotations

from temporalio import activity

from models import AnomalyType, CorrectionProposal, CorridorPattern

# ---------------------------------------------------------------------------
# Passive corridor memory
#
# For the workshop's starting point this is a plain in-process dict, pre-
# seeded with one known pattern so the demo runs end-to-end offline (the
# matching anomaly hits the cache and never calls an LLM). A later step
# swaps this backing store for the long-running corridor-memory *workflow*
# (see the STEP block in workflows.py and read_corridor_memory below).
# ---------------------------------------------------------------------------
_MEMORY: dict[tuple[str, AnomalyType], CorridorPattern] = {
    ("US->IN", AnomalyType.WRONG_IBAN): CorridorPattern(
        corridor="US->IN",
        anomaly_type=AnomalyType.WRONG_IBAN,
        field_to_fix="iban",
        proposed_value="DE89370400440532013000",
        confidence=0.95,
    ),
}


@activity.defn
async def read_corridor_memory(
    corridor: str, anomaly_type: AnomalyType
) -> CorridorPattern | None:
    """Look up a known correction pattern for a corridor + anomaly type."""
    pattern = _MEMORY.get((corridor, anomaly_type))

    meter = activity.metric_meter()
    lookups = meter.create_counter(
        "corridor_memory_lookups", "Passive corridor-memory lookups"
    )
    lookups.add(1, {"corridor": corridor, "result": "hit" if pattern else "miss"})

    if pattern is not None:
        pattern.hit_count += 1
        activity.logger.info("Corridor-memory hit for %s/%s", corridor, anomaly_type)
    return pattern

    # --- STEP: corridor-memory-workflow ---
    # Route reads through the long-running corridor-memory workflow instead
    # of the in-process dict. The activity queries the workflow.
    #
    # from temporalio.client import Client
    # from workflows import CorridorMemoryWorkflow
    #
    # client: Client = activity.client()  # provided by the worker
    # handle = client.get_workflow_handle(CorridorMemoryWorkflow.WORKFLOW_ID)
    # return await handle.query(
    #     CorridorMemoryWorkflow.lookup, args=[corridor, anomaly_type]
    # )
    # --- END STEP: corridor-memory-workflow ---


@activity.defn
async def write_corridor_memory(pattern: CorridorPattern) -> None:
    """Remember a newly learned correction pattern."""
    _MEMORY[(pattern.corridor, pattern.anomaly_type)] = pattern
    activity.logger.info(
        "Corridor-memory learned pattern for %s/%s",
        pattern.corridor,
        pattern.anomaly_type,
    )

    # --- STEP: corridor-memory-workflow ---
    # Persist the pattern by signalling the corridor-memory workflow instead.
    #
    # from temporalio.client import Client
    # from workflows import CorridorMemoryWorkflow
    #
    # client: Client = activity.client()
    # handle = client.get_workflow_handle(CorridorMemoryWorkflow.WORKFLOW_ID)
    # await handle.signal(CorridorMemoryWorkflow.remember, pattern)
    # --- END STEP: corridor-memory-workflow ---


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

    reference = f"corr-{proposal.field_to_fix}-{abs(hash(proposal.proposed_value)) % 100000}"
    activity.logger.info(
        "Applied %s=%s (ref %s)", proposal.field_to_fix, proposal.proposed_value, reference
    )
    return reference


# --- STEP: saga-compensation ---
# @activity.defn
# async def revert_correction(reference: str) -> None:
#     """Undo a previously applied correction (saga compensation)."""
#     activity.logger.warning("Reverting correction %s", reference)
# --- END STEP: saga-compensation ---
