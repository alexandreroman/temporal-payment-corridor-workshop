"""Codec server entrypoint.

Runtime bootstrap for the remote codec server: load configuration and start
the uvicorn server. The application itself is defined in
``codec/app.py``.

The codec runs as the ``codec`` Compose service (image built from
Dockerfile.codec); the container entrypoint is ``python -m codec.main``.
The app never raises on missing config: when CODEC_ENCRYPTION_KEY or
CODEC_SERVER_AUTH_TOKEN is unset it falls back to an insecure built-in demo
value and logs a warning, so the server always starts.
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
    pull in ``codec.app`` and its dependencies before the server starts.
    ``codec.app`` reads its configuration at import time but never raises:
    missing values degrade to insecure built-in defaults with a warning.
    """
    from codec.app import app

    uvicorn.run(app, host=CODEC_SERVER_HOST, port=CODEC_SERVER_PORT)


if __name__ == "__main__":
    run()
