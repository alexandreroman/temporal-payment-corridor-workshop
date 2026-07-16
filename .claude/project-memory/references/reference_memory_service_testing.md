---
name: "Testing the memory service across the memory-workflow FEATURE toggle"
description: "How memory/ and payments/ memory tests stay green in both FEATURE-OFF and FEATURE-ON states, plus the MemoryWorkflow start_local gotchas."
type: reference
---

# Testing the memory service across the memory-workflow FEATURE toggle

The `memory/` service tests and the `payments/` HTTP-client activity tests
must pass with the `memory-workflow` FEATURE both OFF and ON. Enabling the
FEATURE rewrites the route bodies in `memory/app.py`: reads/writes stop
calling `memory.store` directly and instead go through
`app.state.temporal_client` (a Temporal query / update). Three gotchas were
learned making every test green in both states.

## HTTP-level tests need a store-backed client stub to be toggle-robust

`memory/test_app.py` and `payments/test_memory.py` drive the FastAPI app
in-process via httpx `ASGITransport` (no sockets; `ASGITransport` does not run
lifespan events, so `app.state.temporal_client` is never populated). With the
FEATURE OFF the routes call `store` directly. With the FEATURE ON they read
`app.state.temporal_client`, which is unset — the routes raise `AttributeError`.

Fix: an autouse fixture sets `app.state.temporal_client` to a tiny stub whose
`get_workflow_handle(...).query(...)` / `.execute_update(...)` delegate to
`memory.store`. The stub is unused in the baseline and harmless there; with the
FEATURE ON it makes the routes resolve to the same in-memory store, so the exact
same HTTP-contract tests pass in both states with no live Temporal server. The
real workflow query/update path is covered separately by `memory/test_workflow.py`.

## MemoryWorkflow tests run under UnsandboxedWorkflowRunner

`memory/test_workflow.py` builds its `Worker` with
`temporalio.worker.UnsandboxedWorkflowRunner`. Two reasons: (1) MemoryWorkflow
holds only in-memory state and imports nothing nondeterministic, so the sandbox
buys no safety; (2) when a prior sandboxed-workflow test (e.g.
`payments/test_workflows.py`) has run in the same process, MemoryWorkflow's
sandbox validation fails with `RuntimeError: Failed validating workflow
MemoryWorkflow` (sandbox-importer state pollution). Running unsandboxed isolates
the tests from that and also lets the continue-as-new test's monkeypatched
`MAX_UPDATES_BEFORE_CONTINUE` reach the running workflow (the sandbox re-imports
the module, giving a fresh, unpatched class).

## Entity-workflow state is seeded in @workflow.init (no barrier query needed)

`MemoryWorkflow` seeds `self._patterns = dict(initial or {})` in its
`__init__`, decorated with `@workflow.init` so the initializer receives the same
arguments as `run` and is guaranteed to complete before any update/signal
handler executes. An `execute_update` fired immediately after `start_workflow`
therefore cannot be lost.

Previously `run` did the seeding, which was subject to a lost-write race: an
update delivered in the *same* first workflow task could be applied before the
seeding assignment and then clobbered by it. Tests worked around this with a
barrier query after starting and before any update. That workaround has been
removed now that seeding lives in `@workflow.init` — do not reintroduce it.
