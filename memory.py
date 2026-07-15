"""Passive corridor-memory feature, bundled in one place.

This module gathers everything that makes up the passive corridor memory so
the feature is easy to find and to swap out:

  * the in-process starting-point store (``_MEMORY``),
  * the ``read_corridor_memory`` / ``write_corridor_memory`` activities the
    agents use, and
  * the long-running ``CorridorMemoryWorkflow`` (bounded via continue-as-new).

Because this file is loaded as a workflow module inside the Temporal sandbox,
models are imported through the sandbox passthrough exactly like
``workflows.py`` does.
"""

from __future__ import annotations

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from models import AnomalyType, CorridorPattern

# ---------------------------------------------------------------------------
# Passive corridor memory
#
# For the workshop's starting point this is a plain in-process dict, pre-
# seeded with one known pattern so the demo runs end-to-end offline (the
# matching anomaly hits the cache and never calls an LLM). A later step
# swaps this backing store for the long-running corridor-memory *workflow*
# (see the STEP block below and read_corridor_memory below).
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
    #
    # client: Client = activity.client()
    # handle = client.get_workflow_handle(CorridorMemoryWorkflow.WORKFLOW_ID)
    # await handle.signal(CorridorMemoryWorkflow.remember, pattern)
    # --- END STEP: corridor-memory-workflow ---


@workflow.defn
class CorridorMemoryWorkflow:
    """Long-running passive corridor memory, bounded via continue-as-new.

    Holds known correction patterns in workflow state. Agents (through the
    ``read_corridor_memory`` activity) query it before calling a model, and
    learned patterns are added via the ``remember`` signal. History is kept
    small by continuing-as-new after a fixed number of updates.
    """

    WORKFLOW_ID = "corridor-memory"
    MAX_UPDATES_BEFORE_CONTINUE = 100

    def __init__(self) -> None:
        self._patterns: dict[str, CorridorPattern] = {}
        self._updates = 0

    @staticmethod
    def _key(corridor: str, anomaly_type: AnomalyType) -> str:
        return f"{corridor}|{anomaly_type}"

    @workflow.run
    async def run(self, initial: dict[str, CorridorPattern] | None = None) -> None:
        self._patterns = dict(initial or {})
        await workflow.wait_condition(
            lambda: self._updates >= self.MAX_UPDATES_BEFORE_CONTINUE
        )
        workflow.continue_as_new(args=[self._patterns])

    @workflow.signal
    async def remember(self, pattern: CorridorPattern) -> None:
        self._patterns[self._key(pattern.corridor, pattern.anomaly_type)] = pattern
        self._updates += 1

    @workflow.query
    def lookup(
        self, corridor: str, anomaly_type: AnomalyType
    ) -> CorridorPattern | None:
        return self._patterns.get(self._key(corridor, anomaly_type))
