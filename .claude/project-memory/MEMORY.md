# Project Memory

> When a new decision **contradicts** an existing
> memory note, do NOT silently override it.
> Instead: surface the conflict, quote the
> existing memory, explain how the new decision
> differs, and ask for explicit confirmation
> before updating. **Do NOT take any action** —
> no tool calls, no file writes — until confirmed.

- [Dev workflow: hot reload and HTML preview](references/feedback_dev_workflow.md) — use `make dev`/`make webui` for hot reload; preview HTML via Casper Browser when available.
- [Casper worktree port remap](references/project_casper_port_remap.md) — make dev/webui honor CASPER_PORT via compose.override.yaml (setup hook seeds it); no auto-heal by decision.
- [Docker images run modules from source](references/project_docker_build.md) — images install deps only and run `python -m worker.main`/`webui.main`; never build the wheel (readme field breaks the build).
- [Module layout: packages per domain with thin main.py](references/project_module_layout.md) — package-per-domain, thin main.py + isolated definition; Logfire config lives in webui/app.py (reload subprocess), not main.py.
- [Config conventions: host/port env pairs and local-only Logfire](references/project_config_conventions.md) — endpoints use split `*_HOST`+`*_PORT` env vars; Logfire runs local-only (`send_to_logfire=False`, no token).
- [Generated text and code must be in English](references/feedback_english_only.md) — all output (code, comments, docs, commits, prose) is written in English, whatever the conversation language.
