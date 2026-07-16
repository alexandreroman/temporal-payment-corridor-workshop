---
name: "Gateway is the single HTTP entry point; codec is always-on infra"
description: "Caddy gateway fronts the Temporal Web UI (/) and codec (/codec) on :8233; codec is a non-profiled Compose service that warns and falls back to insecure defaults when unset"
type: project
---

# Gateway is the single HTTP entry point; codec is always-on infra

The codec server and the Caddy gateway are both Compose services
(`Dockerfile.codec`, `gateway/Caddyfile`). The gateway is the app's
sole published HTTP entry point on the familiar Temporal UI port
`:8233` and routes by path: `/` → the Temporal Web UI
(`temporal:8233`), `/codec/*` → the codec server (`codec:8081`) with
`handle_path` stripping the `/codec` prefix. `temporal` publishes
ONLY `7233`; its `8233` stays internal (the gateway reaches
`temporal:8233` on the Compose network). `codec` publishes no host
port. The gateway injects
`Authorization: Bearer $CODEC_SERVER_AUTH_TOKEN` on forwarded
`/codec` requests, defaulting to `changeme` when the variable is
unset — matching the codec server's own default.

Because the Web UI page and the codec endpoint share the one
`localhost:8233` origin, UI→codec calls are same-origin: no CORS
preflight, so the codec needs no CORS config for the UI.

The Fernet key env var is `CODEC_ENCRYPTION_KEY` (loaded by
`shared.encryption.load_key`), NOT `CORRIDOR_ENCRYPTION_KEY`.

**Why:** a single origin removes the CORS problem entirely and gives
one published port on the port operators already expect (8233). The
Web UI cannot send a static shared secret (it only forwards a
signed-in user's token, absent on `temporal server start-dev`), so
the gateway supplies it — a local-dev convenience; production
forwards the user's real token and needs no gateway/secret.

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
- `gateway` intentionally does NOT `depends_on` codec, so `/codec`
  502s while the codec is stopped (harmless — nothing calls it yet).
- The dev server is auto-wired with `--ui-codec-endpoint
  http://localhost:8233/codec` (a browser-facing URL), so no manual
  Web UI configuration is needed.
- `make infra-up` starts `temporal` + `codec` + `gateway`. Temporal
  Web UI is at `http://localhost:8233` (via the gateway).
- CLI codec access goes through the gateway
  (`--codec-endpoint http://localhost:8233/codec`, no `--codec-auth`).
- `make worktree-ports` gives the gateway `CASPER_PORT` itself
  (primary entry point, mapped to its 8233); temporal-grpc `+1`,
  payments-metrics `+2`, webui `+3`; temporal publishes only 7233.

Pairs with [[project_docker_build]] and
[[feedback_codec_server_not_a_feature]].
