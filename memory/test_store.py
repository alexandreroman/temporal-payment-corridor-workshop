"""Tests for the naive in-memory corridor-memory store (the baseline backend).

These exercise the plain module-level dict behind the HTTP service: the seeded
US->IN / WRONG_BIC pattern, lookup hit/miss, remember upserts with
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
    pattern = store.lookup("US->IN", AnomalyType.WRONG_BIC, "HDFCINBB")

    assert pattern is not None
    assert pattern.field_to_fix == "bic"
    assert pattern.proposed_value == "HDFCINBBXXX"
    assert pattern.confidence == 0.95


def test_lookup_returns_none_on_miss():
    assert store.lookup("US->GB", AnomalyType.WRONG_BIC) is None


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
    assert stored is not None
    assert stored.proposed_value == "EUR"


def test_lookup_does_not_mutate_hit_count():
    # A lookup is a pure read: repeated lookups must never bump hit_count, so
    # the baseline matches the future durable query (which cannot mutate state).
    first = store.lookup("US->IN", AnomalyType.WRONG_BIC, "HDFCINBB")
    second = store.lookup("US->IN", AnomalyType.WRONG_BIC, "HDFCINBB")

    assert first is not None and second is not None
    assert first.hit_count == 0
    assert second.hit_count == 0


def test_beneficiary_bank_id_keys_a_distinct_pattern():
    specific = CorridorPattern(
        corridor="US->GB",
        anomaly_type=AnomalyType.WRONG_BIC,
        beneficiary_bank_id="BARCGB22",
        field_to_fix="bic",
        proposed_value="BARCGB22XXX",
        confidence=0.9,
    )
    store.remember(specific)

    # A lookup carrying the same bank id hits; a corridor-wide lookup (no
    # discriminator) is a different key and misses.
    assert store.lookup("US->GB", AnomalyType.WRONG_BIC, "BARCGB22") == specific
    assert store.lookup("US->GB", AnomalyType.WRONG_BIC) is None


def test_seed_returns_a_fresh_isolated_dict_each_call():
    first = store.seed()
    assert set(first) == {"US->IN|wrong_bic|HDFCINBB"}

    # Mutating the returned dict must not affect a later seed() or the live
    # store: seed() hands back a brand-new dict on every call.
    first["US->IN|wrong_bic|HDFCINBB"].proposed_value = "TAMPERED"
    first["injected"] = first["US->IN|wrong_bic|HDFCINBB"]

    second = store.seed()
    assert "injected" not in second
    assert second["US->IN|wrong_bic|HDFCINBB"].proposed_value == "HDFCINBBXXX"

    live = store.lookup("US->IN", AnomalyType.WRONG_BIC, "HDFCINBB")
    assert live is not None
    assert live.proposed_value == "HDFCINBBXXX"
