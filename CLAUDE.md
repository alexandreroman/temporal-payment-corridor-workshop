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
- `workflows.py` — coordinator and agent child workflows
- `activities.py` — applying the correction
- `memory.py` — passive corridor memory: in-process store, the
  read/write activities, and the long-running `CorridorMemoryWorkflow`
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
  Workshop steps live in commented `# --- STEP: <name> ---` blocks;
  attendees uncomment them following an external guide. Keep this
  structure intact: add new workshop features as tagged STEP blocks
  rather than deleting or rewriting existing code.
- **Determinism** — workflow code must stay deterministic; all I/O lives
  in activities or inside the durable agents.
- **Config via environment** — read configuration from environment
  variables (local `.env`), never hard-code endpoints or keys.
- Line length: 80 columns for text/Markdown, 120 for code.
