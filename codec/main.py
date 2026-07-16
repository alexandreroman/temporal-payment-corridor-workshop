"""Codec server entrypoint.

Runtime bootstrap for the remote codec server: load configuration and start
the uvicorn server. The application itself is defined in
``codec/app.py``.

Run with:  ``uv run python -m codec.main``  (also what
``make codec-server`` calls). Requires CORRIDOR_ENCRYPTION_KEY to be set —
the app raises on import otherwise.
"""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before reading any getenv.
load_dotenv()

CODEC_SERVER_HOST = os.getenv("CODEC_SERVER_HOST", "0.0.0.0")
CODEC_SERVER_PORT = int(os.getenv("CODEC_SERVER_PORT", "8081"))


def run() -> None:
    """Start the codec server (no hot reload — a single stable process).

    The import is deferred to here so merely importing this module does not
    require CORRIDOR_ENCRYPTION_KEY to be set: ``codec.app`` reads and
    validates the key at import time and raises when it is missing.
    """
    from codec.app import app

    uvicorn.run(app, host=CODEC_SERVER_HOST, port=CODEC_SERVER_PORT)


if __name__ == "__main__":
    run()
