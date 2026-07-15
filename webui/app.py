"""Web UI application definition.

A small FastAPI application that serves the payment-corridor landing page.
This is the foundation only: a static, temporal.io-styled page plus a health
check. Interactive, Temporal-facing actions are added later as progressive
`# --- STEP: <name> ---` blocks.

The runtime bootstrap (env, Logfire, server startup) lives in
``webui/main.py``; this module only defines the ``app`` object, imported as
``webui.app:app`` by uvicorn.
"""

from __future__ import annotations

from pathlib import Path

import logfire
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Resolve asset directories relative to this file so the app runs the same
# regardless of the current working directory.
_BASE_DIR = Path(__file__).parent
_STATIC_DIR = _BASE_DIR / "static"
_TEMPLATES_DIR = _BASE_DIR / "templates"

app = FastAPI(title="Payment Corridor")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# Trace incoming requests through Logfire (a no-op export when offline).
logfire.instrument_fastapi(app)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve the landing page."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
