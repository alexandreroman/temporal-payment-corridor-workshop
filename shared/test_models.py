"""Tests for the shared Pydantic models' newest contract.

Focused on the beneficiary discriminator added to the corridor-memory key:
``Beneficiary`` defaults, ``PaymentAnomaly`` now requiring a beneficiary, and
``CorridorPattern`` carrying an optional ``beneficiary_bank_id``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.models import AnomalyType, Beneficiary, CorridorPattern, PaymentAnomaly


def test_beneficiary_bank_id_defaults_to_none():
    assert Beneficiary(name="Acme Textiles Pvt Ltd").bank_id is None


def test_payment_anomaly_requires_a_beneficiary():
    with pytest.raises(ValidationError):
        PaymentAnomaly(
            payment_id="pmt-1",
            corridor="US->IN",
            amount=500.0,
            currency="INR",
            anomaly_type=AnomalyType.WRONG_BIC,
        )


def test_payment_anomaly_carries_its_beneficiary():
    anomaly = PaymentAnomaly(
        payment_id="pmt-1",
        corridor="US->IN",
        amount=500.0,
        currency="INR",
        anomaly_type=AnomalyType.WRONG_BIC,
        beneficiary=Beneficiary(name="Acme Textiles Pvt Ltd", bank_id="HDFCINBB"),
    )
    assert anomaly.beneficiary.bank_id == "HDFCINBB"


def test_corridor_pattern_bank_id_defaults_to_none():
    pattern = CorridorPattern(
        corridor="US->IN",
        anomaly_type=AnomalyType.WRONG_BIC,
        field_to_fix="bic",
        proposed_value="HDFCINBBXXX",
        confidence=0.95,
    )
    assert pattern.beneficiary_bank_id is None


def test_payment_anomaly_schema_is_fully_built():
    # Regression guard: PaymentAnomaly.beneficiary references Beneficiary, so
    # Beneficiary MUST be defined before PaymentAnomaly. If it is defined after
    # (a forward reference under `from __future__ import annotations`), Pydantic
    # leaves the schema unbuilt with a MockValSer serializer that passes
    # in-process tests but crashes in the Temporal workflow sandbox when the
    # coordinator serializes the anomaly to its child workflows.
    assert PaymentAnomaly.__pydantic_complete__ is True


def test_payment_anomaly_round_trips_through_the_temporal_pydantic_converter():
    # Exercises the exact serialization path the Temporal worker uses for
    # workflow/activity arguments; a MockValSer serializer fails here.
    from temporalio.contrib.pydantic import pydantic_data_converter

    anomaly = PaymentAnomaly(
        payment_id="pmt-1",
        corridor="US->IN",
        amount=500.0,
        currency="INR",
        anomaly_type=AnomalyType.WRONG_BIC,
        beneficiary=Beneficiary(name="Acme Textiles Pvt Ltd", bank_id="HDFCINBB"),
    )
    payloads = pydantic_data_converter.payload_converter.to_payloads([anomaly])
    back = pydantic_data_converter.payload_converter.from_payloads(
        payloads, [PaymentAnomaly]
    )
    assert back[0] == anomaly
