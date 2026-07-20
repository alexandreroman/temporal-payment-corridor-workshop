---
name: "Dev workflow: hot reload and HTML preview"
description: "Run via hot-reload make targets; a browser preview tightens the feedback loop on the slides and the guide"
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

When working on a rendered artifact — the slides or the guide, as well as
the Web UI — previewing it in a browser tightens the feedback loop: you
see the actual result instead of reasoning about it. Use whatever
browser-preview tool the environment offers; none is a prerequisite, and
no specific tool's commands are hard-coded here.

**Why:** hot reload keeps the edit→see loop tight without manual
restarts; rendering the page and looking at it catches layout and content
problems that are invisible in the source, so a change is confirmed rather
than assumed.

**How to apply:** when starting or iterating on the app, use the make
targets; after a change to a rendered page (slides, guide, Web UI), open
it in a browser and confirm it before declaring the change done. Fall back
to sharing the URL when no browser preview is available.

**Operational specifics (bringing the stack up).** Ensure the container
engine is running before `make infra-up` / `make dev` (the engine is
machine-specific — do not assume which one).
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
