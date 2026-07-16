---
name: "Workshop audience and scope"
description: "Who the workshop is for and the scope preferences that shape it"
type: project
---

# Workshop audience and scope

This repository is the reference application and hands-on
material for a Temporal workshop. Keep everything timeless and
audience-neutral: no dates, times, timezones, headcounts,
locations, company names, or other engagement-specific details in
any artifact (see the related feedback notes). Describe the
audience only by role, skill level, and industry.

**Delivery format:** three 2-hour hands-on sessions — theory
followed by exercises.

**Audience:** developers who are strong in Python and have
completed **Temporal 101 and 102**. Assume fluency with the core
primitives — workflows, activities, retries, timers, child
workflows, signals, queries, and updates. Session 1 builds
directly on that foundation and goes straight into the app's
coordinator + child-workflow + durable-agent architecture rather
than teaching the basics.

**Why this app fits them:** their real work is exactly this
domain — an agentic cross-border payment error-resolution
solution for banks, with a coordinator, specialized agents,
human-in-the-loop approval, and a passive memory model that
agents consult before calling an LLM. Their stack is Python +
Pydantic/Logfire on a cloud + Kubernetes environment,
microservices. They chose Temporal for a cloud-agnostic,
production-grade, compliance-guardrailed solution without vendor
lock-in.

**Scope preferences (drive module selection):**

- They want production-grade usage knowledge, not just basics.
- They consider deep production-ops topics — deployments and
  **versioning** — too detailed for now; do not build workshop
  modules around those.
- They are explicitly open to **metrics/observability** (light),
  which matters for their use case.
- Banking **compliance guardrails** are a first-class concern
  (fits a payload-encryption module).

**Pedagogy (no code authoring):** attendees never write code.
Each session enables the application's features with the Feature
Toggle CLI (`make feature-enable NAME=<name>`, reversible), studies
the additions/modifications each feature introduces (via
`make feature-diff NAME=<name>`), and runs the system to observe
behavior. Tests ship with the app: attendees run them
(`make check`) and read what they assert. The baseline code is
production-robust by default (idempotent activities, resilient
fan-out, determinism) and abundantly commented with sources —
reading the commented code is the main lesson; features are
additive capabilities enabled via the CLI. See
[[feedback_code_comments]].

**How to apply:** the agreed emphasis is durable AI agents,
payload encryption (PII/compliance), light metrics observability,
search attributes, and tests — delivered as three 2-hour
sessions. Frame every module in the cross-border-payments domain.
Keep prerequisites/setup friction near zero (the audience wants
no time wasted on environment setup).
