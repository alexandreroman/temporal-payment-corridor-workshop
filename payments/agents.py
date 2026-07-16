"""Pydantic AI agents, wrapped for durable execution on Temporal.

Each :class:`~pydantic_ai.Agent` is wrapped in a
:class:`~pydantic_ai.durable_exec.temporal.TemporalAgent`. That wrapper
transparently offloads every I/O-bound step (model requests, tool calls,
MCP traffic) to Temporal *activities*, so the agent can be driven from
inside a deterministic workflow and replayed safely.

The wrapped agents are referenced by the agent child workflows in
``payments/workflows.py`` (via ``__pydantic_ai_agents__``) and their
activities are registered automatically by the ``PydanticAIPlugin`` in
``payments/main_worker.py``.
"""

from __future__ import annotations

import os
from datetime import timedelta

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import TemporalAgent
from temporalio.common import RetryPolicy

# Model is resolved at import time from the environment so attendees can
# switch providers without touching code. Any Pydantic AI model string
# works, e.g. 'anthropic:claude-sonnet-5', 'openai:gpt-5.2',
# 'google-gla:gemini-2.5-pro'.
MODEL = os.getenv("CORRIDOR_MODEL", "anthropic:claude-sonnet-5")

# NOTE: Pydantic AI resolves the provider (and validates its API key) when the
# Agent is constructed. The seeded happy path never calls a model, so we set
# a placeholder key when none is present to keep imports working offline. A
# *real* key is only needed once an anomaly misses corridor memory and an
# agent actually calls the LLM — set it then (e.g. `export ANTHROPIC_API_KEY=...`).
_PROVIDER_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google-gla": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}
_env_var = _PROVIDER_ENV.get(MODEL.split(":", 1)[0])
if _env_var:
    os.environ.setdefault(_env_var, "set-a-real-key-to-run-the-agents")


class AgentCorrection(BaseModel):
    """Structured output every correction agent must return."""

    field_to_fix: str = Field(description="Payment field to change, e.g. 'bic'.")
    proposed_value: str = Field(description="The corrected value for that field.")
    rationale: str = Field(description="Short justification for the fix.")
    confidence: float = Field(ge=0.0, le=1.0, description="0=guess, 1=certain.")


# --- InstructionAgent --------------------------------------------------
# Fixes the *payment instruction* itself: a malformed BIC/SWIFT code, a missing
# intermediary/correspondent bank, an inconsistent routing detail, etc.
instruction_agent = Agent(
    MODEL,
    name="instruction_agent",
    output_type=AgentCorrection,
    instructions=(
        "You are a cross-border payments operations expert. You are given a "
        "single payment anomaly on a corridor (an ordered country pair). "
        "Propose the smallest correct fix to the payment instruction so it "
        "can settle: a valid BIC/SWIFT code, the required intermediary bank, or a "
        "consistent settlement detail. Be conservative and report an honest confidence."
    ),
)


# --- ComplianceAgent ---------------------------------------------------
# Checks the correction against compliance rules: currency consistency
# with the corridor, sanctioned intermediaries, and similar constraints.
compliance_agent = Agent(
    MODEL,
    name="compliance_agent",
    output_type=AgentCorrection,
    instructions=(
        "You are a payments compliance officer. Given a payment anomaly on a "
        "corridor, propose a correction that keeps the payment compliant: the "
        "settlement currency must match the corridor's destination, and no "
        "sanctioned intermediary may be introduced. Report an honest "
        "confidence and explain the compliance rationale briefly."
    ),
)


# NOTE: Tune how the durable agents' model activities retry and time out. Pydantic
# AI runs each model request as a Temporal activity; `model_activity_config`
# sets that activity's timeout and RetryPolicy so slow/rate-limited model
# calls are retried durably instead of failing the workflow.
# Source: https://ai.pydantic.dev/durable_execution/temporal/#activity-configuration
_MODEL_ACTIVITY_CONFIG = {
    "start_to_close_timeout": timedelta(seconds=60),
    "retry_policy": RetryPolicy(maximum_attempts=5),
}
instruction_temporal_agent = TemporalAgent(
    instruction_agent, model_activity_config=_MODEL_ACTIVITY_CONFIG
)
compliance_temporal_agent = TemporalAgent(
    compliance_agent, model_activity_config=_MODEL_ACTIVITY_CONFIG
)
