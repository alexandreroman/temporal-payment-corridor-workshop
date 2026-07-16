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

## Run a real agent (not yet implemented)

Fire a payment anomaly that **misses** corridor memory, forcing
the child workflows to actually call the LLM (`source=llm`).
Intended as a documented step plus a parameterizable simulator
(anomaly from env / CLI flag, defaulting to the seeded happy
path) — **not** a `FEATURE` toggle, since it is about *running*
the app differently, not activating dormant code.

- **Why:** the default `simulator` always fires the pre-seeded
  `US->IN` / `wrong_iban` anomaly, which hits passive corridor
  memory and short-circuits before `agent.run()`, so the
  headline capability (durable Pydantic AI agents) is never
  exercised in the default demo and no API key is needed.
- **How to apply:** use a memory-miss anomaly (e.g.
  `currency_mismatch`); require the provider key
  (`ANTHROPIC_API_KEY` etc.) for this step only; have learners
  observe the model-request activity in the Web UI, a possibly
  sub-threshold confidence routing into the [[human-approval]]
  path, durable resume after a mid-call worker kill, and durable
  retries from the now-always-on `_MODEL_ACTIVITY_CONFIG`.
