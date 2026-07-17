---
name: "Casper worktree port remap"
description: "make dev/simulator honor CASPER_PORT via compose.override.yaml; run the simulator through make; no auto-heal by decision"
type: project
---

# Casper worktree port remap

In a Casper worktree `CASPER_PORT` is set, and the Casper `setup` hook
(`make worktree-ports`) remaps only two published ports into
`compose.override.yaml`: the `gateway` (host port = `CASPER_PORT`, offset
+0; the container-side port stays `8080`) and Temporal gRPC
(`CASPER_PORT+1`). The Makefile derives
the remaining host-dev ports from `GATEWAY_PORT` with shell arithmetic —
payments metrics at +2, memory at +4, payments API at +5 (+3 is unused)
— and exports the full set (`TEMPORAL_ADDRESS`, `PAYMENTS_METRICS_HOST`,
`PAYMENTS_METRICS_PORT`, `MEMORY_PORT`, `PAYMENTS_API_PORT`,
`GATEWAY_HOST`, `GATEWAY_PORT`) to the host-side `uv run` processes, so
`make dev` binds the right ports. Those metrics/memory/payments-API
ports are host-only dev ports the Makefile computes, not values written
into the override file. The simulator is in the same boat: run it
through `make simulator` (optionally `SCENARIO=<name>` to pick a named
anomaly), which inherits the exported `TEMPORAL_ADDRESS`. A bare
`uv run simulator` uses the hard-coded `localhost:7233` default and
fails to connect whenever the ports are remapped. This works in a normal
worktree because the Casper `setup` hook writes the override file once at
worktree creation.

Decision: do NOT add auto-heal to regenerate `compose.override.yaml` when
it is missing (e.g. a worktree created via plain `git worktree add`, so the
`setup` hook never ran). Rely on the Casper setup hook; keep the Makefile
minimal.

**Why:** the normal Casper flow already seeds the file, so an auto-heal is a
speculative safety net for a non-Casper edge case. The user prefers minimal
changes over such guards. A GNU Make 3.81 gotcha also makes a naive fix
wrong: `$(wildcard compose.override.yaml)` cannot see a file created
mid-parse, because the top-of-Makefile `$(wildcard .env)` caches the `.`
directory listing.

**How to apply:** treat `compose.override.yaml` as present in a normal
worktree; do not add regeneration logic to `make dev`/`app-up`. If a future
task genuinely needs auto-heal, detect the file with `$(shell test -f …)`,
never `$(wildcard)`. When verifying dev-server behavior, launch the real
process and read its bound port from the uvicorn log — not `make -pn`; and
when testing the "normal" situation, keep `compose.override.yaml` in place.
See [[Dev workflow: hot reload and HTML preview]].
