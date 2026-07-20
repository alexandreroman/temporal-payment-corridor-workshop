---
name: "Versioning/patching is out of scope for the workshop"
description: "Do not teach workflow.patched/versioning in the slides; replay stays only as a light observation"
type: feedback
---

# Versioning/patching is out of scope for the workshop

Temporal **versioning / patching** (`workflow.patched(...)`, old-vs-new
execution forks) is explicitly excluded from the workshop scope and must not
appear in the slide decks. The Session 2 "replay & versioning fork" diagram
was removed for this reason.

**The replay-test theme is also out of the slides.** The Session 2 slides
carry NO "enabling a step changes the Event History / breaks the committed
replay test" framing at all (removed from the objectives, the Step 07 divider
+ hands-on, the Search-Attributes note, and the checkpoint). Do not
reintroduce it. Exception: *observing a durable Timer in the Event History* in
Step 04 is fine — that is the feature working, not the replay-test theme.

The **guide** keeps a minimal `## Step 4 — A note on replay` in step 07
(`guide/07-settlement-confirmation.md`): the learner running `make test`
there genuinely hits the by-design failing replay fixture and needs the
heads-up. Regenerating the fixture / replay testing belongs to the Session 3
testing step [12]. (See [[project_all_features_test_contract]].)

**Why:** the audience scope emphasises durable agents, encryption, light
metrics, search attributes, and tests (see [[project_workshop_audience]]);
versioning is a separate advanced topic the workshop does not cover.

**How to apply:** never reintroduce versioning content in the slides; if a step
changes workflow history, frame it as a replay-test observation deferred to the
testing session. See [[project_workshop_slides]] and
[[feedback_slides_style_conventions]].
