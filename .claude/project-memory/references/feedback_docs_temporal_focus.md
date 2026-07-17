---
name: "Docs and comments stay focused on Temporal"
description: "Strip app-implementation plumbing from README/guide/comments; keep the durable-execution teaching"
type: feedback
---

# Docs and comments stay focused on Temporal

The README, the learner guide, and code comments teach **Temporal /
durable execution**. Strip this app's implementation *plumbing* — it is
noise that distracts from the subject. Plumbing includes: gateway routing
internals, service bind addresses, port derivations, container-vs-dev
routing, listing-seam mechanics (which query/attribute feeds which listing
path), the corridor-memory keying discriminator, correction status-lifecycle
wiring, and config-load asides (e.g. *where* Logfire is configured, uvicorn
reload subprocess behavior).

This **refines**, not overrides, [[feedback_code_comments]] and
[[feedback_note_marker]]: keep the abundant Temporal-teaching comments, every
`Source:` link, and the `NOTE:` markers on teaching comments. Only trim the
prose that explains app-specific plumbing.

**Why:** the subject is Temporal; app-implementation detail hurts
comprehension of the durable-execution concepts the material exists to teach.

**How to apply:** when writing or editing docs, keep the cross-border-payments
domain framing and the Temporal concepts a lesson needs; cut incidental ops
plumbing. When editing comments, trim only unambiguous app-plumbing and leave
anything that teaches a Temporal/production concept. Pairs with
[[project_workshop_audience]].
