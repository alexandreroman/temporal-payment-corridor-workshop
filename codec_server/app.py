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

import os
from collections.abc import Awaitable, Callable, Sequence

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from google.protobuf import json_format
from temporalio.api.common.v1 import Payload, Payloads

from shared.encryption import EncryptionCodec, load_key

# All configuration comes from environment variables, loaded from a local
# .env file when present (see .env.example). Load before reading any getenv.
load_dotenv()

# Fail fast at import time: a codec server with no key cannot do its one job
# (decrypting payloads for display). Raising here surfaces the misconfiguration
# on startup instead of on the first Web UI request.
_key = load_key()
if _key is None:
    raise RuntimeError(
        "CORRIDOR_ENCRYPTION_KEY is not set; the codec server cannot "
        "decrypt payloads without it. Generate a key with: "
        "python -c 'from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())'"
    )

# One codec instance shared by every request — it is stateless and thread-safe.
_codec = EncryptionCodec(_key)

# The Web UI's codec calls originate from the browser, so the server must send
# permissive CORS headers or the browser blocks the response. Restrict it to
# the Web UI's own origin and to the method/headers the sample uses. This is
# deliberately narrow, but note it is browser-enforced and not a security
# boundary by itself (a non-browser client ignores CORS entirely). Mirrors the
# sample's cors_options handler:
# https://github.com/temporalio/samples-python/blob/main/encryption/codec_server.py
_UI_ORIGIN = os.getenv("TEMPORAL_UI_ORIGIN", "http://localhost:8233")

app = FastAPI(title="Payment Corridor Codec Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_UI_ORIGIN],
    allow_methods=["POST"],
    allow_headers=["content-type", "x-namespace"],
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
