---
name: "Gateway payments-API upstream is mode-specific"
description: "Container mode routes gateway->payments-api:8020 in-network; dev mode routes gateway->host.docker.internal via dev-only compose.dev.yaml, not the auto-merged override"
type: project
---

# Gateway payments-API upstream is mode-specific

The Caddy gateway proxies `/api/payments/v1/*` to
`{$PAYMENTS_API_UPSTREAM:payments-api:8020}` (`gateway/Caddyfile`). That
upstream must differ by run mode, so it is NOT set in the auto-merged
`compose.override.yaml` (which both modes read):

- **Container mode** (`make app-up`): `PAYMENTS_API_UPSTREAM` is unset, so
  Caddy uses its in-network default `payments-api:8020` — the payments API
  container on the Compose network. No host round-trip.
- **Dev mode** (`make dev` / `make infra-up`): the payments API runs on the
  host with hot reload, so the containerised gateway must dial back out to
  `host.docker.internal:${PAYMENTS_API_PORT}`. This value lives in a
  committed, dev-only overlay `compose.dev.yaml` that is deliberately NOT
  named `compose.override.yaml` (so Compose never auto-merges it). The
  Makefile applies it explicitly via
  `COMPOSE_DEV_FILES := -f compose.yaml $(if $(wildcard compose.override.yaml),-f compose.override.yaml,) -f compose.dev.yaml`
  used only by `infra-up`; `app-up`/`app-down`/`app-logs` stay on plain
  `docker compose` (auto-merge only).

`worktree-ports` no longer emits a `gateway.environment` block in the
generated override — it writes port remaps only.

**Why:** a single static override applied to both modes forced container
mode through an unnecessary `host.docker.internal` round-trip. Splitting the
dev-only host route into `compose.dev.yaml` keeps container mode on the clean
in-network route and also fixes a plain-checkout dev bug (with no override
file, dev mode previously fell back to `payments-api:8020`, a container that
is not running in dev mode, so the gateway 502'd).

**How to apply:** keep mode-specific gateway config in `compose.dev.yaml`
(dev) vs the Caddyfile default (container), never in the auto-merged
override. When verifying, confirm `docker compose exec gateway printenv
PAYMENTS_API_UPSTREAM` is empty under `app-up` and
`host.docker.internal:<port>` under `dev`. Both routes verified end-to-end
(simulator through the gateway completes the correction). See
[[Casper worktree port remap]] and
[[Gateway is the single HTTP entry point; codec is always-on infra]].
