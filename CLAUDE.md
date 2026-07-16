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
make dev           # Temporal dev server (Docker) + worker & web UI (hot reload)
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
- `worker/` — Temporal worker. `main.py` bootstraps infra (runtime,
  metrics, Logfire, client, hot reload); `worker.py` builds the `Worker`
  (task queue + workflow/activity registration); `agents.py`,
  `activities.py`, `workflows.py`, `memory.py` hold the durable logic
- `webui/` — FastAPI web UI. `main.py` bootstraps infra + uvicorn;
  `app.py` defines the app and routes; `templates/` and `static/` hold
  the HTML/CSS
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
- Line length: 80 columns for text/Markdown, 120 for code.
