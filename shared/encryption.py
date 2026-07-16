"""Payload encryption for the Temporal boundary.

A ``PayloadCodec`` sits at the very edge of serialization: the SDK calls
``encode`` on the way out (client and worker) and ``decode`` on the way in, so
sensitive fields (IBANs, amounts) travel and rest in Event History as
ciphertext, never plaintext. Encryption uses Fernet (AES-128-CBC + HMAC).
Source: https://docs.temporal.io/production-deployment/data-encryption
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from dataclasses import replace

from cryptography.fernet import Fernet
from temporalio.api.common.v1 import Payload
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.converter import DataConverter, PayloadCodec

# Marker written into the wire payload's metadata so decode() can recognize
# ciphertext it produced (and pass through anything else unchanged).
_ENCODING = b"binary/encrypted"


class EncryptionCodec(PayloadCodec):
    """Encrypt/decrypt every payload with a symmetric Fernet key."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    async def encode(self, payloads: Sequence[Payload]) -> list[Payload]:
        # Fernet releases the GIL in its C extension; to_thread keeps the
        # async event loop responsive under load.
        return [
            Payload(
                metadata={"encoding": _ENCODING},
                data=await asyncio.to_thread(
                    self._fernet.encrypt, p.SerializeToString()
                ),
            )
            for p in payloads
        ]

    async def decode(self, payloads: Sequence[Payload]) -> list[Payload]:
        result: list[Payload] = []
        for p in payloads:
            if p.metadata.get("encoding") != _ENCODING:
                result.append(p)  # not ours (e.g. plaintext) — pass through
                continue
            decrypted = await asyncio.to_thread(self._fernet.decrypt, p.data)
            restored = Payload()
            restored.ParseFromString(decrypted)
            result.append(restored)
        return result


def load_key() -> bytes | None:
    """Read the Fernet key from ``CORRIDOR_ENCRYPTION_KEY`` (None if unset).

    Generate one with ``python -c 'from cryptography.fernet import Fernet;
    print(Fernet.generate_key().decode())'``.
    """
    key = os.getenv("CORRIDOR_ENCRYPTION_KEY")
    return key.encode() if key else None


def build_data_converter(codec: PayloadCodec) -> DataConverter:
    """Pydantic AI's data converter with the encryption codec attached."""
    return replace(pydantic_data_converter, payload_codec=codec)
