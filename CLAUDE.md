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
make dev           # Temporal dev server (Docker) + worker with hot reload
make simulator     # simulate an incoming payment anomaly
make check         # lint + tests
```

## Modules

- `models.py` — shared Pydantic models exchanged across the Temporal boundary
- `agents.py` — Pydantic AI agents wrapped as durable `TemporalAgent`s
- `workflows.py` — coordinator, agent child workflows, and corridor memory
- `activities.py` — corridor-memory read/write and applying the correction
- `worker.py` — worker entrypoint: runtime, metrics, Logfire, registration
- `simulator.py` — client that simulates an incoming payment anomaly

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

## Conventions

- **Progressive activation** — the full application ships up front.
  Workshop steps live in commented `# --- STEP: <name> ---` blocks;
  attendees uncomment them following an external guide. Keep this
  structure intact: add new workshop features as tagged STEP blocks
  rather than deleting or rewriting existing code.
- **Determinism** — workflow code must stay deterministic; all I/O lives
  in activities or inside the durable agents.
- **Config via environment** — read configuration from environment
  variables (local `.env`), never hard-code endpoints or keys.
- Line length: 80 columns for text/Markdown, 120 for code.
