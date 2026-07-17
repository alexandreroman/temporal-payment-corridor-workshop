"""Web UI application definition.

A small FastAPI application that serves the payment-corridor homepage: a
live listing of payment corrections plus a human-approval intervention
panel. The page polls the payments API same-origin through the gateway,
refreshing running corrections and relaying operator approvals.

The server startup lives in ``webui/main.py``; this module defines the
``app`` object, imported as ``webui.app:app`` by uvicorn. Logfire is
configured here (not in ``main.py``) because uvicorn's reload runs the app in
a fresh subprocess that imports this module directly, never ``main.py``.
"""

from __future__ import annotations

from pathlib import Path

import logfire
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before configuring Logfire so
# its environment is visible in this (serving) process.
load_dotenv()


def setup_logfire() -> logfire.Logfire:
    """Configure Logfire the same local-only way payments does.

    ``send_to_logfire=False`` keeps Logfire local-only: spans are produced
    locally for instrumentation but nothing is shipped to any backend.
    """
    return logfire.configure(
        service_name="payment-corridor",
        send_to_logfire=False,
    )


# NOTE: Configure Logfire before instrumenting the app, in the process that serves
# requests (the uvicorn reload subprocess imports this module, not main.py).
setup_logfire()

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
