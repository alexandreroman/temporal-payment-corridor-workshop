---
name: "CORRIDOR_MODEL resolution and per-provider examples"
description: "How agents resolve the model from env, plus the canonical example set kept identical across three files"
type: project
---

# CORRIDOR_MODEL resolution and per-provider examples

`payments/agents.py` resolves the agents' model at import time from
`CORRIDOR_MODEL` via `_resolve_model() -> str | OpenAIChatModel`. Three
outcomes:

- Plain provider string (default): returned as-is to `Agent(...)`; the
  provider's placeholder key is `setdefault` from `_PROVIDER_ENV`
  (anthropic, openai, google-gla, groq, mistral) so imports work offline.
  Only anthropic, openai, and google-gla have their SDK installed by
  default (the extras shipped by `pydantic-ai[temporal]`). Groq/Mistral
  stay in `_PROVIDER_ENV` and the resolver handles their string form, but
  running them raises ImportError until their extra (e.g.
  `pydantic-ai-slim[groq]`) is added to `pyproject.toml` + `uv sync`. Deps
  are intentionally NOT added, so examples only advertise the three that
  work out of the box.
- `azure:<deployment>`: builds `OpenAIChatModel(deployment,
  provider=AzureProvider(...))` from `AZURE_OPENAI_ENDPOINT`,
  `AZURE_OPENAI_API_KEY`, `OPENAI_API_VERSION` (default `2024-10-21`).
  Placeholder endpoint/key are `setdefault` before construction.
- `openai:<model>` with `OPENAI_BASE_URL` set: builds
  `OpenAIChatModel(model, provider=OpenAIProvider(base_url=..., api_key=...))`
  for any OpenAI-compatible endpoint (proxy, LiteLLM, vLLM, local server).

This is plain always-on code, not a FEATURE-ON block.

## Canonical per-provider examples — keep identical across three files

The example model ids appear in three places that MUST stay in sync:
`README.md` (Configuration table), `.env.example` (Agents / LLM section),
and the `payments/agents.py` model-resolution comment. Any change to one
must update the other two.

- Anthropic: `anthropic:claude-sonnet-5` -> `ANTHROPIC_API_KEY`
- OpenAI: `openai:gpt-5-mini` -> `OPENAI_API_KEY`
- Azure OpenAI: `azure:<deployment>` -> `AZURE_OPENAI_ENDPOINT` +
  `AZURE_OPENAI_API_KEY` (+ optional `OPENAI_API_VERSION`, default `2024-10-21`)
- Custom OpenAI-compatible endpoint: `openai:<model>` + `OPENAI_BASE_URL`
  -> `OPENAI_API_KEY`

The doc examples deliberately advertise only Anthropic and OpenAI (plus
the two custom-endpoint cases): they are the least-friction path. Gemini
(`google-gla`) works out of the box too (its SDK ships with
`pydantic-ai[temporal]`) but is intentionally dropped from the examples to
keep the list minimal. Each file carries a one-line note that other
providers also work, some (e.g. Groq, Mistral) only after adding their
extra + `uv sync`. Do NOT re-add Gemini/Groq/Mistral example rows.
