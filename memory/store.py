"""Intentionally-naive baseline store for the corridor-memory service.

This is the workshop's *starting point*, kept deliberately simple so the HTTP
service runs end-to-end offline before any durable machinery is introduced:

  * in-memory only — a plain module-level dict,
  * lost on restart — nothing is persisted anywhere,
  * no audit trail — reads and writes leave no history,
  * not shared across replicas — each process keeps its own copy.

A later workshop step swaps this backing store for a durable Temporal
workflow (query for reads, update for writes) behind the exact same HTTP
handlers in ``memory/app.py``. Keeping the naive version isolated in this
module makes that swap a one-file change.
"""

from __future__ import annotations

from shared.models import AnomalyType, CorridorPattern


def _key(
    corridor: str,
    anomaly_type: AnomalyType,
    beneficiary_bank_id: str | None = None,
) -> str:
    """Build the stable dict key for a corridor + anomaly type, optionally
    scoped to a beneficiary bank.

    A single flat string key (``"US->IN|wrong_bic"``) mirrors the key form
    the future durable memory workflow uses, so the two backing stores stay
    interchangeable behind the same lookup/remember contract.

    NOTE: append the beneficiary-bank discriminator only when present, so a
    wrong_bic pattern is beneficiary-specific while corridor-wide anomaly
    types (bank_id None) keep the original corridor|anomaly_type key. Both
    backends must build the key identically to stay interchangeable.
    """
    base = f"{corridor}|{anomaly_type}"
    return f"{base}|{beneficiary_bank_id}" if beneficiary_bank_id else base


def seed() -> dict[str, CorridorPattern]:
    """Return the initial known patterns, keyed exactly as ``_key`` builds them.

    NOTE: Exposed as a reusable function so the naive in-memory store below and
    the durable ``MemoryWorkflow`` (``memory-workflow`` FEATURE) start from the
    same data — the workflow is seeded with ``seed()`` at startup, keeping both
    backing stores identical behind the HTTP contract. A fresh dict is returned
    on each call so callers never share (or mutate) a common seed instance.

    Pre-seeded with one known pattern (identical to the workshop's original
    in-process corridor memory) so the demo corrects the matching anomaly from
    memory alone, without ever calling an LLM.
    """
    return {
        _key("US->IN", AnomalyType.WRONG_BIC, "HDFCINBB"): CorridorPattern(
            corridor="US->IN",
            anomaly_type=AnomalyType.WRONG_BIC,
            beneficiary_bank_id="HDFCINBB",
            field_to_fix="bic",
            proposed_value="HDFCINBBXXX",
            confidence=0.95,
        ),
    }


_PATTERNS: dict[str, CorridorPattern] = seed()


def lookup(
    corridor: str,
    anomaly_type: AnomalyType,
    beneficiary_bank_id: str | None = None,
) -> CorridorPattern | None:
    """Return the stored pattern for a corridor + anomaly type, optionally
    scoped to a beneficiary bank, or None.

    NOTE: This read is intentionally pure — it never mutates ``hit_count`` or
    any other state. That keeps the baseline consistent with the future durable
    implementation, where lookups are served by a Temporal *query*: a query is
    read-only and cannot durably mutate workflow state, so counting hits here
    would create a behaviour the durable version could not reproduce.
    """
    return _PATTERNS.get(_key(corridor, anomaly_type, beneficiary_bank_id))


def remember(pattern: CorridorPattern) -> None:
    """Upsert a learned correction pattern (last-write-wins)."""
    _PATTERNS[
        _key(pattern.corridor, pattern.anomaly_type, pattern.beneficiary_bank_id)
    ] = pattern
