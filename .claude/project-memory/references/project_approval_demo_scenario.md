---
name: "Approval-flow demos default to the compliance scenario"
description: "Hold-dependent hands-on steps use SCENARIO=compliance; no scenario is a deterministic hold, and corridor memory makes re-runs auto-apply"
type: project
---

# Approval-flow demos default to the compliance scenario

The hands-on steps that need a correction to **hold** for human review
default to `make simulator SCENARIO=compliance`, not `needs-approval`:
guide steps 03 (human-approval), 04 (approval-timeout), 08
(search-attributes), and slides `session-1` step 03 + `session-2` steps
04/08.

No scenario deterministically reaches the awaiting-approval hold:

- `needs-approval` and `low-confidence` are **best-effort** — a decisive
  model (e.g. `openai:gpt-5-mini`) clears the `CONFIDENCE_THRESHOLD` (0.75)
  and auto-applies, so the approval panel / durable timer / awaiting filter
  often have nothing to act on.
- `compliance` (US->GB currency mismatch) holds **reliably only on a
  corridor-memory MISS**: the compliance agent flags an unambiguous
  violation, forcing the `REVIEW` branch regardless of confidence.
- Corridor memory is written when an LLM-sourced correction is applied
  (`_learned_pattern` in `payments/workflows.py`, learned confidence ~0.9).
  So once a held `compliance` correction is approved, re-runs of that
  corridor hit memory (`source=memory`, presumed compliant, no LLM call)
  and **auto-apply**. Restarting the stack (`make dev`) clears the
  in-memory corridor store and restores the miss. This is the passive
  memory covered in step 10.

**Why:** verified by live reproduction — the guide previously claimed
`needs-approval` (and briefly "deterministic") would hold, but it does not;
the compliance violation is the only reliable, model-independent trigger,
and the memory-learning gotcha is easy to hit across steps (step 03's
approval contaminates step 04's hold). See [[project domain model
simplified]] and the memory-service notes.

**How to apply:** keep these demos on `compliance` with the "reliable on a
memory miss + restart the stack to clear memory" framing; do NOT revert
them to `needs-approval`. The step-03 screenshots
(`03-approval-panel.png` shows a compliance violation, `03-app-applied.png`)
are captured from a `compliance` run.
