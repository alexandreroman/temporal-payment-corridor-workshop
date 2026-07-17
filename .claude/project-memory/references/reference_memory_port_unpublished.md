---
name: "Memory service publishes no host port"
description: "corridor-memory is reached only in-network (memory:8010); MEMORY_PORT is a derived host-side dev port, not a published container port"
type: reference
---

# Memory service publishes no host port

The `memory` Compose service uses `expose: ["8010"]`, not `ports:`. Nothing
outside the Compose network reaches it: the payments containers call
`memory:8010` on the Compose network, and `capture-history` reaches
Temporal directly over gRPC via the CLI (see
[[reference_capture_history_cli]]), not via the memory service. In
container mode (`make app-up`) the only published host ports are the
gateway (`8080`) and Temporal gRPC (`7233`).

In dev mode (`make dev`) the memory service still runs as a HOST process
(`make memory`), so `MEMORY_PORT` still exists there, but it is no longer
read back from `compose.override.yaml` (which no longer remaps memory at
all). Instead the Makefile derives it from `GATEWAY_PORT + 4`, the same
offset `worktree-ports` used to use when it remapped memory in the
override — grouped alongside `PAYMENTS_METRICS_PORT` (`+2`) and
`PAYMENTS_API_PORT` (`+5`), which are derived the same way for the same
reason (no longer published container ports).

**How to apply:** `worktree-ports` only remaps genuinely published
services in `compose.override.yaml`: gateway (`CASPER_PORT` itself) and
Temporal gRPC (`+1`). Metrics, the payments API, and memory are
host-only dev ports derived arithmetically from `GATEWAY_PORT`; they are
never written to the override.

Pairs with [[project_gateway_topology]] (topology is otherwise stale on
the port numbers there — that predates the gateway moving to `:8080`) and
[[reference_capture_history_cli]].
