"""Unit checks on the agents' output contracts (no model calls)."""

from __future__ import annotations

from payments.agents import (
    AgentCorrection,
    ComplianceCheck,
    compliance_agent,
    instruction_agent,
)


def test_instruction_agent_still_proposes_a_correction():
    assert instruction_agent.output_type is AgentCorrection


def test_compliance_agent_returns_a_verdict_not_a_proposal():
    assert compliance_agent.output_type is ComplianceCheck
    # A verdict carries compliance fields but never the proposal's field_to_fix.
    assert "compliant" in ComplianceCheck.model_fields
    assert "field_to_fix" not in ComplianceCheck.model_fields
