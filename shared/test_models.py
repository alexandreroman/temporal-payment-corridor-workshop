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
