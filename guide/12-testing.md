# 12 — Testing durable code

> [!NOTE]
> **Goal of this step.** Learn how the app is tested — and what is
> *distinctive* about testing durable workflows: replay tests for
> determinism, and mocking the model so agent tests never hit the network.

## At a glance

- **Feature:** none — the test suite is always present
- **Key files:** [`payments/test_replay.py`](../payments/test_replay.py),
  [`payments/test_workflows.py`](../payments/test_workflows.py),
  [`payments/test_agents.py`](../payments/test_agents.py)
- **Temporal concepts:** `Replayer`, captured history, `WorkflowEnvironment`,
  mocking the model
- **Docs:** [Testing suite](https://docs.temporal.io/develop/python/testing-suite)

> [!IMPORTANT]
> **Start from a clean baseline.** Each page stands on its own. If you
> enabled features in other steps, reset first so nothing carries over:
>
> ```bash
> make feature-reset
> ```

## Running the suite

```bash
make check      # lint + tests
make test       # tests only
```

The suite covers every package: payments (workflows, activities, API,
agents, replay), the memory service (store, HTTP app, and the durable
workflow), the simulator scenarios, the encryption codec, and the feature
toggle tool itself. Browse them alongside the code:
`payments/test_*.py`, `memory/test_*.py`, `shared/test_encryption.py`,
`simulator/test_scenarios.py`, `tools/test_features.py`.

## Replay tests: guarding determinism

The standout is [`payments/test_replay.py`](../payments/test_replay.py).
Read its docstring — it explains the whole idea:

> [!NOTE]
> Temporal recovers a running workflow by **replaying** its recorded event
> history against the current code. If a change alters the sequence of
> decisions a workflow makes (reordering awaited calls, adding one
> conditionally, changing what a child is passed), replay diverges from
> history and the instance gets stuck. A replay test catches that class of
> bug at *test time*.

The test does **not** run the workflow. It feeds a previously captured
history (`payments/testdata/coordinator-history.json`) to
`temporalio.worker.Replayer`, which re-executes it against whatever the
coordinator looks like *now*.

You met this in steps [07](07-settlement-confirmation.md) and
[08](08-search-attributes.md): enabling a feature that changes the
coordinator's shape **intentionally** breaks the replay test, because the
committed fixture was captured with those features off. That failure is the
lesson — in production you would reach for
[versioning/patching](https://docs.temporal.io/develop/python/versioning)
instead of silently recapturing.

### Regenerating the fixture

If you want the replay test green while a shape-changing feature stays
enabled, recapture the fixture from a real run. With the dev stack up
(`make dev`), the coordinator and the corridor-memory service it reads
over HTTP are already running, so there is no separate service to start.

Capture is a two-step flow because each correction gets a random workflow
id. Run the simulator, note the `workflow: correction-pmt-XXXX` line it
prints, then pass that id to `capture-history`:

```bash
make simulator                                        # prints the workflow id
make capture-history WORKFLOW_ID=correction-pmt-XXXX  # writes the fixture
```

The default `memory-hit` scenario replays the seeded `US->IN` /
`WRONG_BIC` anomaly: a guaranteed memory hit, no model call, and the same
history shape as the committed fixture. It closes in under a second, so by
capture time the workflow is complete and its full history is available.

The target shells out to the `temporal` CLI and `jq` (both must be on your
`PATH`). To restore the committed baseline:
`git checkout payments/testdata/coordinator-history.json`.

## Testing agents without the network

Agent tests must never call a real model. See
[`payments/test_agents.py`](../payments/test_agents.py) and
[`payments/test_workflows.py`](../payments/test_workflows.py): the model is
mocked so tests are fast, deterministic, and offline — matching the
checklist item "the model/LLM is mocked in agent tests: no network calls."

> [!NOTE]
> **A gotcha worth knowing.** When testing `TemporalAgent`-based workflows
> under a local test environment, `Agent.override(model=...)` does *not*
> reach the model activity that Pydantic AI offloads to. Register a
> `TestModel` stand-in under the real workflow name instead, and remember
> that Fernet needs `imports_passed_through()` too. The test files show the
> working pattern.

## What good coverage looks like here

Temporal's [pre-production testing best practices](https://docs.temporal.io/best-practices/pre-production-testing)
are the rubric:

- [ ] Failure paths are tested: retries exhausted, worker restart,
      cancellation.
- [ ] A replay test replays captured history through `Replayer` to catch
      determinism regressions.
- [ ] The model/LLM is mocked in agent tests: no network calls.

## Checkpoint

- [ ] `make check` passes on the baseline (no features enabled).
- [ ] You can explain what a replay test proves — and why it *should* fail
      after enabling a shape-changing feature.
- [ ] You can explain why agent tests mock the model.

---

Next: [13 — Wrap-up](13-wrap-up.md).
