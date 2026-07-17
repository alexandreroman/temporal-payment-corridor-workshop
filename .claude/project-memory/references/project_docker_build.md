---
name: "Docker images run modules from source, never build the project wheel"
description: "Container images install deps only and run python -m payments.main_worker/memory.main/codec.main; building the wheel fails on the readme field"
type: project
---

# Docker images run modules from source, never build the project wheel

The `Dockerfile.payments`, `Dockerfile.memory`, and `Dockerfile.codec`
images install dependencies only
(`uv sync --frozen --no-dev --no-install-project`) and run their
package directly from `/app` with `python -m <package>.main...`:
`payments.main_worker`, `memory.main`, and `codec.main`. Each image
copies only the packages it needs. They must NOT build/install the
project package (no `uv sync --no-editable`).

**Why:** `pyproject.toml` declares `readme = "README.md"`, so building
the project wheel makes hatchling read README.md at build time. README.md
is excluded from the image (`.dockerignore` ignores `*.md`, and only the
needed package directories are copied), so a wheel build fails with
`OSError: Readme file does not exist: README.md`. `docker compose config
-q` does not catch this because it never builds. The sibling project
`temporal-bedtime-agent` has no `readme` field, so it can safely use
`--no-editable` — do not copy that step here.

**How to apply:** when editing the Dockerfiles, keep the deps-only sync
and the direct `python -m <package>.main` entrypoints. If the project ever must
be installed as a package in-image, also copy README.md into the build
context (and stop excluding it) or drop the `readme` field. Verify
container changes with a real `docker build`, not just `compose config`.
