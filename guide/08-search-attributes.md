# 08 — Fleet-wide visibility with Search Attributes

> **Goal of this step.** Make corrections filterable by business
> dimension — corridor, anomaly type, lifecycle status — and, in doing so,
> replace an N+1 listing pattern with a single server-side Visibility
> query.

## At a glance

|                       |                                                                                                                                                             |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Feature**           | `search-attributes`                                                                                                                                         |
| **Files touched**     | [`payments/workflows.py`](../payments/workflows.py), [`payments/api.py`](../payments/api.py), [`payments/test_workflows.py`](../payments/test_workflows.py) |
| **Temporal concepts** | Search Attributes, `upsert_search_attributes`, the Visibility API, list queries                                                                             |
| **Docs**              | [Observability — Search Attributes](https://docs.temporal.io/develop/python/observability#search-attributes)                                                |
| **Builds on**         | steps [02](02-durable-agents.md) and [03](03-human-approval-signal.md)                                                                                      |

## Why this matters

Once you run more than a handful of corrections, "show me everything on
the `US->IN` corridor" or "show me everything awaiting approval" becomes a
real operational need. Without Search Attributes, the listing endpoint has
to fetch every running execution and then **query each one individually**
for its business fields — the classic **N+1** pattern. Search Attributes
push those fields into Temporal's Visibility index, so a single query
filters server-side. This is one of the workshop's headline production
concerns.

## Step 1 — Preview the change

```bash
make feature-diff NAME=search-attributes
```

## Step 2 — Enable it

```bash
make feature-enable NAME=search-attributes
```

> **No manual registration step.** The three custom attributes
> (`corridor`, `anomalyType`, `status`) are pre-registered by the dev
> server on startup (see the `temporal` service command in
> [`compose.yaml`](../compose.yaml)), so you do *not* run
> `temporal operator search-attribute create`.

## Step 3 — Read the newly-live code

**Tagging the execution** — in
[`payments/workflows.py`](../payments/workflows.py), the coordinator now
upserts typed Search Attributes at the top of `run`:

```python
workflow.upsert_search_attributes(
    [
        _CORRIDOR_SA.value_set(anomaly.corridor),
        _ANOMALY_TYPE_SA.value_set(str(anomaly.anomaly_type)),
        _STATUS_SA.value_set("processing"),
    ]
)
```

The typed keys are defined near the top of the file
(`SearchAttributeKey.for_keyword(...)`). The `status` attribute carries the
correction **lifecycle** (`processing` → `awaiting-approval`), driven by
the `_set_status(...)` helper — which was a no-op in the baseline and now
actually upserts. This is the second seam from step
[03](03-human-approval-signal.md) coming to life.

> The call is deterministic and workflow-safe, so it belongs in workflow
> code. `anomaly.anomaly_type` is a `StrEnum`, converted with `str(...)`
> because `value_set` expects a plain string for a keyword key.

**The listing endpoint** — in [`payments/api.py`](../payments/api.py),
`list_anomalies` is a `REPLACE`-style feature with two implementations:

- **Baseline (`FEATURE-OFF`)**: list running executions, then for *each*
  one run a per-workflow query (`describe_anomaly`) to read its
  corridor/anomaly-type and an `awaiting_approval` query — the N+1 cost,
  with the awaiting filter applied in Python.
- **Enabled (`FEATURE-ON`)**: one Visibility query reads the attributes
  straight off each execution, and the awaiting filter is pushed *into*
  the query string:

  ```python
  query = f"WorkflowType = '{_WORKFLOW_TYPE}' AND ExecutionStatus = 'Running'"
  if awaiting_approval:
      query += " AND status = 'awaiting-approval'"
  ```

Read both blocks side by side — the contrast *is* the lesson.

## Step 4 — Run and observe

Start a few corrections (mix `memory-hit` and, if you have a key,
`low-confidence` from step [03](03-human-approval-signal.md) so some are
awaiting):

```bash
make simulator
make simulator SCENARIO=low-confidence   # needs a provider key
```

**In the Web UI**, filter executions with a query on the new attributes:

```text
corridor = 'US->IN'
status = 'awaiting-approval'
```

![Filtering executions by the corridor Search Attribute in the Web UI](images/08-search-attribute-filter.png)

**From the CLI:**

```bash
temporal workflow list --namespace payments \
  --query "corridor = 'US->IN'"
```

**Through the API** — the awaiting filter is now server-side:

```bash
curl -s "http://localhost:8080/api/payments/v1/anomalies?awaiting_approval=true" | jq
```

Compare the Event History / logs between the two implementations: with the
feature off you will see a query per listed workflow; with it on, a single
list call. That is the N+1 removed.

## Step 5 — A note on replay

Like step [07](07-settlement-confirmation.md), adding the
`upsert_search_attributes` call changes the coordinator's Event History, so
it **invalidates the committed replay fixture** — `make test`'s replay
test failing after you enable this is expected, not a regression. To get it
green while the feature stays on, regenerate from a real run: `make
simulator`, grab the printed workflow id, then `make capture-history
WORKFLOW_ID=correction-pmt-XXXX` (the dev stack is already running, so no
separate memory service). See step [12](12-testing.md).

## Step 6 — Checkpoint

- [ ] Executions are filterable by `corridor` / `anomalyType` / `status`
      in the Web UI and the CLI.
- [ ] The API's `awaiting_approval=true` filter runs server-side.
- [ ] You can explain the N+1 pattern the feature removes.

## Revert

```bash
make feature-disable NAME=search-attributes
```

---

Next: [09 — Encrypting payloads](09-payload-encryption.md).
