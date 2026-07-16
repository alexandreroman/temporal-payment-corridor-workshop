"""Tests for the naive in-memory corridor-memory store (the baseline backend).

These exercise the plain module-level dict behind the HTTP service: the seeded
US->IN / WRONG_IBAN pattern, lookup hit/miss, remember upserts with
last-write-wins, and the read being non-mutating.

The store keeps its patterns in a module-level dict, so an autouse fixture
snapshots and restores that dict around every test to keep them
order-independent (a ``remember`` in one test must not leak into the next).
"""

from __future__ import annotations

import pytest

from memory import store
from shared.models import AnomalyType, CorridorPattern


@pytest.fixture(autouse=True)
def restore_store():
    """Snapshot the module-level store before each test and restore it after.

    NOTE: ``store`` holds patterns in a single module-level dict, shared across
    every test in the process. Without this reset a test that calls ``remember``
    would leak state into later tests and make results order-dependent.
    """
    snapshot = dict(store._PATTERNS)
    yield
    store._PATTERNS.clear()
    store._PATTERNS.update(snapshot)


def test_lookup_returns_seeded_pattern_on_hit():
    pattern = store.lookup("US->IN", AnomalyType.WRONG_IBAN)

    assert pattern is not None
    assert pattern.field_to_fix == "iban"
    assert pattern.proposed_value == "DE89370400440532013000"
    assert pattern.confidence == 0.95


def test_lookup_returns_none_on_miss():
    assert store.lookup("US->GB", AnomalyType.WRONG_IBAN) is None


def test_remember_then_lookup_returns_the_new_pattern():
    pattern = CorridorPattern(
        corridor="US->GB",
        anomaly_type=AnomalyType.CURRENCY_MISMATCH,
        field_to_fix="currency",
        proposed_value="GBP",
        confidence=0.8,
    )

    store.remember(pattern)

    assert store.lookup("US->GB", AnomalyType.CURRENCY_MISMATCH) == pattern


def test_remember_is_last_write_wins():
    key = ("US->GB", AnomalyType.CURRENCY_MISMATCH)
    first = CorridorPattern(
        corridor=key[0],
        anomaly_type=key[1],
        field_to_fix="currency",
        proposed_value="GBP",
        confidence=0.5,
    )
    second = first.model_copy(update={"proposed_value": "EUR", "confidence": 0.9})

    store.remember(first)
    store.remember(second)

    stored = store.lookup(*key)
    assert stored == second
    assert stored.proposed_value == "EUR"


def test_lookup_does_not_mutate_hit_count():
    # A lookup is a pure read: repeated lookups must never bump hit_count, so
    # the baseline matches the future durable query (which cannot mutate state).
    first = store.lookup("US->IN", AnomalyType.WRONG_IBAN)
    second = store.lookup("US->IN", AnomalyType.WRONG_IBAN)

    assert first is not None and second is not None
    assert first.hit_count == 0
    assert second.hit_count == 0


def test_seed_returns_a_fresh_isolated_dict_each_call():
    first = store.seed()
    assert set(first) == {"US->IN|wrong_iban"}

    # Mutating the returned dict must not affect a later seed() or the live
    # store: seed() hands back a brand-new dict on every call.
    first["US->IN|wrong_iban"].proposed_value = "TAMPERED"
    first["injected"] = first["US->IN|wrong_iban"]

    second = store.seed()
    assert "injected" not in second
    assert second["US->IN|wrong_iban"].proposed_value == "DE89370400440532013000"

    live = store.lookup("US->IN", AnomalyType.WRONG_IBAN)
    assert live is not None
    assert live.proposed_value == "DE89370400440532013000"
