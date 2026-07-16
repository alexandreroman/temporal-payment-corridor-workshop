---
name: "Regenerating the replay fixture needs the memory service on make's port"
description: "make capture-history reaches the memory service on the (possibly Casper-remapped) MEMORY_PORT, not the 8010 default"
type: reference
---

# Regenerating the replay fixture needs the memory service on make's port

`make capture-history` regenerates `payments/testdata/coordinator-history.json`
by running the real coordinator under `WorkflowEnvironment.start_local()`; the
`read_corridor_memory` activity calls the corridor-memory service over HTTP, so
that service must be running and reachable during the capture.

The catch: the `Makefile` derives `MEMORY_PORT` from `compose.override.yaml`
(`MEMORY_PORT := $(shell sed ... )`) and `export`s it, so in a Casper worktree
the capture process looks for the memory service on the **remapped** host port
(e.g. `40304`), not the `8010` default. Starting the service on `8010` while
capturing under `make` yields `httpx.ConnectError: All connection attempts
failed` on `read_corridor_memory`, the agents then fail (no API key), and the
captured fixture is a broken `applied:false` / "All correction agents failed"
history instead of the seeded memory hit.

**Why:** the symptom looks like an httpx/anyio/Temporal-worker networking bug
(standalone httpx works, the service is up), but it is purely a port mismatch
between where the service listens and where `make`'s environment points the
worker.

**How to access:** start the memory service on the port `make` uses — `make
memory` (it exports the remapped `MEMORY_PORT`) or `MEMORY_PORT=<port> uv run
python -m memory.main` — confirm it answers (`curl
http://127.0.0.1:<port>/api/memory/v1/lookup?...`), then run `make
capture-history`. Confirm the fixture outcome is `applied:true` via `memory`
with `proposed_value` `HDFCINBBXXX`, then `uv run pytest
payments/test_replay.py`. See [[casper-worktree-port-remap]] for the remap
mechanism and [[transfer-domain-model-is-intentionally-simplified]] for the
seeded pattern.
