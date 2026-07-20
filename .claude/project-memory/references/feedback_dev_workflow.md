---
name: "Dev workflow: hot reload and HTML preview"
description: "Run via hot-reload make targets; preview HTML pages with Casper Browser when available"
type: feedback
---

# Dev workflow: hot reload and HTML preview

Run the app through the hot-reload make targets rather than invoking
commands by hand: `make dev` runs the whole hot-reload dev stack —
Temporal and the gateway in containers, plus the payments worker, its
HTTP API, and the corridor memory service on the host with hot reload.
The Web UI is static and served by the gateway, so a frontend edit is
seen by simply refreshing the browser — there is no reload process for
it.

To render or preview HTML pages, prefer Casper Browser when available.
Its own skill defines how to drive it — do not hard-code commands here.

**Why:** hot reload keeps the edit→see loop tight without manual
restarts; Casper Browser is the in-workspace way to actually render a
page and confirm a UI change instead of asking the user to eyeball it.

**How to apply:** when starting or iterating on the app, use the make
targets; after a frontend edit, render the page in Casper Browser and
confirm it before declaring the change done. Fall back to sharing the
URL when Casper is not available.

**Operational specifics (bringing the stack up).** The container runtime
here is Podman — the `docker` / `docker compose` CLIs proxy to it, so a
"Cannot connect to Podman" / connection-refused error means the machine is
stopped: run `podman machine start` before `make infra-up` / `make dev`.
`make dev` runs the payments worker, HTTP API, and memory service in the
foreground (via `make -j`), so it blocks; to drive it programmatically,
launch `make dev` itself as one background process. Never start the host
processes with a bare `uv run payments` / `uv run memory` / `uv run
payments-api` — that bypasses the Makefile-exported `TEMPORAL_ADDRESS`
(`localhost:CASPER_PORT+1` in a worktree) and connects to the default
`localhost:7233`, which fails (same trap as the simulator; see
[[Casper worktree port remap]]). After a failed or killed start, leftover
host processes keep their ports bound (payments metrics `+2`, memory `+4`,
payments API `+5`), and a relaunched worker then dies with
`Failed starting Prometheus exporter: Address already in use`; free those
ports (kill the holders) before relaunching, and leave the separate
`make slides` server running. Preview slides only through `make slides`
(no-cache) — never a bare `python -m http.server`, which serves stale
assets (see [[reference_slides_authoring_workflow]]).
