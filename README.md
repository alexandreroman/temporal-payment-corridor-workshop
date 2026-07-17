# Temporal Payment Corridor Workshop

[![CI](https://github.com/alexandreroman/temporal-payment-corridor-workshop/actions/workflows/ci.yml/badge.svg)](https://github.com/alexandreroman/temporal-payment-corridor-workshop/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Repairs cross-border payments that arrive with an anomaly — a wrong
BIC/SWIFT code, a missing intermediary bank, a currency mismatch — by
coordinating specialized AI agents as durable Temporal workflows, with
a passive corridor memory and human oversight for low-confidence fixes.
It doubles as a hands-on Temporal + Pydantic AI training that runs
end-to-end on a local dev server.

> [!NOTE]
> The payment/transfer domain model is intentionally simplified to keep
> the workshop focused on durable execution with Temporal, not on
> payments compliance. A real cross-border payment carries far more than
> a single field. Here each anomaly targets exactly one field — a wrong
> BIC, a missing intermediary bank, or a currency mismatch — so the
> correction logic stays easy to follow.

## Features

- **Durable agents** — Pydantic AI agents wrapped as Temporal workflows,
  so every model call survives worker crashes and restarts.
- **Coordinator + child workflows** — a parent workflow fans out to two
  specialized agents, each its own child workflow: the **instruction agent**
  (a payments operations expert that repairs the instruction so it can
  settle — a valid BIC/SWIFT, the required intermediary bank, a consistent
  routing detail) and the **compliance agent** (a compliance officer that
  keeps the fix within the rules — the settlement currency must match the
  corridor destination, no sanctioned intermediary). The coordinator
  applies the instruction fix only when the compliance agent clears it and
  the confidence is high enough; otherwise it holds for human review.
- **Passive corridor memory** — agents check a memory of known
  corridor-specific patterns before spending a model call; the seeded
  happy path never touches an LLM. Memory is keyed on the beneficiary bank for
  `wrong_bic`, so a stored fix applies to that payee's bank, not the whole
  corridor. Treating a stored pattern as compliance-cleared is a workshop
  simplification — a real system separates sanctions screening from corridor
  policy and re-screens on a TTL.
- **Human-in-the-loop** — low-confidence corrections wait for a human
  decision via Signal, demonstrated as progressive steps.
- **One metrics endpoint** — a single Prometheus/OpenMetrics endpoint
  serves both Temporal SDK metrics (`temporal_*`) and application metrics
  (`corridor_*`).
- **HTTP API** — external clients and the simulator submit anomalies and
  observe in-flight corrections through a single HTTP API
  (`/api/payments/v1`) behind the gateway, never by opening a Temporal
  client of their own.
- **Progressive activation** — the full application ships up front;
  workshop steps are enabled by uncommenting tagged `FEATURE-ON` blocks.

## Prerequisites

- **Python 3.13+** and [uv](https://docs.astral.sh/uv/)
- **Docker** (or a compatible engine) with Compose — runs the Temporal
  dev server container
- **LLM provider API key** — only needed once an anomaly misses corridor
  memory and an agent actually calls a model (e.g. `ANTHROPIC_API_KEY`)
- **[Temporal CLI](https://docs.temporal.io/cli)** (`temporal`) — only
  needed for the optional replay-fixture capture (`make capture-history`),
  not for the core `make dev` flow
- **[jq](https://jqlang.github.io/jq/)** — only needed for the optional
  replay-fixture capture, where `make capture-history` uses it to shape the
  captured history JSON

No Kubernetes or cloud account is required.

## Getting Started

```bash
git clone <repository-url>
cd temporal-payment-corridor-workshop
uv sync
cp .env.example .env   # optional: adjust configuration
```

Contributors should enable the local pre-commit hook once. It runs ruff
formatting and lint before each commit, so a slip is caught locally
instead of only by CI:

```bash
make setup       # enable the local ruff pre-commit hook
```

There are two ways to run the app. For development, `make dev` starts the
Temporal dev server plus the payments worker and its HTTP API, the web UI,
and the corridor memory service (all on the host with hot reload) and prints
the reachable URLs in a banner:

```bash
make dev       # Temporal dev server + payments worker & API, web UI & memory (hot reload)
```

For a fully containerized run, `make app-up` brings the whole stack up in
containers (`make app-down` tears it down):

```bash
make app-up    # bring up the full stack in containers
```

Payments and the memory service run in two separate Temporal namespaces
(`payments` and `memory`); the dev server pre-creates both. Payments never
talks to the memory service over Temporal — it calls the memory HTTP API
(`/api/memory/v1`) instead.

Then, in another terminal, fire a payment anomaly:

```bash
make simulator   # simulate an incoming payment anomaly
```

By default the payment-corridor Web UI (the homepage) is at
http://localhost:8233 — the gateway's root and the app's single published
HTTP entry point. The Temporal Web UI is at http://localhost:8233/temporal,
the payments HTTP API at http://localhost:8233/api/payments/v1, and the
payments metrics at http://localhost:9464/metrics; `make dev` also prints
these URLs in its banner. The homepage lists payment-anomaly corrections
and auto-refreshes every few seconds; once `human-approval-signal` is
enabled it also lets you approve or reject corrections held for human
review. The default anomaly matches a pre-seeded corridor-memory pattern,
so it is corrected end-to-end with no API key. Run `make help` to list all
targets.

## Workshop features

The full application ships up front; individual capabilities stay dormant in
tagged `# region FEATURE-ON: <name>` blocks until you enable them. Toggle
them by name — no manual editing:

```bash
make feature-list                           # every feature and its state
make feature-diff    NAME=search-attributes # what enabling it changes
make feature-enable  NAME=search-attributes # turn it on (everywhere it appears)
make feature-disable NAME=search-attributes # revert
```

Enabling uncomments a feature's code; disabling re-comments it. A feature that
replaces existing behavior pairs a `# region FEATURE-ON: <name>` block with an
inverse `# region FEATURE-OFF: <name>` block, so the swap is reversible
both ways.

These blocks use VS Code folding-region markers. On open (with the
recommended `zokugun.explicit-folding` extension installed), VS Code folds
the dormant `# region FEATURE-ON:` regions while the base implementation
(the `# region FEATURE-OFF:` / live code) stays visible. Expand a folded
`FEATURE-ON` region to study it.

### Decrypting payloads in the Temporal Web UI (codec server)

Once `payload-encryption` is enabled (`make feature-enable
NAME=payload-encryption`) payments encrypts every payload on the wire, so
the Temporal Web UI shows raw ciphertext in Event History. A codec server
decrypts payloads on demand — a small HTTP service that reuses the same
encryption key — and the Temporal Web UI calls it to display cleartext.

Both the codec server and the gateway are Compose services that come up with
the stack (`make dev` / `make app-up`). The gateway is the app's single
published HTTP entry point (`http://localhost:8233`): it serves the
payment-corridor Web UI at `/`, the Temporal Web UI at `/temporal`, the
payments API at `/api/payments/v1`, and the codec server at `/codec`, so
calls from the UI to `/codec` are same-origin and need no CORS
configuration.

You don't have to configure anything for the demo. When
`CODEC_ENCRYPTION_KEY` and `CODEC_SERVER_AUTH_TOKEN` are unset, both the
codec and the gateway fall back to matching public, insecure built-in
defaults (logging a warning) — so decoding works out of the box, even
before you create a `.env`. The dev server is already pointed at `/codec`
via its `--ui-codec-endpoint http://localhost:8233/codec` flag, and the
gateway injects the bearer token, so decrypted payloads appear in the
Temporal Web UI with no manual configuration. Set your own
`CODEC_ENCRYPTION_KEY` and `CODEC_SERVER_AUTH_TOKEN` in `.env` only when you
want to actually secure the setup.

The same goes for the CLI: with the feature active, point `temporal` at the
codec through the gateway to read decrypted payloads. No `--codec-auth` is
needed — the gateway injects the token:

```bash
temporal workflow show \
  --workflow-id <workflow-id> \
  --codec-endpoint http://localhost:8233/codec
```

### Registering Search Attributes (search-attributes)

Once `search-attributes` is enabled (`make feature-enable
NAME=search-attributes`) the coordinator tags each workflow execution with a
`corridor`, an `anomalyType`, and a `status` Search Attribute — the last
carrying the correction lifecycle (`processing` → `awaiting-approval`) so the
payments API can filter in-flight corrections server-side. All three custom
attributes are pre-registered by the dev server on startup (`make dev` /
`make app-up`), so there is no manual registration step — filter executions
in the Temporal Web UI or with
`temporal workflow list --query "corridor = '...'"`.

Enabling a feature that changes workflow code — as `search-attributes` does
by adding a Search Attribute upsert inside the coordinator — intentionally
invalidates the committed replay fixture
(`payments/testdata/coordinator-history.json`). The captured history no longer
matches the new code path, so `payments/test_replay.py` failing after you
enable such a feature is expected, not a regression. To get a passing
replay test while the feature stays enabled, regenerate the fixture from a
completed run. `make capture-history` is no longer self-contained: it
captures an existing execution, so it assumes `make dev` is up and a `make
simulator` run has happened — pass that run's workflow id, e.g. `make
capture-history WORKFLOW_ID=correction-pmt-XXXX`.

## Usage

`make simulator` submits an anomaly to the payments API through the gateway,
which starts a `PaymentCorrectionCoordinator` execution, and prints the
accepted identifiers:

```text
scenario: memory-hit
payment : pmt-9f3c1a2b
workflow: correction-pmt-9f3c1a2b
accepted: submitted to http://localhost:8233/api/payments/v1/anomalies
```

Follow the correction on the homepage (http://localhost:8233), or in the
Temporal Web UI at http://localhost:8233/temporal, or fetch its outcome
from `GET /api/payments/v1/anomalies/<payment_id>` once it completes.

By default this sends the offline `memory-hit` scenario. Pick another named
scenario with `SCENARIO=<name>`:

```bash
make simulator SCENARIO=memory-miss
```

Run `make simulator-list` to see them all. Every scenario other than
`memory-hit` misses corridor memory and invokes the agents, so it needs
`ANTHROPIC_API_KEY` (see [Configuration](#configuration)). Always launch the
simulator through `make`: the target exports the ports from
`compose.override.yaml`, so it keeps working when the ports are remapped.

Inspect the merged metrics endpoint:

```bash
curl -s http://localhost:9464/metrics | grep -E '^(temporal_|corridor_)'
```

## Payments HTTP API

The payments component runs as two processes that share one package: the
**payments worker** (`uv run payments`), a Temporal worker hosting the
coordinator, agents, and activities; and the **payments HTTP API** (`uv run
payments-api`), a Temporal *client* — no worker — that starts corrections,
lists in-flight ones over the Visibility API, and relays human approvals.
`make dev` and `make app-up` run both.

The API is the single external entry point for payment requests: clients and
the simulator submit and observe corrections over HTTP through the gateway
under `/api/payments/v1`, never by opening a Temporal client of their own —
the same convention as the corridor-memory service's `/api/memory/v1`. Every
request goes through the gateway; the API's own bind address
(`PAYMENTS_API_HOST`/`PAYMENTS_API_PORT`, default `0.0.0.0:8020`) is internal.

| Method & path                                           | Purpose                                                                                                                            |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/payments/v1/anomalies`                       | Submit a `PaymentAnomaly`; starts a correction. Returns `202` with `{payment_id, workflow_id}`; a duplicate payment returns `409`. |
| `GET /api/payments/v1/anomalies`                        | List in-flight corrections; `?awaiting_approval=true` keeps only those blocked on a human decision.                                |
| `GET /api/payments/v1/anomalies/{payment_id}`           | One correction's state — running, or completed with its outcome; an unknown payment returns `404`.                                 |
| `POST /api/payments/v1/anomalies/{payment_id}/approval` | Relay an `ApprovalDecision` to a waiting correction. Present only when the `human-approval-signal` feature is enabled.             |

The listing endpoint has two implementations toggled by the
`search-attributes` feature: enabled, it filters running executions
server-side in a single Visibility query on the `status` Search Attribute;
disabled (the baseline), it lists running executions and reads each one's
summary with a per-workflow query — the N+1 pattern that search attributes
exist to remove.

Because these routes are served through the gateway, the simulator reaches
them at `http://<GATEWAY_HOST>:<GATEWAY_PORT>/api/payments/v1` (default
`localhost:8233`). Container mode routes `/api/payments/v1/*` to the
`payments-api` Compose service; dev mode routes it to the host-run API via
`host.docker.internal`, wired automatically by the generated Compose override.

## Configuration

All configuration comes from environment variables, loaded from a local
`.env` file when present (see [.env.example](.env.example)). The essentials
are the AI model the agents use and its matching provider key:

| Variable            | Description                             | Default                      |
| ------------------- | --------------------------------------- | ---------------------------- |
| `CORRIDOR_MODEL`    | Pydantic AI model string for the agents | `anthropic:claude-sonnet-5`  |
| `ANTHROPIC_API_KEY` | Provider key matching `CORRIDOR_MODEL`  | (required to run the agents) |

Swap `CORRIDOR_MODEL` and its provider key for any other Pydantic AI provider.
See [.env.example](.env.example) for the remaining, rarely changed settings.

## Architecture

The payment-correction component (`payments/`, namespace `payments`) runs as
two processes that share one package: the payments worker hosts the
coordinator, agents, and activities on one task queue, while the payments HTTP
API (`/api/payments/v1`) is a Temporal client that starts and observes
corrections for external callers. The coordinator
orchestrates two specialized agents — the instruction agent proposes a fix
to the payment instruction so it can settle, while the compliance agent
returns a verdict guarding the fix against currency and sanctions rules — and
applies the fix only when the verdict clears it and confidence ≥ 0.75
(fail-closed otherwise). Each agent consults corridor memory before the LLM;
activities perform all side effects and emit application metrics. After an
LLM-reasoned correction is applied, the coordinator writes the learned
pattern back via `write_corridor_memory` so the next matching anomaly can
skip the model. Corridor
memory is a separate service (`memory/`) that the `read_corridor_memory` and
`write_corridor_memory` activities reach over HTTP (`/api/memory/v1`). With
the `memory-workflow` FEATURE on, that service runs its own embedded worker
and `MemoryWorkflow` on namespace `memory`; otherwise it serves a naive
in-memory store.

The correction of one payment plays out as this sequence — the coordinator
fans out to both agents concurrently, each tries corridor memory before the
LLM, and the coordinator applies the fix or escalates to a human:

```mermaid
sequenceDiagram
    participant Sim as simulator
    participant API as payments API
    participant Coord as PaymentCorrectionCoordinator
    participant Agent as Instruction & Compliance<br/>agent child workflows
    participant Mem as corridor-memory service
    participant LLM as LLM (Pydantic AI)
    participant Human as human reviewer

    Sim->>API: POST /api/payments/v1/anomalies (via gateway)
    API->>Coord: start workflow (PaymentAnomaly)
    API-->>Sim: 202 Accepted (payment_id, workflow_id)
    par for each agent, concurrently
        Coord->>Agent: execute child workflow
        Agent->>Mem: read_corridor_memory (HTTP /api/memory/v1)
        alt confident pattern in memory
            Mem-->>Agent: known correction (source=memory)
        else memory miss
            Agent->>LLM: agent.run(prompt)
            LLM-->>Agent: proposed correction (source=llm)
        end
        Agent-->>Coord: CorrectionProposal / ComplianceVerdict
    end
    Note over Coord: gate: apply only if compliant AND confidence >= 0.75
    alt compliant and confidence >= 0.75
        Coord->>Coord: apply_correction (activity)
        opt LLM-reasoned fix
            Coord->>Mem: write_corridor_memory (learn the pattern)
        end
    else violation, missing verdict, or low confidence
        Coord->>Human: await decision (signal)
        Human-->>Coord: ApprovalDecision
        opt approved
            Coord->>Coord: apply_correction (activity)
        end
    end
    Coord-->>API: CorrectionOutcome
    Note over Sim,API: simulator fetches the outcome later via<br/>GET /api/payments/v1/anomalies/{payment_id}
```

| Component     | Role                                                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `shared/`     | Pydantic models exchanged across the Temporal boundary                                                                   |
| `payments/`   | Payment-correction component (namespace `payments`): a Temporal worker plus the `/api/payments/v1` HTTP API              |
| `memory/`     | Corridor-memory service (namespace `memory`): serves `/api/memory/v1` over an in-memory store or `MemoryWorkflow`        |
| `webui/`      | FastAPI web UI — the temporal.io-styled landing page                                                                     |
| `codec/`      | Codec server that decrypts payloads for the Temporal Web UI (with `payload-encryption`)                                  |
| `gateway/`    | API gateway — the single published HTTP entry point; injects the codec bearer token                                      |
| `simulator/`  | Client that simulates an incoming payment anomaly                                                                        |

## License

This project is licensed under the Apache-2.0 License — see
[LICENSE](LICENSE) for details.
