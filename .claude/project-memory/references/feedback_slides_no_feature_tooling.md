---
name: "Slides never reference the feature-toggle tooling"
description: "Slide content omits the FEATURE-ON/FEATURE-OFF 'REPLACE' toggle vocabulary; describe changes in plain language"
type: feedback
---

# Slides never reference the feature-toggle tooling

Slide content (code comments shown on slides, diagram
captions, speaker notes) never names the workshop
feature-toggle tooling's internal vocabulary — notably
the "REPLACE" concept (the `FEATURE-ON`/`FEATURE-OFF`
replace-pairing). Describe a change in plain language
instead: "same change in both processes", "both handlers
change in `memory/app.py`".

**Why:** the toggle mechanism is workshop scaffolding
driven by the external guide; it has no connection to
Temporal and adds nothing to the learner's mental model.
The slides teach Temporal concepts, so tooling jargon is
noise. (Related: [[feedback_docs_temporal_focus]],
[[reference_feature_block_authoring]].)

**How to apply:** keep `REPLACE` / `FEATURE-ON` /
`FEATURE-OFF` out of every slide surface. The
`make feature-enable NAME=...` hands-on command is fine —
that is the learner's real action — the objection is only
to naming the underlying toggle mechanism. Ordinary
English "replace/replaced" as prose (e.g. "we replaced the
entire backend with a durable workflow") is fine; the ban
is on the tooling term.
