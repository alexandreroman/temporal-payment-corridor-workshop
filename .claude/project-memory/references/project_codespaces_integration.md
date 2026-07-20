---
name: "GitHub Codespaces integration and the codec-endpoint rewrite"
description: "How Codespaces runs the whole guide; the browser-facing codec URL is rewritten via a generated compose.codespaces.yaml overlay"
type: project
---

# GitHub Codespaces integration and the codec-endpoint rewrite

`.devcontainer/` makes the whole learner guide runnable in a GitHub
Codespace with nothing installed locally: `devcontainer.json` uses the
`base:ubuntu` image plus the official `docker-in-docker` feature (for
`make dev`'s `docker compose`), forwards only port **8080** (the gateway
is the single entry point), and carries the VS Code extensions +
FEATURE-region folding settings that live in the gitignored
`.vscode/settings.json` (so they reach a Codespace). `.devcontainer/setup.sh`
(onCreate) installs make/jq/uv/Temporal CLI, runs `uv sync`, `make setup`,
and seeds `.env`. Startup stays **manual** — the learner runs `make dev`
per guide step 01; the devcontainer does not auto-start the stack.

The one browser-facing absolute URL is Temporal's `--ui-codec-endpoint`
(hard-wired to `http://localhost:8080/codec` in `compose.yaml`). In a
browser Codespace `localhost:8080` is the learner's own machine, so
payload decoding (guide 09/11) breaks. `make codespaces-init` (run on
`postStartCommand`) fixes this: when `$CODESPACE_NAME` is set it writes a
gitignored `compose.codespaces.yaml` that overrides only the `temporal`
`command` (`command: !override`, full list mirrored from compose.yaml) so
the codec endpoint becomes
`https://<CODESPACE_NAME>-8080.<GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN>/codec`.
It is a no-op outside a Codespace. `COMPOSE_DEV_FILES` folds the overlay in
only when present — the `make dev` path only; `make app-up` does not get
the rewrite. This is deliberately separate from the Casper
`compose.override.yaml` worktree flow (see [[project_casper_port_remap]]);
Codespaces keeps the default 8080/7233 ports, so the Makefile's `else`
branch applies. App UI and payments API use same-origin relative
`fetch()`, so they need no rewrite (see [[project_gateway_topology]]).
