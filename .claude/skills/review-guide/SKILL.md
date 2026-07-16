---
name: review-guide
description: Semantic audit of the learner guide (guide/) against the codebase — catches prose drift a test can't. User-invoked only, via /review-guide.
disable-model-invocation: true
argument-hint: "[optional: a guide file, feature name, or topic to scope the audit]"
---

Run a **semantic accuracy audit** of the learner guide in `guide/` against
the current codebase.

## Why this exists

Mechanical drift is already caught automatically and is **out of scope** here:

- `tools/test_guide.py` (part of `make check`) verifies that every
  `NAME=<feature>`, `make <target>`, `SCENARIO=<x>`, `corridor_*` metric,
  internal link, and screenshot manifest entry in the guide still resolves.
- `.github/workflows/links.yml` checks external links.

This skill covers what those cannot: **does the prose still describe what
the code actually does?** Stale explanations, conceptual claims that no
longer hold, a `NOTE:` the guide summarizes incorrectly, steps whose
observed behavior has changed, ordering/prerequisite contradictions between
steps.

## What to do

Scope: any argument passed when invoking this skill (e.g.
`/review-guide 09-payload-encryption`). If none is given, audit the whole
guide. If a file, feature name, or topic is given, focus there but still
flag cross-references that break.

Dispatch the **`skillbox:code-reviewer`** subagent (read-only) with this brief:

> Review the learner guide (`guide/**/*.md`) for **semantic** accuracy
> against the reference application, focusing on whether each explanation
> still matches current behavior. Cross-check claims against the source:
> `README.md`, `Makefile`, `tools/features.py`, `payments/*.py`,
> `memory/*.py`, `shared/*.py`, `simulator/*.py`, `.env.example`,
> `compose.yaml`, `gateway/Caddyfile`, `production-ready-checklist.md`.
> For each guide step, verify:
>
> 1. The described concept and behavior match the live code path (read the
>    `FEATURE-ON`/`FEATURE-OFF` blocks the step enables, and the `NOTE:`
>    comments it references — the guide must not contradict them).
> 2. The "At a glance" table (files touched, concepts, prerequisites) is
>    still correct and complete.
> 3. The "Run and observe" instructions would actually produce what the
>    prose claims (commands, expected outputs, what shows up in the Web UI
>    / Event History / metrics).
> 4. Ordering and prerequisites are consistent across steps.
>
> Do NOT check things `tools/test_guide.py` already covers (existence of
> features, targets, scenarios, metric names, internal links) — assume
> those pass. Do NOT modify any file. Produce a concise report of concrete
> findings ranked by severity (factual/behavioral errors first), each with
> the file, the exact claim, and the correction. Skip anything that is
> still correct.

## After the audit

Relay the findings to me, ranked by severity. **Do not edit any guide file
yet** — wait for me to confirm which fixes to apply. When I approve fixes,
apply them to the Markdown directly, then re-run `make check` (which runs
`tools/test_guide.py`) and re-align any changed tables with
`skillbox`'s `general-rules/scripts/check_tables.py`.
