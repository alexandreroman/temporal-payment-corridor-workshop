# 13 — Wrap-up

> [!NOTE]
> **Goal of this step.** Consolidate what you built, return the app to a
> clean baseline, and measure the code against a production-ready
> checklist.

## What you built

Starting from a running baseline, you enabled and studied one durable
execution concept at a time:

| Feature                    | Concept you now own                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------------ |
| *(baseline)*               | Durable agents, coordinator + child workflows, memory-first gate, determinism, idempotency |
| `human-approval-signal`    | Signals & queries; a human decision as durable state                                       |
| `approval-timeout`         | Durable timers; bounded waiting                                                            |
| `non-retryable-validation` | Failure classification; when *not* to retry                                                |
| `retry-alerting`           | Reacting to retries; custom metrics                                                        |
| `settlement-confirmation`  | Long-running activities; heartbeats, cancellation, replay & versioning                     |
| `search-attributes`        | Fleet-wide visibility; filter the fleet via Visibility API                                 |
| `payload-encryption`       | Payload codecs; the codec server                                                           |
| `memory-workflow`          | The Entity Workflow pattern; update/query, continue-as-new                                 |

Along the way you learned to read Event History, scrape one metrics
endpoint for two metric families, and test durable code with replay tests
and a mocked model.

## Reset to a clean baseline

Confirm which features are on, then turn them all off:

```bash
make feature-list                                # see current state
make feature-disable NAME=<feature>              # one at a time
```

If you regenerated the replay fixture during steps 07 or 08, restore the
committed one:

```bash
git checkout payments/testdata/coordinator-history.json
```

Verify a clean tree and a green suite:

```bash
git status
make check
```

Tear the stack down when you are finished:

```bash
# stop `make dev` (Ctrl-C), then:
make infra-down
```

## Measure it against production-ready

Map what you built onto Temporal's [best
practices](https://docs.temporal.io/best-practices). Every point below is
backed by code you read:

- **Correctness** — idempotent activities (step [02](02-durable-agents.md)),
  non-retryable classification (step [05](05-non-retryable-validation.md)),
  deterministic workflow code (step [02](02-durable-agents.md)).
- **Resilience** — timeouts and tuned retry policies everywhere; resilient
  fan-out with `gather(return_exceptions=True)` (step
  [02](02-durable-agents.md)).
- **Data** — payload encryption paired with a codec server (step
  [09](09-payload-encryption.md)).
- **Observability** — `workflow.logger`/`activity.logger`, exported metrics
  (step [11](11-observability.md)), search attributes (step
  [08](08-search-attributes.md)).
- **Testing** — replay tests, mocked model, failure paths (step
  [12](12-testing.md)).

## Deploying: Temporal Cloud vs self-hosting

Throughout the workshop the Temporal Service ran as a dev server in a
container. In production you either **self-host** the Service — running and
scaling its datastore, the front-end / history / matching services, the
Visibility store, upgrades and backups yourself — or you point the same
workers and clients at **Temporal Cloud** and operate none of it. For an app
like this one, Cloud carries real weight:

- **No Service to run.** The coordinator, agent and memory workers, the
  payments API and the simulator connect exactly as they do now; only the
  target address and credentials change. There is no cluster, datastore, or
  Visibility store to size, patch, or keep alive — Temporal runs it, with an
  availability SLA and prioritized support.
- **Managed, isolated namespaces.** The two namespaces this app uses —
  `payments` and `memory` — are each provisioned in a click (many per
  account), with their own retention and access, instead of being configured
  on a cluster you operate.
- **High availability when it matters.** Standard namespaces run
  highly-available; HA namespaces add cross-region failover for the
  strictest continuity needs — no capacity planning on your side.
- **Security built in.** Connections authenticate with mTLS certificates or
  API keys, and each namespace is isolated per account.
- **End-to-end encryption stays yours.** The `PayloadCodec` from step
  [09](09-payload-encryption.md) encrypts payloads *before* they leave your
  process, so even Temporal Cloud only ever stores ciphertext; the codec
  server that decrypts for the UI runs on your side, not theirs.
- **Metrics without a monitoring stack.** The Cloud OpenMetrics endpoint
  and reference dashboards (step [11](11-observability.md)) give you the
  `temporal_cloud_*` fleet view without running Prometheus yourself.

Docs: [Temporal Cloud](https://docs.temporal.io/cloud) ·
[Cloud vs self-hosted](https://docs.temporal.io/evaluate/development-production-features/cloud-vs-self-hosted-features).

## Where to go next

- Combine features. Enable `search-attributes` *and* `human-approval-signal`
  together and watch the `status` attribute drive the server-side
  awaiting-approval filter — the two seams from step
  [03](03-human-approval-signal.md) working as one.
- Turn the insecure codec defaults into real ones (step
  [09](09-payload-encryption.md)) and re-read the decryption-oracle caveat.
- Practice [versioning/patching](https://docs.temporal.io/develop/python/versioning)
  on the `settlement-confirmation` change instead of recapturing history.
- Swap `CORRIDOR_MODEL` for a different provider and re-run the agent
  scenarios.

## Reference index

- [Application README](../README.md) — full reference documentation.
- [Temporal best practices](https://docs.temporal.io/best-practices).
- [Temporal Python docs](https://docs.temporal.io/develop/python).
- [Pydantic AI + Temporal](https://ai.pydantic.dev/durable_execution/temporal/).

Thank you for working through the corridor. Back to the
[guide index](README.md).
