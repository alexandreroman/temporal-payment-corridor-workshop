"""Unit checks on the agents' output contracts (no model calls)."""

from __future__ import annotations

from shared.models import ComplianceVerdict
from payments.agents import AgentCorrection, compliance_agent, instruction_agent


def test_instruction_agent_still_proposes_a_correction():
    assert instruction_agent.output_type is AgentCorrection


def test_compliance_agent_returns_a_verdict_not_a_proposal():
    assert compliance_agent.output_type is ComplianceVerdict
