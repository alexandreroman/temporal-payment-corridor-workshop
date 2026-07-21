# 11 — Observability

> [!NOTE]
> **Goal of this step.** Know where to *look*. This is a reference for the
> observability surfaces the app exposes: one metrics endpoint (local, and
> in Temporal Cloud), and the Temporal Web UI (including decoded payloads).

## At a glance

- **Feature:** none — always on (payload decoding needs `payload-encryption`)
- **Key files:** [`payments/main_worker.py`](../payments/main_worker.py),
  [`payments/activities.py`](../payments/activities.py),
  [`payments/memory.py`](../payments/memory.py)
- **Temporal concepts:** SDK metrics, custom metrics, the Prometheus runtime,
  Temporal Cloud metrics, the Temporal Web UI
- **Docs:** [Observability](https://docs.temporal.io/develop/python/observability)
  · [Temporal Cloud metrics](https://docs.temporal.io/cloud/metrics)

> [!IMPORTANT]
> **Start from a clean baseline.** Each page stands on its own. If you
> enabled features in other steps, reset first so nothing carries over:
>
> ```bash
> make feature-reset
> ```

## One metrics endpoint, two families

A single Prometheus/OpenMetrics endpoint serves *both* Temporal SDK
metrics and the application's own metrics. The wiring is in
[`payments/main_worker.py`](../payments/main_worker.py):

> [!NOTE]
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
what is measured and how each series is tagged.

A trimmed sample of what it returns — both families side by side on the one
endpoint (labels abbreviated for readability):

```text
# Temporal SDK / worker metrics (temporal_*)
temporal_worker_task_slots_available{namespace="payments",worker_type="ActivityWorker"} 1000
temporal_long_request{namespace="payments",operation="PollActivityTaskQueue"} 10
temporal_activity_execution_latency_count{namespace="payments",activity_type="read_corridor_memory"} 2

# Application metrics (corridor_*)
# HELP corridor_memory_lookups Passive corridor-memory lookups
# TYPE corridor_memory_lookups counter
corridor_memory_lookups{corridor="US->IN",result="hit"} 4
# HELP corridor_corrections_applied Corrections applied to payments
# TYPE corridor_corrections_applied counter
corridor_corrections_applied{field="bic",source="memory"} 6
# HELP corridor_correction_confidence Confidence of applied corrections
# TYPE corridor_correction_confidence histogram
# HELP corridor_correction_retries_alerted Corrections whose retries crossed the alert threshold
# TYPE corridor_correction_retries_alerted counter
corridor_correction_retries_alerted{field="bic",source="memory"} 4
```

## Metrics in Temporal Cloud

The `temporal_*` SDK metrics you scrape locally are complemented, in
production, by **Temporal Cloud metrics**: a Prometheus-compatible
OpenMetrics endpoint (`metrics.temporal.io`) that exposes server-side
`temporal_cloud_*` series — workflow and task-queue health, latencies, and
platform limits — for every namespace in your account, authenticated with a
metrics-scoped API key and consumable by Datadog, Grafana Cloud, and the
like.

Temporal also publishes **reference Grafana dashboards** for both the
SDK/worker metrics and the Cloud metrics — a starting point to adapt, not a
production-final board.

- Temporal Cloud metrics: <https://docs.temporal.io/cloud/metrics>
- Reference dashboards: <https://github.com/temporalio/dashboards>

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
UI calls the codec server — already wired up in dev, so decoded payloads
appear with no manual configuration. (The `make feature-reset` above turns
`payload-encryption` off, so re-enable it — `make feature-enable
NAME=payload-encryption` — if you want to see this.)

## Logging discipline

Temporal's [best practices](https://docs.temporal.io/best-practices) call
it out, and the code follows it: logging goes through `workflow.logger` and
`activity.logger`, never `print`. `workflow.logger` is replay-aware (it
does not double-log on replay), which `print` cannot be.

## Checkpoint

- [ ] You can scrape both `temporal_*` and `corridor_*` from `/metrics`.
- [ ] You can name which metric each activity emits and how it is tagged.
- [ ] You can point to Temporal Cloud's metrics endpoint and dashboards.

---

Next: [12 — Testing durable code](12-testing.md).
