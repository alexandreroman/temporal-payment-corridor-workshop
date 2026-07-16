"""Durable, audited corridor-memory workflow (the ``memory-workflow`` FEATURE).

This is the storage backend the memory service switches to when the workshop
``memory-workflow`` feature is enabled; in the baseline it is dormant, imported
only from the FEATURE-ON blocks in ``memory/app.py`` and never registered on a
worker.

``MemoryWorkflow`` is the *Entity Workflow* pattern: a single long-lived
instance with a well-known workflow id that holds all known correction patterns
in workflow state (no disk, no database). Reads are served by a Temporal
*query* (read-only, never recorded in history) and writes by a Temporal
*update* (synchronous, validated, and durably acknowledged). History is kept
bounded by continuing-as-new after a fixed number of updates, carrying the
accumulated state forward.

Because this file is loaded as a workflow module inside the Temporal sandbox,
models are imported through the sandbox passthrough exactly like the payments
workflows do.

Source: https://docs.temporal.io/develop/python/message-passing
"""

from __future__ import annotations

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from shared.models import AnomalyType, CorridorPattern


@workflow.defn
class MemoryWorkflow:
    """Singleton entity workflow holding the corridor-memory patterns.

    Query it (``lookup``) to read a known pattern; update it (``remember``) to
    learn a new one. Bounded via continue-as-new so the audit history never
    grows without limit.
    """

    WORKFLOW_ID = "corridor-memory"
    TASK_QUEUE = "memory"
    MAX_UPDATES_BEFORE_CONTINUE = 100

    @workflow.init
    def __init__(self, initial: dict[str, CorridorPattern] | None = None) -> None:
        # NOTE: seed state in the @workflow.init initializer, not in `run`. With
        # @workflow.init, __init__ receives the same arguments as `run` and is
        # guaranteed to complete before any update/signal handler executes, so an
        # early `remember` delivered in the very first workflow task cannot be
        # lost by a later seeding assignment.
        # Source: https://docs.temporal.io/develop/python/message-passing#workflow-initializer
        self._patterns: dict[str, CorridorPattern] = dict(initial or {})
        self._updates = 0

    @staticmethod
    def _key(corridor: str, anomaly_type: AnomalyType) -> str:
        return f"{corridor}|{anomaly_type}"

    @workflow.run
    async def run(self, initial: dict[str, CorridorPattern] | None = None) -> None:
        # State is seeded in @workflow.init, which receives this same `initial`
        # argument; `run` must not reassign self._patterns or it would clobber
        # writes accepted before it advances.
        await workflow.wait_condition(
            lambda: self._updates >= self.MAX_UPDATES_BEFORE_CONTINUE
        )
        # NOTE: drain in-flight update handlers before continue-as-new so no
        # accepted `remember` is lost from the carried-over state.
        # Source: https://docs.temporal.io/develop/python/message-passing#wait-for-message-handlers
        await workflow.wait_condition(workflow.all_handlers_finished)
        workflow.continue_as_new(args=[self._patterns])

    @workflow.update
    async def remember(self, pattern: CorridorPattern) -> None:
        self._patterns[self._key(pattern.corridor, pattern.anomaly_type)] = pattern
        self._updates += 1

    @remember.validator
    def _validate_remember(self, pattern: CorridorPattern) -> None:
        # NOTE: update validators run before the update is admitted to history;
        # rejecting here means an invalid write is never durably recorded — the
        # acknowledged-write advantage of Update over Signal.
        # Source: https://docs.temporal.io/develop/python/message-passing#validate-updates
        if not pattern.corridor or not pattern.field_to_fix:
            raise ValueError("corridor and field_to_fix must be non-empty")

    @workflow.query
    def lookup(
        self, corridor: str, anomaly_type: AnomalyType
    ) -> CorridorPattern | None:
        return self._patterns.get(self._key(corridor, anomaly_type))
