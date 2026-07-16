---
name: "Testing TemporalAgent-based workflows under start_local"
description: "How to mock the model and avoid a sandbox import crash when testing PydanticAIWorkflow/TemporalAgent workflows"
type: reference
---

# Testing TemporalAgent-based workflows under start_local

`payments/test_workflows.py` runs real workflow code against
`temporalio.testing.WorkflowEnvironment.start_local()`. Two non-obvious
things about this setup are worth knowing before writing more tests in
this area.

## `Agent.override(model=...)` does not reach the model activity

Pydantic AI's documented way to test an agent without a network call is
`agent.override(model=TestModel())` around the call. Under `TemporalAgent`
this does **not** work: model requests are dispatched as Temporal
*activities*, independent tasks picked up by the worker's activity
poller — not plain nested Python calls — so the contextvar `override()`
sets around the workflow call never reaches the activity's execution
context. Empirically, wrapping `client.execute_workflow(...)` in the
override still makes a real call to the configured provider and fails
authentication.

The reliable alternative: construct a *different* `Agent` directly with
`pydantic_ai.models.test.TestModel`, wrap it in its own `TemporalAgent`,
and register a stand-in `@workflow.defn(name="<RealWorkflowName>")` class
running it, on a test-only `Worker`. Child/parent workflows address each
other by **type name**, not Python object identity, so registering a
different implementation under the real name is enough — no production
code changes.

## `cryptography.fernet.Fernet` needs `imports_passed_through()` too

Importing `from cryptography.fernet import Fernet` at the top level of a
module that also defines `@workflow.defn` classes crashes `Worker`
construction with a low-level `SystemError:
Objects/dictobject.c:1882: bad argument to internal function`. The
sandboxed workflow runner re-imports that module's dependencies, and
`cryptography`'s Rust extension cannot survive being loaded a second time.
Fix: import `Fernet` inside the same
`with workflow.unsafe.imports_passed_through():` block already used for
`pydantic_ai`, `shared.encryption`, `shared.models`, and `payments.*` (the
same convention `payments/workflows.py` / `payments/agents.py` /
`payments/memory.py` already follow).
