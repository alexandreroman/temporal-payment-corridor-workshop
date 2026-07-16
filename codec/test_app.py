"""Tests for the remote codec server.

Exercise the HTTP contract the Temporal Web UI relies on: POST a JSON
``Payloads`` envelope to ``/encode`` / ``/decode`` and get an equivalent
envelope back, encrypted or decrypted. Requests and responses are derived
with ``json_format`` (never hand-written base64) so the test proves the real
envelope shape rather than assuming it.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from google.protobuf import json_format
from temporalio.api.common.v1 import Payload, Payloads

# codec.app reads CODEC_ENCRYPTION_KEY and CODEC_SERVER_AUTH_TOKEN at *import*
# time; when unset it falls back to insecure built-in demo defaults (with a
# warning) rather than raising. Set both before the import so the tests run
# against known values instead of the fallbacks. Hence the deliberate
# import-after-statement below (see payments/main.py for the same "import
# deferred until after env is set" pattern).
os.environ["CODEC_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["CODEC_SERVER_AUTH_TOKEN"] = "test-shared-secret"

from codec.app import app  # noqa: E402

# NOTE: The codec server rejects any request without the shared bearer token, so
# set it as a default header and the encode/decode tests below keep exercising
# the happy path. Source:
# https://www.python-httpx.org/advanced/clients/#setting-and-getting-default-headers
client = TestClient(
    app,
    headers={"Authorization": f"Bearer {os.environ['CODEC_SERVER_AUTH_TOKEN']}"},
)

# A representative plaintext payload, shaped like what the SDK puts on the
# wire: a metadata "encoding" hint plus the serialized value in "data".
_PLAINTEXT = b'{"bic":"HDFCINBBXXX"}'


def _envelope(payload: Payload) -> str:
    """Serialize a payload into the JSON envelope the Web UI would POST."""
    return json_format.MessageToJson(Payloads(payloads=[payload]))


def test_encode_wraps_plaintext_as_encrypted_envelope() -> None:
    payload = Payload(metadata={"encoding": b"json/plain"}, data=_PLAINTEXT)

    response = client.post(
        "/encode",
        content=_envelope(payload),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 200

    # The response round-trips through the same
    # {"payloads": [{"metadata": {...}, "data": "..."}]} envelope the Web UI
    # sends, with every bytes field rendered as a base64 string.
    body = response.json()
    assert "payloads" in body
    assert len(body["payloads"]) == 1
    item = body["payloads"][0]
    assert isinstance(item["metadata"]["encoding"], str)
    assert isinstance(item["data"], str)

    # At the protobuf level, the single payload now carries the ciphertext
    # marker EncryptionCodec.encode writes (see shared/encryption.py).
    payloads = json_format.Parse(response.text, Payloads())
    assert len(payloads.payloads) == 1
    assert payloads.payloads[0].metadata["encoding"] == b"binary/encrypted"


def test_decode_restores_original_plaintext() -> None:
    payload = Payload(metadata={"encoding": b"json/plain"}, data=_PLAINTEXT)

    encoded = client.post(
        "/encode",
        content=_envelope(payload),
        headers={"content-type": "application/json"},
    )
    decoded = client.post(
        "/decode",
        content=encoded.text,
        headers={"content-type": "application/json"},
    )
    assert decoded.status_code == 200

    payloads = json_format.Parse(decoded.text, Payloads())
    assert len(payloads.payloads) == 1
    restored = payloads.payloads[0]
    assert restored.metadata["encoding"] == b"json/plain"
    assert restored.data == _PLAINTEXT


def test_request_without_bearer_token_is_rejected() -> None:
    # A client with no default Authorization header stands in for any caller that
    # reaches the codec server without the shared secret.
    unauthenticated = TestClient(app)
    payload = Payload(metadata={"encoding": b"json/plain"}, data=_PLAINTEXT)
    response = unauthenticated.post(
        "/decode",
        content=_envelope(payload),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 401
