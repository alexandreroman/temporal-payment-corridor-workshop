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

## search-attributes enabled leaves `handle` unused (F841)

Enabling the `search-attributes` feature alone raises a ruff
`F841` in `payments/test_workflows.py`
(`test_coordinator_exposes_listing_query_surface`): the sole live
use of the `handle` local lives in the `FEATURE-OFF:
search-attributes` block (the `describe_anomaly` query), so
enabling the feature comments it out and `handle` becomes
assigned-but-unused. Baseline `make check` (all features off)
passes; the lint only bites in the enabled state.

- **Why:** the test was introduced by the payments-API (backend)
  work, and its other `handle` uses sit in the `human-approval-signal`
  FEATURE-ON block. So `search-attributes` on + `human-approval-signal`
  off is the failing combination — a real workshop-step lint gap, not
  caused by the compliance-gate refactor.
- **How to apply:** decide the intended enable order. If
  `search-attributes` is meant to be enabled together with
  `human-approval-signal`, document that; otherwise make the enabled
  state consume `handle` (or drop it) so ruff stays clean in every
  toggle combination, honouring [[Authoring toggleable FEATURE blocks]].
