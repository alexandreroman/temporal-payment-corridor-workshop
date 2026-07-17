"""Tests for the named simulator scenarios and the CLI argument parsing.

Pure and offline: no Temporal, no network. They guard the registry (every
scenario builds a valid anomaly), the offline happy path (the default scenario
still matches the seeded corridor pattern), the ``reaches_agents`` flag, and
the argparse surface (known names resolve, unknown names are rejected).
"""

from __future__ import annotations

import pytest

from memory import store
from payments.workflows import CONFIDENCE_THRESHOLD
from shared.models import PaymentAnomaly
from simulator.main import _build_parser
from simulator.scenarios import DEFAULT_SCENARIO, SCENARIOS, build_anomaly


@pytest.mark.parametrize("scenario", SCENARIOS.values(), ids=list(SCENARIOS))
def test_build_anomaly_produces_a_valid_payment_anomaly(scenario):
    anomaly = build_anomaly(scenario)

    assert isinstance(anomaly, PaymentAnomaly)
    assert anomaly.payment_id.startswith("pmt-")
    assert len(anomaly.payment_id) > len("pmt-")
    assert anomaly.corridor == scenario.corridor
    assert anomaly.anomaly_type == scenario.anomaly_type


def test_build_anomaly_generates_a_fresh_payment_id_each_call():
    scenario = SCENARIOS[DEFAULT_SCENARIO]

    assert build_anomaly(scenario).payment_id != build_anomaly(scenario).payment_id


def test_default_scenario_is_memory_hit_and_matches_the_seeded_pattern():
    # Regression guard: the offline happy path must keep hitting the one
    # pre-seeded corridor pattern *at or above CONFIDENCE_THRESHOLD*, so the
    # default run corrects from memory with no LLM call. Asserting the pattern
    # merely exists is not enough: the property that keeps memory-hit LLM-free
    # is its confidence clearing the threshold (payments/workflows.py). If the
    # seed confidence dropped below it, memory-hit would silently reach the
    # agents, so pin the confidence against the imported threshold too.
    assert DEFAULT_SCENARIO == "memory-hit"

    default = SCENARIOS[DEFAULT_SCENARIO]
    pattern = store.lookup(
        default.corridor, default.anomaly_type, default.beneficiary_bank_id
    )
    assert pattern is not None
    assert pattern.confidence >= CONFIDENCE_THRESHOLD


def test_reaches_agents_is_false_only_for_memory_hit():
    offline = {
        name for name, scenario in SCENARIOS.items() if not scenario.reaches_agents
    }

    assert offline == {"memory-hit"}


def test_parser_resolves_a_known_scenario_name():
    args = _build_parser().parse_args(["--scenario", "memory-miss"])

    assert SCENARIOS[args.scenario].name == "memory-miss"


def test_parser_defaults_to_the_default_scenario():
    args = _build_parser().parse_args([])

    assert args.scenario == DEFAULT_SCENARIO


def test_parser_rejects_an_unknown_scenario_name():
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["--scenario", "does-not-exist"])
