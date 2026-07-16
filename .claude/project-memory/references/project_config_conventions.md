---
name: "Config conventions: host/port env pairs and local-only Logfire"
description: "Endpoints are configured as separate HOST + PORT env vars; Logfire runs local-only with no token."
type: project
---

# Config conventions: host/port env pairs and local-only Logfire

## Endpoint env vars are split into HOST + PORT

Network endpoints are configured as two separate environment
variables — a `*_HOST` and a `*_PORT` (cast to `int`) — combined at
the point of use, never as a single `host:port` string.

- Web UI: `WEBUI_HOST` + `WEBUI_PORT`.
- Payments metrics: `PAYMENTS_METRICS_HOST` (default `0.0.0.0`) +
  `PAYMENTS_METRICS_PORT` (default `9464`), combined into the
  `PrometheusConfig` bind address in `payments/main_worker.py`.

Do not use a single `host:port` variable such as
`PAYMENTS_METRICS_BIND_ADDRESS`.
When adding a new endpoint, follow the two-var shape and mirror the
`int(os.getenv(...))` port cast used in `webui/main.py`.

## Logfire is local-only

Both `payments/main_worker.py` and `webui/app.py` call `logfire.configure(...)`
with `send_to_logfire=False`. Spans are produced locally for
instrumentation but nothing is shipped to any backend. There is no
`LOGFIRE_TOKEN` and no token-conditional behavior — do not reintroduce
`send_to_logfire="if-token-present"` or a token env var.
