---
name: walk-guide
description: Empirically walk the learner guide (guide/) as a real attendee would — run every command, enable each feature, observe the outcome — to catch instructions, commands, code, or expected output that drift from reality, then review and correct in the same pass. User-invoked only, via /walk-guide.
disable-model-invocation: true
argument-hint: "[optional: a guide step file, feature name, or arc to scope the walkthrough]"
---

**Walk the learner guide in `guide/` the way an attendee actually would** —
execute each step against a live stack, observe the result, and fix every
instruction that does not hold up.

## Why this exists (and how it differs from `/review-guide`)

`/review-guide` is a **static, read-only** semantic audit: it reads prose
and code side by side and waits for your approval before touching anything.
It cannot catch what only surfaces when you *run* the guide.

`/walk-guide` is the **empirical** counterpart. It brings the stack up, runs
the commands the guide prints, enables the features, fires the scenarios,
and compares what the learner *sees* against what the guide *says*. It then
**reviews and corrects in one pass** — no separate approval gate, because
each finding is backed by an observation you can point at.

Mechanical drift (`make` targets, `NAME=`, `SCENARIO=`, `corridor_*`
metrics, internal links, screenshot manifest) is already covered by
`tools/test_guide.py` in `make check` and by `.github/workflows/links.yml`.
Assume those pass; do not re-check them. This skill catches what running the
guide reveals: a command that fails or needs an unstated prerequisite,
output that no longer matches, a feature whose enabled code behaves
differently than described, an ordering that breaks because a prior step
left state behind.

## Adopt the learner persona

The target audience is fixed in `guide/README.md` ("Who this is for"):
comfortable with Python, already met Temporal's core
ideas (workflows, activities, workers, dev server, Web UI), works in or near
payments, running **everything locally** — no Kubernetes, no cloud account.

Judge every step from *exactly* that level:

- **Do not** flag things this audience already knows (what a workflow is,
  what `curl`/`jq` do, basic Python).
- **Do** flag anything under-specified for that level: a tool used but never
  listed as a prerequisite, an env var referenced but never explained, a
  step that silently assumes a feature enabled earlier is still on.
- **Do** flag relevance (*pertinence*): content pitched too low or too high
  for the audience, or a tangent that does not serve the step's stated goal.

## Follow the steps literally — do not compensate

The single most important discipline: **do exactly what the guide says,
using only what it told the learner to have.** Your job is to reproduce the
attendee's experience, not to succeed despite the guide.

If a step breaks, an output differs, or a command needs something the guide
never mentioned — **that is a finding**, even if you personally know the
fix. Record what the guide said, what actually happened, and the correction.

| Rationalization | Reality |
| --- | --- |
| "I know what they meant, so it's fine." | The learner does not. Silently fixing it in your head hides the exact drift you were sent to find. |
| "This obviously needs `X` first." | If the guide did not say so, the learner won't do it. Flag the missing prerequisite. |
| "The output is close enough." | "Close enough" is where stale expected-output lives. Diff it literally. |

## Procedure

Scope from the argument, if any (e.g. `/walk-guide 05-non-retryable-validation`,
`/walk-guide approval-timeout`, `/walk-guide "Arc 1"`). No argument → walk
the whole guide in order, starting at `00`.

1. **Confirm a clean baseline.** `make feature-status` should show every
   feature disabled and `git status` should be clean. If not, stop and tell
   me — you must start from the state a fresh learner has.

2. **Establish what you can actually exercise, and say so.** Bringing the
   stack up needs Docker; scenarios other than `memory-hit` need an LLM
   provider key matching `CORRIDOR_MODEL` (see `01`/`.env.example`). Before
   walking, state which paths you can run:
   - Docker + key available → full walkthrough.
   - Docker only → offline `memory-hit` path runs; key-gated scenarios are
     verified statically (read the code path), **explicitly marked as not
     empirically exercised**. Never let a static check masquerade as a run.
   - No Docker → degrade to static verification for the whole run and say so
     up front; the review is weaker and you must label it as such.

3. **Bring the stack up once** with `make dev` (background it; it hot-reloads
   your later feature edits). Wait for the banner and the two URLs before
   proceeding. Keep it up for the whole walkthrough; tear it down at the end.

4. **Walk each step in order.** For every guide file:
   - Read the step as the learner reads it.
   - Run each command it prints, in order, from the state left by the prior
     step. `make feature-diff NAME=…` → `make feature-enable NAME=…` → read
     the now-live `FEATURE-ON`/`FEATURE-OFF` blocks and the `NOTE:` comments
     the step points at → run the scenario → observe the terminal, the Web
     UI (Event History, workflow tree, search attributes), the metrics
     endpoint, and any `curl` output the step promises.
   - Compare, literally, against every claim: command syntax and flags,
     expected terminal/`curl` output, what appears in the Web UI, the "At a
     glance" table (files touched, concepts, builds-on), ordering, and the
     Checkpoint items — can you actually tick each box?
   - Honor `Revert`: `make feature-disable NAME=…` and undo any hand-edits
     the step told you to make (e.g. a `_SIMULATE_*` fault switch) before the
     next step, so the next step starts where its learner would.

5. **Record findings as you go**, each with: file and location, the exact
   claim/command, what actually happened, severity (a step that fails or
   misleads outranks imprecision), and the concrete correction. Skip
   anything that held up.

### Visual checks (Web UI)

Many steps tell the learner to *look* — at the Temporal Web UI
(<http://localhost:8080/temporal>), the app Web UI (<http://localhost:8080>),
an Event History, a workflow tree, or search attributes. Do not infer these
from logs alone: open the page and confirm what the prose promises is
actually on screen.

Drive it with a browser, and **prefer the integrated in-workspace browser
over an external one** — use the `casper:casper-browser` skill (or the
equivalent integrated browser in your harness) to navigate, screenshot, and
inspect the page; only fall back to an external browser (e.g.
`chrome-devtools-mcp`) if no integrated one is available. When a step
references a screenshot in `images/`, use your capture as the ground truth
for whether the caption and surrounding claims still match the real view.

## Review, then correct — in the same pass

Relay the complete review first (findings ranked by severity), then apply
the corrections without waiting for a separate approval — the observations
are the justification. Route each fix by *where the truth is*:

- **Guide is wrong / imprecise** → edit the Markdown in `guide/` directly
  (prose, commands, expected output, tables). This is documentation, so it
  is not delegated to `code-writer`.
- **Guide is right but the code drifted** → the fix touches source; delegate
  it to the **`skillbox:code-writer`** agent per the project conventions.
  Never hand-edit source files.
- **Genuinely ambiguous which should change** → surface it in the review and
  ask me; do not guess.

## After correcting

- Re-run `make check` (runs `tools/test_guide.py`) — it must pass.
- Re-align any Markdown table you touched with
  `skillbox`'s `general-rules/scripts/check_tables.py`.
- If a fix was behavioral, re-walk that one step to confirm the guide now
  matches reality.

## Leave no trace

A learner walkthrough mutates state. Before finishing, restore the clean
baseline a fresh attendee expects, and confirm it:

- `make feature-disable NAME=…` for every feature you enabled.
- Undo every hand-edit the guide told you to make (`_SIMULATE_*` switches,
  scratch `.env` values) — but keep the guide/code *corrections*.
- Tear down the stack (`make app-down` if you used it, and stop the
  backgrounded `make dev`).
- End with `make feature-status` clean and a `git status` that shows only
  your intended corrections. Report what remains changed.
