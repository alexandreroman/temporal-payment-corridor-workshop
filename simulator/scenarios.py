"""Named simulator scenarios: pure data plus a ``PaymentAnomaly`` builder.

Each scenario is a fixed ``(corridor, amount, currency, anomaly_type, details)``
tuple that steers what the simulator sends. ``memory-hit`` (the default)
reproduces today's offline happy path — it matches the pre-seeded corridor
pattern in ``memory/store.py`` and is corrected from memory with no LLM call.
The other scenarios deliberately miss corridor memory so the Pydantic AI
agents are actually exercised.

Honest caveats (they hold no matter which scenario runs):

* **Both** agents always run. ``PaymentCorrectionCoordinator`` fans out to
  both the instruction and compliance child workflows every time; a scenario
  cannot select a single agent. ``instruction`` and ``compliance`` only steer
  which *domain* the anomaly falls in (see ``payments/agents.py``), not which
  agent executes.
* ``low-confidence`` is **best-effort**. Its sparse, ambiguous ``details``
  nudge the model toward a low-confidence proposal, but the outcome depends on
  the model's response — it is not guaranteed. Watching the coordinator
  actually *pause* for a human verdict additionally requires the
  ``human-approval-signal`` feature enabled on payments; with that feature
  off, a sub-threshold proposal yields the "human approval required" refusal
  outcome (``applied=False``), which the simulator prints.

This module is pure and import-safe: no Temporal, no network, no I/O. That
keeps it trivially testable and lets ``--list-scenarios`` work with no
payments or dev server running.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from shared.models import AnomalyType, PaymentAnomaly


@dataclass(frozen=True)
class Scenario:
    """An immutable named recipe for a simulated payment anomaly.

    Holds only static anomaly fields. ``payment_id`` is intentionally absent:
    it is generated fresh per run by :func:`build_anomaly`, so a scenario stays
    pure, reusable data.
    """

    name: str
    description: str
    # Whether this scenario is expected to reach the LLM agents (i.e. it misses
    # corridor memory). Surfaced by ``--list-scenarios``; see the module caveat
    # about both agents always running.
    reaches_agents: bool
    corridor: str
    amount: float
    currency: str
    anomaly_type: AnomalyType
    details: dict[str, str] = field(default_factory=dict)


# Registry of the workshop scenarios, keyed by CLI name. Insertion order is the
# listing order for ``--list-scenarios``.
SCENARIOS: dict[str, Scenario] = {
    "memory-hit": Scenario(
        name="memory-hit",
        description="US->IN wrong BIC — corrected from memory at 0.95, no LLM call.",
        reaches_agents=False,
        corridor="US->IN",
        amount=15000.0,
        currency="USD",
        anomaly_type=AnomalyType.WRONG_BIC,
        # "HDFC" is a malformed BIC: a real ISO 9362 BIC/SWIFT code is 8 or 11 chars.
        # This pair matches the seeded US->IN pattern in memory/store.py.
        details={"beneficiary": "Acme Textiles Pvt Ltd", "bic": "HDFC"},
    ),
    "memory-miss": Scenario(
        name="memory-miss",
        description="US->GB wrong BIC — misses memory, so both agents are invoked.",
        reaches_agents=True,
        corridor="US->GB",
        amount=15000.0,
        currency="USD",
        # Enough context (a named UK bank) for an agent to confidently derive a
        # valid BIC, so the fix comes from the LLM rather than from memory.
        anomaly_type=AnomalyType.WRONG_BIC,
        details={
            "beneficiary": "Globex Trading Ltd",
            "bank": "Barclays",
            "bic": "BARC",
        },
    ),
    "instruction": Scenario(
        name="instruction",
        description="US->GB missing intermediary bank — anomaly in the instruction agent's domain.",
        reaches_agents=True,
        corridor="US->GB",
        amount=15000.0,
        currency="USD",
        anomaly_type=AnomalyType.MISSING_INTERMEDIARY_BANK,
        details={
            "beneficiary": "Globex Trading Ltd",
            "bank": "Barclays",
            "bic": "BARCGB22",
        },
    ),
    "compliance": Scenario(
        name="compliance",
        description="US->GB currency mismatch — anomaly in the compliance agent's domain.",
        reaches_agents=True,
        corridor="US->GB",
        # USD sent into a GB corridor: the settlement currency should be GBP.
        amount=15000.0,
        currency="USD",
        anomaly_type=AnomalyType.CURRENCY_MISMATCH,
        details={"beneficiary": "Globex Trading Ltd", "bank": "Barclays"},
    ),
    "low-confidence": Scenario(
        name="low-confidence",
        description="US->GB wrong BIC with vague details — best-effort push toward the approval branch.",
        reaches_agents=True,
        corridor="US->GB",
        amount=15000.0,
        currency="USD",
        anomaly_type=AnomalyType.WRONG_BIC,
        # Deliberately sparse and ambiguous: no bank name and a BIC fragment too
        # short to disambiguate, so the agent has little to anchor a confident
        # fix on. Best-effort only — see the module-level caveat.
        details={"beneficiary": "private individual", "bic": "GB"},
    ),
}

# The no-argument default: byte-for-byte the current offline happy path.
DEFAULT_SCENARIO = "memory-hit"


def build_anomaly(scenario: Scenario) -> PaymentAnomaly:
    """Turn a scenario into a ``PaymentAnomaly`` with a freshly generated id.

    The ``payment_id`` uses the same ``pmt-<8 hex>`` form the simulator has
    always used, so downstream workflow ids stay familiar.
    """
    return PaymentAnomaly(
        payment_id=f"pmt-{uuid.uuid4().hex[:8]}",
        corridor=scenario.corridor,
        amount=scenario.amount,
        currency=scenario.currency,
        anomaly_type=scenario.anomaly_type,
        details=dict(scenario.details),
    )
