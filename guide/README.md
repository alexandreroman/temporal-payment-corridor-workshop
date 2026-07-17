# Payment Corridor Workshop — Learner Guide

Welcome. This guide is the step-by-step companion to the **Temporal
Payment Corridor** reference application. It walks you from a running
baseline to a production-shaped system, one durable-execution concept at
a time.

You do not build the app from scratch. The full application ships up
front; each concept is a dormant **feature** you switch on, read, run,
and observe. That way every step is a focused lesson on one Temporal or
Pydantic AI idea, backed by working code you can inspect.

## Who this is for

You are comfortable with Python and have already met Temporal's core
ideas (workflows, activities, workers, the dev server, the Web UI). You
work in or near payments, or you simply want a realistic domain to hang
durable-execution concepts on. No Kubernetes and no cloud account are
required — everything runs locally against a Temporal dev server.

If you have never seen Temporal before, skim the
[Temporal Python quickstart](https://docs.temporal.io/develop/python)
first, then come back here.

## How the guide is organised

The journey is split into three arcs. Start at the top and go in order:
each step assumes the concepts (and sometimes the enabled features) of
the ones before it.

### Arc 0 — Understand and run the baseline

| Step                             | Topic                          | What you learn                                                                 |
| -------------------------------- | ------------------------------ | ------------------------------------------------------------------------------ |
| [00](00-application-overview.md) | Application overview           | The domain, the architecture, the components, the request lifecycle            |
| [01](01-getting-started.md)      | Getting started                | Install, run the stack, correct your first payment                             |
| [02](02-durable-agents.md)       | Durable agents & orchestration | Coordinator, agent child workflows, memory-first gate, activities, determinism |

### Arc 1 — Reliability and control flow

| Step                                 | Topic                   | Feature                    | What you learn                                |
| ------------------------------------ | ----------------------- | -------------------------- | --------------------------------------------- |
| [03](03-human-approval-signal.md)    | Human-in-the-loop       | `human-approval-signal`    | Signals & queries, waiting for a human        |
| [04](04-approval-timeout.md)         | Bounded waiting         | `approval-timeout`         | Durable timers, `wait_condition` timeouts     |
| [05](05-non-retryable-validation.md) | Failure classification  | `non-retryable-validation` | Retryable vs non-retryable errors             |
| [06](06-retry-alerting.md)           | Reacting to retries     | `retry-alerting`           | Activity attempts, custom metrics             |
| [07](07-settlement-confirmation.md)  | Long-running activities | `settlement-confirmation`  | Heartbeats, cancellation, replay & versioning |

### Arc 2 — Production concerns

| Step                           | Topic                       | Feature              | What you learn                                             |
| ------------------------------ | --------------------------- | -------------------- | ---------------------------------------------------------- |
| [08](08-search-attributes.md)  | Fleet-wide visibility       | `search-attributes`  | Search Attributes, the Visibility API, CLI filters         |
| [09](09-payload-encryption.md) | Data at rest & in flight    | `payload-encryption` | Payload codecs, the codec server, the gateway              |
| [10](10-memory-workflow.md)    | Durable state as a workflow | `memory-workflow`    | The Entity Workflow pattern, update/query, continue-as-new |

### Cross-cutting references

| Step                      | Topic                | What you learn                                                   |
| ------------------------- | -------------------- | ---------------------------------------------------------------- |
| [11](11-observability.md) | Observability        | The one metrics endpoint, Logfire, the Web UI, decoding payloads |
| [12](12-testing.md)       | Testing durable code | The test suite, replay tests, mocking the model                  |
| [13](13-wrap-up.md)       | Wrap-up              | Reset the app, production-ready checklist, where to go next      |

## The workshop loop

Every feature step follows the same rhythm, so you always know what to
do next:

1. **Preview** the change without touching anything:
   `make feature-diff NAME=<feature>`.
2. **Enable** it everywhere it appears: `make feature-enable NAME=<feature>`.
3. **Read** the newly-live code — the guide links each block by file and
   line, and the code itself carries teaching comments with links to the
   official docs.
4. **Run** a scenario and **observe** the result in the terminal, the Web
   UI, and the metrics endpoint.
5. **Revert** when you want a clean slate: `make feature-disable NAME=<feature>`.

> [!TIP]
> **Reading tip.** In VS Code (with the recommended
> `zokugun.explicit-folding` extension) every dormant `# region
> FEATURE-ON:` block is folded away, so you see the base application
> first and expand a region to study it. See the
> [conventions in CLAUDE.md](../CLAUDE.md) for how the feature blocks
> work.

## `NOTE:` markers

Throughout the source, a comment prefixed with `NOTE:` flags a
non-obvious, production-relevant decision worth pausing on — an
idempotency key, a fail-closed gate, a heartbeat timeout. When a step
tells you to "read the code," the `NOTE:` comments are where the lesson
lives.

## Conventions in this guide

- **Source links** point into the repository, e.g.
  [`payments/workflows.py`](../payments/workflows.py). On GitHub you can
  append a line range (`#L290-L338`) to jump straight to a block.
- **Docs links** point at the official
  [Temporal](https://docs.temporal.io) and
  [Pydantic AI](https://ai.pydantic.dev) documentation. The same links
  appear inline in the code as `Source:` comments.
- **Screenshots** are referenced as
  `![caption](images/<name>.png)`. They are added to the
  [`images/`](images/) folder separately; until then you will see the
  caption and can reproduce the view yourself by following the steps.

Ready? Start with the [application overview](00-application-overview.md).
