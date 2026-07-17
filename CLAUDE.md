# Temporal Payment Corridor Workshop

Reference application and hands-on workshop that repairs anomalous
cross-border payments with durable Temporal workflows and Pydantic AI
agents.

See [README.md](README.md) for full documentation.

## Tech stack

- Python (managed with `uv`)
- Temporal Python SDK (`temporalio`)
- Pydantic AI with its Temporal durable-execution integration
- Pydantic Logfire for observability
- Prometheus/OpenMetrics for metrics

## Build & run

```bash
uv sync            # install dependencies
make dev           # Temporal dev server (Docker) + payments worker & API, web UI & memory (hot reload)
make simulator     # simulate an incoming payment anomaly
make check         # lint + tests
```

## Modules

Each functional domain is a Python package; imports are absolute
(`from shared.models import …`). Every executable module has a thin
`main.py` bootstrap (infra init + logs + entry point), with the
component definition isolated in its own file.

- `shared/models.py` — shared Pydantic models exchanged across the
  Temporal boundary
- `payments/` — payment-correction component; two processes share this
  package. The payments worker: `main_worker.py` bootstraps infra
  (runtime, metrics, Logfire, client, hot reload) and `worker.py` builds
  the `Worker` (task queue + workflow/activity registration), while
  `agents.py`, `activities.py`, `workflows.py`, `memory.py` hold the
  durable logic. The payments HTTP API: `main_api.py` bootstraps uvicorn
  and `api.py` defines the `/api/payments/v1` routes as a Temporal client
  (no `Worker`) that starts, lists, and relays approvals for corrections
- `webui/` — static Web UI (`index.html` + `static/`), no process of its
  own; served directly by the gateway (Caddy `file_server`). Dynamic
  behaviour is client-side, via `fetch()` against `/api/payments/v1`
- `memory/` — FastAPI corridor-memory service (its own process and
  Temporal namespace), reached only over HTTP and only in-network
  (`memory:8010`; a host process in dev). `main.py` bootstraps uvicorn;
  `app.py` defines the `/api/memory/v1` routes; `store.py` is the
  in-memory baseline backend; `workflow.py` holds `MemoryWorkflow`, the
  durable backend enabled by the `memory-workflow` FEATURE
- `simulator/main.py` — client that simulates an incoming payment anomaly

## Agents

Use the following agents (from the
[skillbox](https://github.com/alexandreroman/skillbox)
plugin) for all code tasks:

- **code-writer** — for ANY task that writes, modifies, or refactors
  code. This includes one-line fixes, import changes, visibility
  tweaks, and adding assertions. Never use the Edit or Write tools
  directly on source files — always delegate to this agent.
- **code-reviewer** — for read-only code review before merging or when
  investigating issues.

## Memory

- For ANY request to remember, note, or recall project context, use the
  `skillbox:project-memory` skill.
- Project memory lives in `.claude/project-memory/`
  (version-controlled). Never write project memory to the user-level
  `~/.claude/projects/.../memory/` directory.
- Proactively save decisions, workflow preferences, and corrective
  feedback there — don't wait to be asked.
- At the start of a task that may benefit from prior context, read
  `.claude/project-memory/MEMORY.md` and the notes it references.

## Conventions

- **Progressive activation** — the full application ships up front.
  Workshop steps live in commented `# region FEATURE-ON: <name>` blocks;
  attendees uncomment them following an external guide. Keep this
  structure intact: add new workshop features as tagged FEATURE-ON blocks
  rather than deleting or rewriting existing code.
  Toggle features with `make feature-enable NAME=<name>` /
  `feature-disable` (see `tools/features.py`); a feature that replaces
  live code pairs a `FEATURE-ON` block with an inverse `FEATURE-OFF`
  block.
- **Determinism** — workflow code must stay deterministic; all I/O lives
  in activities or inside the durable agents.
- **Config via environment** — read configuration from environment
  variables (local `.env`), never hard-code endpoints or keys.
- Line length: 80 columns for text/Markdown, 88 for code.
