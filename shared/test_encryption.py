import asyncio

from cryptography.fernet import Fernet
from temporalio.api.common.v1 import Payload

from shared.encryption import EncryptionCodec


async def _round_trip(codec: EncryptionCodec, payload: Payload) -> Payload:
    return (await codec.decode(await codec.encode([payload])))[0]


# No pytest-asyncio dependency is configured in this project (see
# pyproject.toml), so async behaviour is driven with asyncio.run instead of
# `@pytest.mark.asyncio` inside plain, synchronous test functions.


def test_encode_produces_ciphertext_then_decode_restores():
    codec = EncryptionCodec(Fernet.generate_key())
    original = Payload(metadata={"encoding": b"json/plain"}, data=b'{"iban":"DE89"}')

    async def scenario() -> None:
        encoded = (await codec.encode([original]))[0]
        assert encoded.metadata["encoding"] == b"binary/encrypted"
        assert encoded.data != original.data  # ciphertext on the wire

        restored = (await codec.decode([encoded]))[0]
        assert restored.metadata["encoding"] == b"json/plain"
        assert restored.data == original.data

    asyncio.run(scenario())


def test_decode_passes_through_unencrypted_payloads():
    codec = EncryptionCodec(Fernet.generate_key())
    plain = Payload(metadata={"encoding": b"json/plain"}, data=b"{}")

    async def scenario() -> None:
        assert (await codec.decode([plain]))[0].data == plain.data

    asyncio.run(scenario())
