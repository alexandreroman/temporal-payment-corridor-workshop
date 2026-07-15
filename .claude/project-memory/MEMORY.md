# Project Memory

> When a new decision **contradicts** an existing
> memory note, do NOT silently override it.
> Instead: surface the conflict, quote the
> existing memory, explain how the new decision
> differs, and ask for explicit confirmation
> before updating. **Do NOT take any action** —
> no tool calls, no file writes — until confirmed.

- [Dev workflow: hot reload and HTML preview](references/feedback_dev_workflow.md) — use `make dev`/`make webui` for hot reload; preview HTML via Casper Browser when available.
- [Docker images run modules from source](references/project_docker_build.md) — images install deps only and run `python worker.py`/`webui.py`; never build the wheel (readme field breaks the build).
