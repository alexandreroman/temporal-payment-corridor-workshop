---
name: "Docs and comments stay focused on Temporal"
description: "Strip app-implementation plumbing and learner-irrelevant content from README/guide/comments; keep the durable-execution teaching"
type: feedback
---

# Docs and comments stay focused on Temporal

The README, the learner guide, and code comments teach **Temporal /
durable execution**. Strip anything that distracts from that subject.

## 1. Strip app-implementation "plumbing"

Plumbing is noise: gateway routing internals ("injects the bearer token",
same-origin/CORS, which path routes where), service bind addresses, port
derivations, container-vs-dev routing, listing-seam mechanics (which
query/attribute feeds which listing path), the corridor-memory keying
discriminator, correction status-lifecycle wiring, and config-load asides
(e.g. *where* Logfire is configured, uvicorn reload subprocess behavior).

## 2. Strip learner-irrelevant content from learner-facing docs

Beyond plumbing, the README and guide must not carry content a learner has
no use for:

- **Contributor-only setup** — e.g. the pre-commit hook / `make setup`. The
  audience never writes or commits code (see [[project_workshop_audience]]),
  so contributor steps do not belong in the learner-facing docs. The
  Makefile target still exists; it is just not documented for learners.
- **The app's HTTP API route catalog / endpoint locations** — a route table
  (methods, paths, status codes) and "where the endpoints live" is
  app-internal contract, not a Temporal lesson. Keep only the practical
  `make simulator` / observe flow. The one Temporal concept (the API is a
  Temporal *client*, not a worker; single entry point) lives once, in the
  Architecture section.
- **Meta "conventions" sections** — source-link / docs-link / screenshot
  conventions are guide plumbing, not teaching.

## 3. The README must link to the guide

A learner landing on the README needs an obvious path into the learner
guide (a prominent link near the top). The README is reference
documentation, but it stays workshop/Temporal-focused — it is not the place
to document the app's internal HTTP contract.

## Preserve the teaching

This **refines**, not overrides, [[feedback_code_comments]] and
[[feedback_note_marker]]: keep the abundant Temporal-teaching comments,
every `Source:` link, and the `NOTE:` markers on teaching comments; keep the
cross-border-payments domain framing and the Temporal concepts a lesson
needs. Only trim unambiguous plumbing / learner-irrelevant prose.

**Why:** the subject is Temporal; app-implementation and contributor detail
hurt comprehension of the durable-execution concepts the material teaches.

**How to apply:** on every docs/guide/comment pass, sweep for the three
categories above and remove them, verifying no cross-reference is left
dangling (run `tools/test_guide.py`). Pairs with
[[project_workshop_audience]].
