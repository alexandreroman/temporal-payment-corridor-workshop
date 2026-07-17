---
name: "Gateway is the single HTTP entry point; codec is always-on infra"
description: "Caddy gateway on :8080 serves the static Web UI at / and routes /temporal, /api/payments/v1, /codec; codec is a non-profiled Compose service that warns and falls back to insecure defaults when unset; metrics and memory publish no host port"
type: project
---

# Gateway is the single HTTP entry point; codec is always-on infra

The codec server and the Caddy gateway are both Compose services
(`Dockerfile.codec`, `gateway/Caddyfile`). The gateway is the app's
sole published HTTP entry point, on `:8080`, and routes by path: `/`
→ the static Web UI (Caddy `file_server` serving the mounted
`./webui` directory — there is NO webui process in either dev or
container mode), `/temporal` → the Temporal Web UI
(`temporal:8233`), `/api/payments/v1/*` → the payments API
(`payments-api:8020`), `/codec/*` → the codec server (`codec:8081`)
with `handle_path` stripping the `/codec` prefix. The internal
Temporal UI port stays `temporal:8233` — that number never appears
on the host; `temporal` publishes ONLY `7233`. `codec`, `memory`,
and `payments-api` publish no host port either: they are reached
only in-network. Metrics are NEVER routed by the gateway — the
payments worker exposes them on its own port, off-gateway, and
container mode publishes no host port for them. The gateway injects
`Authorization: Bearer $CODEC_SERVER_AUTH_TOKEN` on forwarded
`/codec` requests, defaulting to `changeme` when the variable is
unset — matching the codec server's own default.

Because the Web UI page, the payments API, and the codec endpoint
share the one `localhost:8080` origin, UI→API and UI→codec calls are
same-origin: no CORS preflight, so neither service needs CORS
configuration for the UI.

The Fernet key env var is `CODEC_ENCRYPTION_KEY` (loaded by
`shared.encryption.load_key`), NOT `CORRIDOR_ENCRYPTION_KEY`.

**Why:** a single origin removes the CORS problem entirely and gives
one published port for every user-facing surface. The Web UI cannot
send a static shared secret (it only forwards a signed-in user's
token, absent on `temporal server start-dev`), so the gateway
supplies it — a local-dev convenience; production forwards the
user's real token and needs no gateway/secret.

**How to apply:**
- `codec` is always-on infra (NO `profiles`, `restart:
  unless-stopped`) and comes up with the stack. It NEVER fails fast:
  when `CODEC_ENCRYPTION_KEY` / `CODEC_SERVER_AUTH_TOKEN` are unset it
  logs a WARNING and falls back to insecure built-in demo defaults
  (token `changeme`, plus a demo Fernet key), so it always starts —
  even in Sessions 1-2 and even with no `.env`. `.env.example` ships
  the same demo values so `cp .env.example .env` is coherent (payments
  encrypts with the key the codec expects). There is NO `make codec`
  target; the codec starts with `make dev` / `infra-up` / `app-up`.
- `gateway` intentionally does NOT `depends_on` codec or payments-api,
  so `/codec` or `/api/payments/v1` 502s while either is stopped
  (harmless in dev — `make dev` runs the payments API on the host).
- The dev server is auto-wired with `--ui-codec-endpoint
  http://localhost:8080/codec` (a browser-facing URL), so no manual
  Web UI configuration is needed.
- `make infra-up` starts `temporal` + `codec` + `gateway`. The Web UI
  is at `http://localhost:8080`, the Temporal Web UI at
  `http://localhost:8080/temporal` (both via the gateway).
- CLI codec access goes through the gateway
  (`--codec-endpoint http://localhost:8080/codec`, no `--codec-auth`).
- `make worktree-ports` remaps only the genuinely published services
  off `CASPER_PORT`: the gateway itself (`+0`, at `:8080`) and
  temporal-grpc (`+1`). The Web UI is static and has no port of its
  own to remap. Metrics, the payments API, and memory are dev-only,
  host-side ports (not published container ports); the Makefile
  derives them from `GATEWAY_PORT` with offsets `+2` (metrics), `+4`
  (memory), `+5` (payments API) — `+3` is unused.

Pairs with [[project_docker_build]] and
[[feedback_codec_server_not_a_feature]].
