"""Tests for the corridor-memory HTTP routes (the in-memory baseline backend).

Exercise the stable ``/api/memory/v1`` contract end-to-end against the FastAPI
app, with no network: an httpx ``AsyncClient`` speaks to the app in-process
through ``ASGITransport`` (same technique as ``codec/test_app.py``, but
async because these handlers are ``async def``).

No ``pytest-asyncio`` dependency is configured (see ``pyproject.toml``), so the
async scenarios are driven with ``asyncio.run`` inside plain synchronous test
functions — the same style as ``shared/test_encryption.py``.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from memory import store
from memory.app import app

# ASGITransport ignores the host, but httpx still needs an absolute base URL to
# build request URLs from the relative paths below.
_BASE_URL = "http://memory.test"


class _StoreBackedHandle:
    """A workflow-handle stand-in that serves the in-memory store."""

    async def query(self, _query, args):
        return store.lookup(*args)

    async def execute_update(self, _update, pattern):
        store.remember(pattern)


class _StoreBackedClient:
    """A Temporal-client stand-in whose handle delegates to ``memory.store``.

    NOTE: keeps these HTTP-contract tests backend-agnostic. In the baseline the
    routes call ``store`` directly and this stub is unused; with the
    ``memory-workflow`` FEATURE enabled the routes go through
    ``app.state.temporal_client`` instead, so wiring this stub lets the exact
    same tests pass in both FEATURE states with no live Temporal server.
    """

    def get_workflow_handle(self, _workflow_id):
        return _StoreBackedHandle()


@pytest.fixture(autouse=True)
def restore_store():
    """Snapshot/restore the store and wire a store-backed client, per test.

    The routes delegate to ``memory.store``, whose patterns live in a single
    module-level dict. Reset it between tests so a ``remember`` call cannot leak
    into a later test. The client stub is set unconditionally; it only matters
    when the ``memory-workflow`` FEATURE routes reads/writes through it.
    """
    app.state.temporal_client = _StoreBackedClient()
    snapshot = dict(store._PATTERNS)
    yield
    store._PATTERNS.clear()
    store._PATTERNS.update(snapshot)


def _client() -> httpx.AsyncClient:
    """Build an httpx client wired straight to the app, no sockets involved."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=_BASE_URL)


def test_healthz_reports_ok():
    async def scenario() -> None:
        async with _client() as client:
            response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    asyncio.run(scenario())


def test_lookup_returns_seeded_pattern_on_hit():
    async def scenario() -> None:
        async with _client() as client:
            response = await client.get(
                "/api/memory/v1/lookup",
                params={
                    "corridor": "US->IN",
                    "anomaly_type": "wrong_bic",
                    "beneficiary_bank_id": "HDFCINBB",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["corridor"] == "US->IN"
        assert body["anomaly_type"] == "wrong_bic"
        assert body["field_to_fix"] == "bic"
        assert body["proposed_value"] == "HDFCINBBXXX"
        assert body["confidence"] == 0.95

    asyncio.run(scenario())


def test_lookup_returns_null_on_miss():
    async def scenario() -> None:
        async with _client() as client:
            response = await client.get(
                "/api/memory/v1/lookup",
                params={"corridor": "US->GB", "anomaly_type": "wrong_bic"},
            )
        # A miss is an ordinary answer: HTTP 200 with a JSON null body, not 404.
        assert response.status_code == 200
        assert response.json() is None

    asyncio.run(scenario())


def test_remember_returns_204_then_lookup_finds_the_pattern():
    pattern = {
        "corridor": "US->GB",
        "anomaly_type": "currency_mismatch",
        "field_to_fix": "currency",
        "proposed_value": "GBP",
        "confidence": 0.8,
    }

    async def scenario() -> None:
        async with _client() as client:
            stored = await client.post("/api/memory/v1/remember", json=pattern)
            assert stored.status_code == 204
            assert stored.content == b""  # 204 carries no body

            found = await client.get(
                "/api/memory/v1/lookup",
                params={"corridor": "US->GB", "anomaly_type": "currency_mismatch"},
            )
        assert found.status_code == 200
        assert found.json()["proposed_value"] == "GBP"

    asyncio.run(scenario())


def test_lookup_with_bank_id_keys_a_distinct_pattern():
    pattern = {
        "corridor": "US->GB",
        "anomaly_type": "wrong_bic",
        "beneficiary_bank_id": "BARCGB22",
        "field_to_fix": "bic",
        "proposed_value": "BARCGB22XXX",
        "confidence": 0.9,
    }

    async def scenario() -> None:
        async with _client() as client:
            stored = await client.post("/api/memory/v1/remember", json=pattern)
            assert stored.status_code == 204

            hit = await client.get(
                "/api/memory/v1/lookup",
                params={
                    "corridor": "US->GB",
                    "anomaly_type": "wrong_bic",
                    "beneficiary_bank_id": "BARCGB22",
                },
            )
            miss = await client.get(
                "/api/memory/v1/lookup",
                params={"corridor": "US->GB", "anomaly_type": "wrong_bic"},
            )
        assert hit.json()["proposed_value"] == "BARCGB22XXX"
        assert miss.json() is None

    asyncio.run(scenario())
