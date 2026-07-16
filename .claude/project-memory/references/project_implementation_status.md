---
name: "Implementation status"
description: "Workshop feature-set work that is still pending (not yet implemented)"
type: project
---

# Implementation status

Workshop feature-set work that is still pending. Completed
changes live in git history and are intentionally not repeated
here — this note tracks only what remains to do.

## Keeping this up to date

- **When:** update this note whenever the pending set changes —
  when a listed item ships (implemented and verified), and when a
  new piece of not-yet-implemented work is decided. Do it in the
  same session the change is agreed or completed, not later.
- **How:** when an item ships, **remove** its section entirely
  (do not move it to a "done" list — completed work lives in git
  history). When new pending work is decided, add a section with
  the same shape: a short *what*, a **Why:** line, and a **How to
  apply:** line. If the note becomes empty, delete the file and
  its `MEMORY.md` pointer. Keep the `MEMORY.md` index line
  generic — do not name individual pending items there.

## Compliance as a gate, not a competing proposer (not yet implemented)

Refactor the coordinator's proposal merge so the compliance agent
*validates* the instruction agent's fix instead of proposing a
competing correction. Recorded as future work to handle in a later
session; not a `FEATURE` toggle for now.

- **Why:** both agent child workflows return `CorrectionProposal`
  and the coordinator keeps the highest-`confidence` one via
  `_select_best` (`payments/workflows.py`). That conflates orthogonal
  concerns — operational repair and compliance are not interchangeable
  candidates, so a more-confident instruction fix can silently discard
  a compliance violation. In a real cross-border correction system
  compliance is a gate/veto (and a sanctions hit a hard hold), never
  outvoted by confidence.
- **How to apply:** give `ComplianceAgentWorkflow` a distinct output
  (e.g. a `ComplianceVerdict` with `compliant`, `violations`,
  `confidence`) instead of `CorrectionProposal`; the coordinator
  applies the instruction agent's fix only when compliance clears it,
  blocks/holds on any violation regardless of instruction confidence,
  and routes the low-confidence case into the existing
  [[human-approval]] path. Parallel fan-out may stay, but merging then
  combines constraints and escalates same-field conflicts to a human —
  never `max(confidence)`.
- **Also change the agent, not just the workflow:** in
  `payments/agents.py` the `compliance_agent` has
  `output_type=AgentCorrection` and instructions telling it to
  *propose a correction*. A verdict output means rewriting that
  `output_type` (to the verdict model) and its prompt (validate, don't
  propose), plus the `_propose` path in `payments/workflows.py`, which
  currently assumes both agents return an `AgentCorrection`.
- **Replay fixture will break:** any change to the coordinator's
  workflow code invalidates the committed
  `payments/testdata/coordinator-history.json`, so `test_replay.py`
  fails until regenerated with `make capture-history` (memory service
  must be running first — see [[Regenerating the replay fixture needs
  the memory service on make's port]] for the port gotcha).
- **Preserve progressive activation:** the merge logic sits amid the
  coordinator's existing `FEATURE-ON/OFF` blocks
  (`human-approval-signal`, `settlement-confirmation`); keep that
  structure intact per [[Authoring toggleable FEATURE blocks]] rather
  than rewriting the coordinator in place.
- **Tests affected:** changing the compliance agent's `output_type`
  touches `payments/test_worker.py` and `test_replay.py`; follow
  [[Testing TemporalAgent-based workflows under start_local]] (register
  a `TestModel` stand-in under the real workflow name; `Agent.override`
  does not reach the model activity).
