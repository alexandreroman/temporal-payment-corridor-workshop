"""Web UI entrypoint.

A small FastAPI application that serves the payment-corridor landing page.
This is the foundation only: a static, temporal.io-styled page plus a health
check. Interactive, Temporal-facing actions are added later as progressive
`# --- STEP: <name> ---` blocks.

Run with:  ``uv run webui``  (dev server with hot reload).
"""

from __future__ import annotations

import os
from pathlib import Path

import logfire
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before reading any getenv.
load_dotenv()

WEBUI_HOST = os.getenv("WEBUI_HOST", "0.0.0.0")
WEBUI_PORT = int(os.getenv("WEBUI_PORT", "8000"))

# Resolve asset directories relative to this file so the app runs the same
# regardless of the current working directory.
_BASE_DIR = Path(__file__).parent
_STATIC_DIR = _BASE_DIR / "static"
_TEMPLATES_DIR = _BASE_DIR / "templates"


def setup_logfire() -> logfire.Logfire:
    """Configure Logfire the same guarded way the worker does.

    ``send_to_logfire='if-token-present'`` keeps the workshop offline-friendly:
    with no ``LOGFIRE_TOKEN`` set, spans are still produced locally but nothing
    is shipped to the Logfire backend.
    """
    return logfire.configure(
        service_name="payment-corridor",
        send_to_logfire="if-token-present",
    )


setup_logfire()

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


def dev() -> None:
    """Console-script entry point (`uv run webui`): run with hot reload.

    Uvicorn's ``reload`` watches source files (via watchfiles, already a
    dependency) and restarts the server on change. The app is passed as an
    import string because reload runs it in a fresh subprocess.
    """
    uvicorn.run("webui:app", host=WEBUI_HOST, port=WEBUI_PORT, reload=True)


if __name__ == "__main__":
    dev()
