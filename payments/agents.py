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
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.azure import AzureProvider
from pydantic_ai.providers.openai import OpenAIProvider
from temporalio.common import RetryPolicy
from temporalio.workflow import ActivityConfig

# Model is resolved at import time from the environment so attendees can
# switch providers without touching code. Any Pydantic AI model string
# works whose SDK is installed, e.g. 'anthropic:claude-sonnet-5' or
# 'openai:gpt-5-mini' (extras that ship with pydantic-ai[temporal]). Two
# extra cases point the agents at a custom endpoint instead of a provider's
# default:
#   - 'azure:<deployment>' targets an Azure OpenAI deployment; the suffix is
#     the Azure deployment name, wired via AZURE_OPENAI_ENDPOINT /
#     AZURE_OPENAI_API_KEY / OPENAI_API_VERSION.
#   - 'openai:<model>' with OPENAI_BASE_URL set targets any OpenAI-compatible
#     endpoint (a proxy, LiteLLM, vLLM, a local server, ...).
MODEL_STRING = os.getenv("CORRIDOR_MODEL", "anthropic:claude-sonnet-5")

# NOTE: Pydantic AI resolves the provider (and validates its API key) when the
# Agent is constructed. The seeded happy path never calls a model, so we set
# placeholder values when none are present to keep imports working offline. A
# *real* key is only needed once an anomaly misses corridor memory and an
# agent actually calls the LLM — set it then (e.g. `export ANTHROPIC_API_KEY=...`).
_PLACEHOLDER_KEY = "set-a-real-key-to-run-the-agents"
# The resolver handles the string form for every entry, but only anthropic,
# openai, and google-gla have their SDK installed by default; groq/mistral
# additionally need their extra (e.g. `pydantic-ai-slim[groq]`) + `uv sync`.
_PROVIDER_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google-gla": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


def _resolve_model() -> str | OpenAIChatModel:
    """Resolve CORRIDOR_MODEL into a Pydantic AI model.

    Returns a plain model string for a provider's default endpoint, or an
    OpenAIChatModel wired to a custom provider for the Azure OpenAI and
    custom-OpenAI-endpoint cases. Agent accepts either form, so the two call
    sites below stay identical.
    """
    provider, _, name = MODEL_STRING.partition(":")

    # Azure OpenAI: 'azure:<deployment>'. Placeholder endpoint/key keep the
    # import-time construction from raising when nothing is configured yet.
    if provider == "azure":
        os.environ.setdefault(
            "AZURE_OPENAI_ENDPOINT",
            "https://set-a-real-endpoint.openai.azure.com",
        )
        os.environ.setdefault("AZURE_OPENAI_API_KEY", _PLACEHOLDER_KEY)
        return OpenAIChatModel(
            name,
            provider=AzureProvider(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_version=os.getenv("OPENAI_API_VERSION", "2024-10-21"),
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
            ),
        )

    env_var = _PROVIDER_ENV.get(provider)
    if env_var:
        os.environ.setdefault(env_var, _PLACEHOLDER_KEY)

    # Custom OpenAI-compatible endpoint: 'openai:<model>' plus OPENAI_BASE_URL.
    if provider == "openai" and os.getenv("OPENAI_BASE_URL"):
        return OpenAIChatModel(
            name,
            provider=OpenAIProvider(
                base_url=os.environ["OPENAI_BASE_URL"],
                api_key=os.environ["OPENAI_API_KEY"],
            ),
        )

    # Everything else: hand the plain string to Agent unchanged.
    return MODEL_STRING


MODEL = _resolve_model()


class AgentCorrection(BaseModel):
    """Structured output every correction agent must return."""

    field_to_fix: str = Field(description="Payment field to change, e.g. 'bic'.")
    proposed_value: str = Field(description="The corrected value for that field.")
    rationale: str = Field(description="Short justification for the fix.")
    confidence: float = Field(ge=0.0, le=1.0, description="0=guess, 1=certain.")


class ComplianceCheck(BaseModel):
    """Structured output the compliance agent must return.

    Mirrors AgentCorrection: a dedicated LLM-facing model that omits the
    transport-only `source` field. _verify_compliance adds `source` when it
    builds the cross-boundary ComplianceVerdict, so the model is never asked
    to decide a value it has no business choosing.
    """

    compliant: bool = Field(description="True when no violation blocks a fix.")
    violations: list[str] = Field(
        default_factory=list,
        description="Human-readable violations; empty when compliant.",
    )
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
# Validates the situation against compliance rules and returns a verdict; it
# does NOT propose a correction. The coordinator uses the verdict as a gate
# over the instruction agent's fix.
compliance_agent = Agent(
    MODEL,
    name="compliance_agent",
    output_type=ComplianceCheck,
    instructions=(
        "You are a payments compliance officer. Given a payment anomaly on a "
        "corridor, do NOT propose a correction. Validate whether a compliant "
        "correction is possible and return a verdict. Set compliant to false "
        "and list each violation when the settlement currency does not match "
        "the corridor's destination or a sanctioned intermediary is involved; "
        "otherwise compliant is true with no violations. Report an honest "
        "confidence in the verdict."
    ),
)


# NOTE: Tune how the durable agents' model activities retry and time out. Pydantic
# AI runs each model request as a Temporal activity; `model_activity_config`
# sets that activity's timeout and RetryPolicy so slow/rate-limited model
# calls are retried durably instead of failing the workflow.
# Source: https://ai.pydantic.dev/durable_execution/temporal/#activity-configuration
_MODEL_ACTIVITY_CONFIG: ActivityConfig = {
    "start_to_close_timeout": timedelta(seconds=60),
    "retry_policy": RetryPolicy(maximum_attempts=5),
}
instruction_temporal_agent = TemporalAgent(
    instruction_agent, model_activity_config=_MODEL_ACTIVITY_CONFIG
)
compliance_temporal_agent = TemporalAgent(
    compliance_agent, model_activity_config=_MODEL_ACTIVITY_CONFIG
)
