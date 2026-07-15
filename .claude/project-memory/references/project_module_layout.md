---
name: "Module layout: packages per domain with thin main.py"
description: "Repo is organized as packages per functional domain; each executable module has a thin main.py bootstrap and an isolated definition file"
type: project
---

# Module layout: packages per domain with thin main.py

The repo is organized as one Python package per functional domain —
`shared/` (models), `worker/` (Temporal worker), `webui/` (FastAPI web
UI), `simulator/` (client) — with absolute imports (`from shared.models
import …`). Every executable module has a **thin `main.py` bootstrap**
(infra init + logs + entry point) and the component definition isolated
in its own file: `worker/worker.py` exposes `build_worker(client)`;
`webui/app.py` holds the FastAPI `app`.

Two subtle invariants must be preserved when editing these bootstraps:

- **Logfire is configured in `webui/app.py`, not `webui/main.py`.** With
  `uvicorn.run("webui.app:app", reload=True)`, the app runs in a reload
  subprocess that imports only `webui.app` and never executes
  `main.py`. Any config the served app needs (Logfire, `load_dotenv`)
  must live in `app.py`. The worker does not have this issue because its
  watchfiles subprocess runs `main()`.
- **`worker/main.py` calls `load_dotenv()` before importing
  `worker.worker`**, because `worker/agents.py` reads `CORRIDOR_MODEL`
  from the environment at import time (kept with `# noqa: E402`).

**Why:** clean domain boundaries and a uniform bootstrap/definition
split; the two invariants are non-obvious traps that a naive
"simplification" of a `main.py` would reintroduce, silently breaking
observability or env-dependent agent config.

**How to apply:** add new features inside the owning package; keep
`main.py` files thin; when touching the webui entry point, remember the
reload-subprocess boundary. See also [[feedback_dev_workflow]].
