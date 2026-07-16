---
name: "Run the temporal CLI from the host, never a container"
description: "The temporal CLI is always invoked from the host; localhost URLs only reach the gateway from there"
type: feedback
---

# Run the temporal CLI from the host, never a container

The `temporal` CLI is always run from the host, never from inside a
container (e.g. never via `docker compose exec ... temporal ...`).

**Why:** the documented commands point at `http://localhost:<port>/codec`
(the gateway's published host port), and codec/UI-facing URLs are expressed
from the host's perspective. Inside a container, `localhost` is the
container's own loopback, so it cannot reach the gateway — the call times
out with `context deadline exceeded`. See [[project_gateway_topology]].

**How to apply:** run `temporal workflow show --codec-endpoint
http://localhost:<gateway-port>/codec ...` (no `--codec-auth`; the gateway
injects the bearer token) directly on the host. Point `--address` at the
published Temporal frontend port. When verifying CLI docs or behaviour,
invoke the host CLI — do not shell into the temporal container.
