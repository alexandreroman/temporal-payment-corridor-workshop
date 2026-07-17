"""Payments HTTP API entrypoint.

Runtime bootstrap for the FastAPI payments API: load configuration and start
uvicorn. The application is defined in payments/api.py and referenced as an
import string so hot reload can run it in a fresh subprocess.

Run with:
  * uv run payments-api         — dev server with hot reload.
  * python -m payments.main_api — production server, no reload (container entry).
"""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before reading any getenv.
load_dotenv()

PAYMENTS_API_HOST = os.getenv("PAYMENTS_API_HOST", "0.0.0.0")
PAYMENTS_API_PORT = int(os.getenv("PAYMENTS_API_PORT", "8020"))


def dev() -> None:
    """Console-script entry point (`uv run payments-api`): run with hot reload.

    The app is passed as an import string because reload runs it in a fresh
    subprocess, which imports payments/api.py directly (never this module).
    """
    uvicorn.run(
        "payments.api:app",
        host=PAYMENTS_API_HOST,
        port=PAYMENTS_API_PORT,
        reload=True,
    )


def run() -> None:
    """Container entry point (`python -m payments.main_api`): no reload.

    The app object is imported and passed directly since there is no reload
    subprocess to spawn.
    """
    from payments.api import app

    uvicorn.run(app, host=PAYMENTS_API_HOST, port=PAYMENTS_API_PORT)


if __name__ == "__main__":
    run()
