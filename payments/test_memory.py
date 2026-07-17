"""Tests for the corridor-memory HTTP-client activities, offline.

``read_corridor_memory`` / ``write_corridor_memory`` are plain Temporal
activities that make an outbound HTTP call to the corridor-memory service.
These tests run them under ``temporalio.testing.ActivityEnvironment`` and route
their HTTP calls to the in-process memory FastAPI app through ``ASGITransport``
— no sockets, no running service.

The activities build ``httpx.AsyncClient()`` with no arguments, so we
monkeypatch that constructor to inject an ``ASGITransport`` bound to the app.
httpx sends every request through the client's transport regardless of the URL
host, so the activities' absolute ``http://<host>:<port>/...`` URLs resolve to
the app unchanged.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from temporalio.testing import ActivityEnvironment

from memory import app as memory_app
from memory import store
from payments.memory import read_corridor_memory, write_corridor_memory
from shared.models import AnomalyType, CorridorPattern

# The genuine constructor, captured before monkeypatching so the factory below
# can delegate to it without recursing into the patched name.
_real_async_client = httpx.AsyncClient


class _StoreBackedHandle:
    """A workflow-handle stand-in that serves the in-memory store."""

    async def query(self, _query, args):
        return store.lookup(*args)

    async def execute_update(self, _update, pattern):
        store.remember(pattern)


class _StoreBackedClient:
    """A Temporal-client stand-in whose handle delegates to ``memory.store``.

    NOTE: keeps these activity tests backend-agnostic. In the baseline the memory
    app's routes call ``store`` directly and this stub is unused; with the
    ``memory-workflow`` FEATURE enabled the routes go through
    ``app.state.temporal_client``, so wiring this stub lets the same offline
    tests pass in both FEATURE states with no live Temporal server.
    """

    def get_workflow_handle(self, _workflow_id):
        return _StoreBackedHandle()


def _run_activity(fn, *args):
    """Run one activity to completion under a fresh ActivityEnvironment.

    NOTE: the activities are ``async def``, so ``ActivityEnvironment.run``
    returns a coroutine that must be awaited; ``asyncio.run`` drives it, the
    same no-``pytest-asyncio`` style the rest of the suite uses.
    """
    return asyncio.run(ActivityEnvironment().run(fn, *args))


@pytest.fixture(autouse=True)
def restore_store():
    """Snapshot/restore the store and wire a store-backed client, per test.

    The client stub is set unconditionally; it only matters when the
    ``memory-workflow`` FEATURE routes reads/writes through it.
    """
    memory_app.app.state.temporal_client = _StoreBackedClient()
    snapshot = dict(store._PATTERNS)
    yield
    store._PATTERNS.clear()
    store._PATTERNS.update(snapshot)


@pytest.fixture(autouse=True)
def route_httpx_to_app(monkeypatch):
    """Send the activities' httpx calls to the in-process memory app.

    The activities call ``httpx.AsyncClient()`` with no arguments; this factory
    injects an ``ASGITransport`` bound to the FastAPI app so requests never
    touch the network.
    """

    def factory(*args, **kwargs):
        kwargs.setdefault("transport", httpx.ASGITransport(app=memory_app.app))
        return _real_async_client(*args, **kwargs)

    monkeypatch.setattr("payments.memory.httpx.AsyncClient", factory)


def test_read_corridor_memory_returns_seeded_pattern_on_hit():
    pattern = _run_activity(
        read_corridor_memory, "US->IN", AnomalyType.WRONG_BIC, "HDFCINBB"
    )

    assert pattern is not None
    assert pattern.field_to_fix == "bic"
    assert pattern.proposed_value == "HDFCINBBXXX"


def test_read_corridor_memory_returns_none_on_miss():
    pattern = _run_activity(read_corridor_memory, "US->GB", AnomalyType.WRONG_BIC)

    assert pattern is None


def test_write_then_read_round_trips_through_the_service():
    new = CorridorPattern(
        corridor="US->GB",
        anomaly_type=AnomalyType.CURRENCY_MISMATCH,
        field_to_fix="currency",
        proposed_value="GBP",
        confidence=0.8,
    )

    _run_activity(write_corridor_memory, new)
    stored = _run_activity(
        read_corridor_memory, "US->GB", AnomalyType.CURRENCY_MISMATCH
    )

    assert stored == new


def test_read_corridor_memory_passes_the_bank_id_discriminator():
    specific = CorridorPattern(
        corridor="US->GB",
        anomaly_type=AnomalyType.WRONG_BIC,
        beneficiary_bank_id="BARCGB22",
        field_to_fix="bic",
        proposed_value="BARCGB22XXX",
        confidence=0.9,
    )
    _run_activity(write_corridor_memory, specific)

    hit = _run_activity(
        read_corridor_memory, "US->GB", AnomalyType.WRONG_BIC, "BARCGB22"
    )
    miss = _run_activity(read_corridor_memory, "US->GB", AnomalyType.WRONG_BIC)

    assert hit == specific
    assert miss is None
