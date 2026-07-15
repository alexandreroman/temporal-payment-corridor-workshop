---
name: "Docker images run modules from source, never build the project wheel"
description: "Container images install deps only and run python worker.py/webui.py; building the wheel fails on the readme field"
type: project
---

# Docker images run modules from source, never build the project wheel

The `Dockerfile.worker` and `Dockerfile.webui` images install
dependencies only (`uv sync --frozen --no-dev --no-install-project`) and
run the modules directly from `/app` (`CMD ["python", "worker.py"]` /
`CMD ["python", "webui.py"]`). They must NOT build/install the project
package (no `uv sync --no-editable`).

**Why:** `pyproject.toml` declares `readme = "README.md"`, so building
the project wheel makes hatchling read README.md at build time. README.md
is excluded from the image (`.dockerignore` ignores `*.md`, and only
`*.py` — plus `static/`/`templates/` for the web UI — are copied), so a
wheel build fails with `OSError: Readme file does not exist: README.md`.
`docker compose config -q` does not catch this because it never builds.
The sibling project `temporal-bedtime-agent` has no `readme` field, so it
can safely use `--no-editable` — do not copy that step here.

**How to apply:** when editing the Dockerfiles, keep the deps-only sync
and the direct `python <module>.py` entrypoints. If the project ever must
be installed as a package in-image, also copy README.md into the build
context (and stop excluding it) or drop the `readme` field. Verify
container changes with a real `docker build`, not just `compose config`.
