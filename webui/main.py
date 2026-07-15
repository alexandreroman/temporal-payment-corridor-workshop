"""Web UI entrypoint.

Runtime bootstrap for the FastAPI web UI: load configuration and start the
uvicorn server. The application itself is defined in ``webui/app.py`` and
referenced as an import string so hot reload can run it in a fresh subprocess.

Logfire is configured in ``webui/app.py`` (not here) because uvicorn's reload
imports the app module directly in that subprocess, never this bootstrap.

Run with:
  * ``uv run webui``        — dev server with hot reload.
  * ``python -m webui.main`` — production server, no reload (container entry).
"""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before reading any getenv.
load_dotenv()

WEBUI_HOST = os.getenv("WEBUI_HOST", "0.0.0.0")
WEBUI_PORT = int(os.getenv("WEBUI_PORT", "8000"))


def dev() -> None:
    """Console-script entry point (`uv run webui`): run with hot reload.

    Uvicorn's ``reload`` watches source files (via watchfiles, already a
    dependency) and restarts the server on change. The app is passed as an
    import string because reload runs it in a fresh subprocess.
    """
    uvicorn.run("webui.app:app", host=WEBUI_HOST, port=WEBUI_PORT, reload=True)


def run() -> None:
    """Container entry point (`python -m webui.main`): run without reload.

    Reload is intentionally off so the container runs a single stable process.
    The app object is passed directly (not as an import string) since there is
    no reload subprocess to spawn. The import is deferred to here so the common
    ``dev()`` / ``uv run webui`` path never imports the app module in the
    supervisor process; importing ``webui.app`` also configures Logfire
    in-process, which is correct in production where there is no subprocess.
    """
    from webui.app import app

    uvicorn.run(app, host=WEBUI_HOST, port=WEBUI_PORT)


if __name__ == "__main__":
    run()
