---
name: "Gateway (Caddy) healthcheck reports unhealthy by design"
description: "The gateway container shows unhealthy because its healthcheck probes the Caddy admin API, which is unavailable here; Caddy still serves traffic."
type: reference
---

# Gateway (Caddy) healthcheck reports unhealthy by design

The `gateway` service (Caddy) routinely shows `unhealthy` in
`docker compose ps` even when the whole stack works. Its healthcheck
(`compose.yaml`) probes the Caddy admin API at
`http://localhost:2019/config/`, which is not reachable in this
environment, so the probe fails (`wget: can't connect`). This is
expected — not a regression and not a bug to fix.

Caddy itself serves traffic normally: it routes `/` to the static Web
UI and `/codec` to the codec service, both reachable on the gateway's
port `8080` (remapped to a host port by `compose.override.yaml` in
Casper worktrees). The other services that define a healthcheck
(`temporal`, `payments`, `payments-api`, `memory`) report `healthy`;
`codec` defines no healthcheck, so it shows no health column at all.

**Why:** the admin endpoint quirk makes `gateway` look broken during any
launch verification; treat the gateway's own HTTP responses (Web UI +
`/codec` reachable) as the real liveness signal, not its healthcheck
state.

**How to access:** verify the gateway by curling the Web UI through it
(`http://localhost:<gateway-port>/` → 200), not by reading its
`Health` column. See [[project_gateway_topology]] for the routing
topology and [[project_casper_port_remap]] for the port remapping.
