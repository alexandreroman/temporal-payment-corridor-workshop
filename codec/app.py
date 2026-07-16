"""Remote codec server for the Temporal Web UI.

The Web UI only ever sees the encrypted payloads stored in Event History,
so raw ciphertext is all it can display. A *remote codec server* fixes that:
the Web UI POSTs the encrypted payloads to this HTTP service, which decrypts
them with the same key the worker uses and returns the plaintext for display
(and encrypts on the way back, for the "send" flows).

This is a FastAPI port of the official aiohttp sample — the wire protocol is
identical, only the web framework differs (FastAPI is already a project
dependency; aiohttp is not).
Source: https://github.com/temporalio/samples-python/blob/main/encryption/codec_server.py

Wire protocol. Both routes speak the same JSON envelope the SDK uses for
``temporalio.api.common.v1.Payloads``::

    {"payloads": [{"metadata": {"<key>": "<base64>"}, "data": "<base64>"}]}

Every ``bytes`` field (metadata values and ``data``) is base64-encoded with
the standard alphabet. Rather than hand-roll that base64 mapping, we let
``google.protobuf.json_format`` do it: ``Parse`` decodes the request into a
``Payloads`` message and ``MessageToJson`` re-encodes the result, so the
base64/JSON handling is exactly what the Web UI expects and the code stays
short and correct.
"""

from __future__ import annotations

import hmac
import logging
import os
from collections.abc import Awaitable, Callable, Sequence

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from google.protobuf import json_format
from temporalio.api.common.v1 import Payload, Payloads

from shared.encryption import EncryptionCodec, load_key

logger = logging.getLogger(__name__)

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before reading any getenv.
load_dotenv()

# Insecure, publicly-known dev defaults used only when the real values are
# unset. They MUST match the fallbacks baked into gateway/Caddyfile (token) and
# the values shipped in .env.example (both), so `cp .env.example .env` — or even
# an empty environment — yields a coherent setup where the worker encrypts with
# the key the codec expects and the gateway injects the token the codec expects.
_DEFAULT_ENCRYPTION_KEY = "M80yQxCwjIWwuApHeRjQQoRARc0PhUh6FAEfukmEhlk="
_DEFAULT_AUTH_TOKEN = "changeme"

# NOTE: The codec never fails fast on missing config. Instead of raising (which
# would stop the service from starting before encryption is configured), it
# degrades to a built-in insecure default and logs a loud WARNING. Trade-off:
# the service is always usable out of the box, at the cost of running with a
# public key/token until real values are set — the warning makes that
# unmissable.
_key = load_key()
if _key is None:
    logger.warning(
        "CODEC_ENCRYPTION_KEY is not set; falling back to an insecure "
        "built-in dev default. Set CODEC_ENCRYPTION_KEY to a real Fernet key "
        "for any non-demo use. Generate one with: "
        "python -c 'from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())'"
    )
    # load_key() returns the key as bytes, so encode the string default to match.
    _key = _DEFAULT_ENCRYPTION_KEY.encode()

# One codec instance shared by every request — it is stateless and thread-safe.
_codec = EncryptionCodec(_key)

# NOTE: The codec server turns "encrypted in Event History" back into plaintext for
# anyone who can reach it, over plain HTTP. Gate every request behind a shared
# bearer token so only the Web UI (configured to forward it) can decode. A shared
# secret is the simplest illustration; production would validate a real access
# token / JWT instead. Source:
# https://docs.temporal.io/production-deployment/data-encryption
# As with the key above, an unset token degrades to an insecure built-in
# default (with a warning) rather than failing fast, so the server always
# starts and the gateway's matching default token authenticates out of the box.
_AUTH_TOKEN = os.getenv("CODEC_SERVER_AUTH_TOKEN")
if not _AUTH_TOKEN:
    logger.warning(
        "CODEC_SERVER_AUTH_TOKEN is not set; falling back to an insecure "
        "built-in dev default. Set CODEC_SERVER_AUTH_TOKEN to a real secret "
        "for any non-demo use. Generate one with: "
        "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )
    _AUTH_TOKEN = _DEFAULT_AUTH_TOKEN


def require_bearer_token(request: Request) -> None:
    """FastAPI dependency: reject any request missing the shared bearer token.

    NOTE: Compared in constant time with hmac.compare_digest so the token cannot
    be recovered byte-by-byte from response-timing differences.
    Source: https://docs.python.org/3/library/hmac.html#hmac.compare_digest
    """
    expected = f"Bearer {_AUTH_TOKEN}"
    if not hmac.compare_digest(request.headers.get("authorization", ""), expected):
        raise HTTPException(
            status_code=401,
            detail="missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# NOTE: dependencies=[...] runs on every route, so both codec endpoints are
# gated. Source:
# https://fastapi.tiangolo.com/tutorial/dependencies/global-dependencies/
app = FastAPI(
    title="Payment Corridor Codec Server",
    dependencies=[Depends(require_bearer_token)],
)

# A codec method: takes payloads, returns the transformed payloads.
_CodecMethod = Callable[[Sequence[Payload]], Awaitable[list[Payload]]]


async def _apply_codec(body: bytes, method: _CodecMethod) -> Response:
    """Parse the JSON envelope, run one codec method, serialize the result.

    Shared by ``/encode`` and ``/decode``; only ``method`` differs.
    """
    payloads = json_format.Parse(body, Payloads())
    processed = await method(payloads.payloads)
    result = Payloads(payloads=processed)
    return Response(
        content=json_format.MessageToJson(result),
        media_type="application/json",
    )


@app.post("/encode")
async def encode(request: Request) -> Response:
    """Encrypt every payload in the request envelope."""
    return await _apply_codec(await request.body(), _codec.encode)


@app.post("/decode")
async def decode(request: Request) -> Response:
    """Decrypt every payload in the request envelope."""
    return await _apply_codec(await request.body(), _codec.decode)
