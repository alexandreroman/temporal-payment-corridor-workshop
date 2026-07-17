# 11 — Observability

> **Goal of this step.** Know where to *look*. This is a reference for the
> three observability surfaces the app exposes: one metrics endpoint,
> local tracing with Logfire, and the Temporal Web UI (including decoded
> payloads).

> **Start from a clean baseline.** Each page stands on its own. If you
> enabled features in other steps, reset first so nothing carries over:
>
> ```bash
> make feature-reset
> ```

## At a glance

|                       |                                                                                                                                                               |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Feature**           | none — always on (payload decoding needs `payload-encryption`)                                                                                                |
| **Key files**         | [`payments/main_worker.py`](../payments/main_worker.py), [`payments/activities.py`](../payments/activities.py), [`payments/memory.py`](../payments/memory.py) |
| **Temporal concepts** | SDK metrics, custom metrics, the Prometheus runtime, the Web UI                                                                                               |
| **Docs**              | [Observability](https://docs.temporal.io/develop/python/observability)                                                                                        |

## One metrics endpoint, two families

A single Prometheus/OpenMetrics endpoint serves *both* Temporal SDK
metrics and the application's own metrics. The wiring is in
[`payments/main_worker.py`](../payments/main_worker.py):

> **Order matters.** The Temporal `Runtime` (with its Prometheus exporter)
> is built *first*, before any client or worker, so the SDK metrics
> registry is wired up before anything else runs. The same runtime backs
> the application metrics emitted from activities — so one `/metrics`
> endpoint serves both.

Scrape it:

```bash
curl -s http://localhost:9464/metrics | grep -E '^(temporal_|corridor_)'
```

| Prefix       | Source                | Examples                                                                                                                                                             |
| ------------ | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `temporal_*` | Temporal SDK / worker | task queue, activity, workflow metrics                                                                                                                               |
| `corridor_*` | The app's activities  | `corridor_memory_lookups`, `corridor_corrections_applied`, `corridor_correction_confidence`, `corridor_correction_retries_alerted` (step [06](06-retry-alerting.md)) |

The `corridor_*` metrics are created through `activity.metric_meter()` in
[`payments/activities.py`](../payments/activities.py) and
[`payments/memory.py`](../payments/memory.py) — read those to see exactly
what is measured and how each series is tagged. The
`LogfirePlugin(..., metrics=False)` in the worker is deliberate: metrics
already flow through the Prometheus endpoint, so a second OTel-based
pipeline would be redundant.

![The merged /metrics endpoint showing temporal_* and corridor_* series](images/11-metrics-endpoint.png)

## Local tracing with Logfire

Every process configures Pydantic Logfire the same way:
`logfire.configure(service_name="payment-corridor", send_to_logfire=False)`.

> **Local-only, by design.** `send_to_logfire=False` means spans are
> produced locally for instrumentation but *nothing is shipped* to any
> backend — no token, no network. FastAPI apps call
> `logfire.instrument_fastapi(app)`, and the worker calls
> `instance.instrument_pydantic_ai()` so agent runs are traced too.

Note *where* Logfire is configured: in the modules that actually serve
requests (`payments/api.py`, `memory/app.py`), not in the thin `main.py`
bootstraps — because uvicorn's reload imports the app module in a
subprocess that never runs `main.py`. The Web UI has no such module: it
is static files served directly by the gateway, with no Python process
of its own.

## The Temporal Web UI

Reached through the gateway at <http://localhost:8080/temporal>. This is
your primary window into durable execution. Throughout the guide you use
it to:

- see the coordinator and its **child workflows** (step
  [01](01-getting-started.md), [02](02-durable-agents.md)),
- read **Event History** and match it to code (step
  [02](02-durable-agents.md)),
- watch a **Timer** (step [04](04-approval-timeout.md)) and **heartbeats**
  (step [07](07-settlement-confirmation.md)),
- **filter** executions by Search Attribute (step
  [08](08-search-attributes.md)),
- switch to the **`memory` namespace** for the Entity Workflow (step
  [10](10-memory-workflow.md)).

**Decoding encrypted payloads.** With `payload-encryption` on (step
[09](09-payload-encryption.md)), Event History shows ciphertext until the
UI calls the codec server. The dev server is already pointed at
`/codec` through the gateway, which injects the bearer token — so decoded
payloads appear with no manual configuration.

## Logging discipline

The [production-ready checklist](../production-ready-checklist.md) calls it
out, and the code follows it: logging goes through `workflow.logger` and
`activity.logger`, never `print`. `workflow.logger` is replay-aware (it
does not double-log on replay), which `print` cannot be.

## Checkpoint

- [ ] You can scrape both `temporal_*` and `corridor_*` from `/metrics`.
- [ ] You can name which metric each activity emits and how it is tagged.
- [ ] You know why Logfire is configured in the app module, not `main.py`.

---

Next: [12 — Testing durable code](12-testing.md).
