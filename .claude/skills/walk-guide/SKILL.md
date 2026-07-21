---
name: walk-guide
description: Empirically walk the learner guide (guide/) as a real attendee would — run every command, enable each feature, observe the outcome — to catch instructions, commands, code, or expected output that drift from reality, then review and correct in the same pass. Also runs a static, read-only semantic audit when the stack can't be run or when only a review is wanted.
argument-hint: "[optional: a guide step file, feature name, or arc to scope it; add --static for a read-only audit]"
---

**Walk the learner guide in `guide/` the way an attendee actually would** —
execute each step against a live stack, observe the result, and fix every
instruction that does not hold up.

## Two ways to run it: empirical (default) and static

This skill has one job — keep the guide's prose, commands, code, and expected
output true to the app — and two modes for doing it:

- **Empirical (default).** Bring the stack up, run the commands the guide
  prints, enable the features, fire the scenarios, and compare what the
  learner *sees* against what the guide *says*. Then **review and correct in
  one pass** — no separate approval gate, because each finding is backed by an
  observation you can point at.
- **Static (`/walk-guide --static`, or any run where you can't bring the stack
  up).** A **read-only** semantic audit: read the prose and the code side by
  side and check whether the explanations still match what the code does. It
  cannot catch what only surfaces when you *run* the guide, so it is the weaker
  check — and because nothing is observed, it **stops for your approval before
  editing anything**. Use it when Docker or an LLM key is unavailable, or when
  you explicitly want a review without touching state.

Prefer the empirical mode whenever you can run the stack. Fall back to static
only when you must, and say which mode you ran.

Mechanical drift (`make` targets, `NAME=`, `SCENARIO=`, `corridor_*`
metrics, internal links, screenshot manifest) is already covered by
`tools/test_guide.py` in `make check` and by `.github/workflows/links.yml`.
Assume those pass; do not re-check them in either mode. This skill catches what
those cannot: a command that fails or needs an unstated prerequisite, output
that no longer matches, a feature whose enabled code behaves differently than
described, an ordering that breaks because a prior step left state behind, or a
stale explanation whose prose no longer describes what the code actually does.

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

## Procedure (empirical)

Scope from the argument, if any (e.g. `/walk-guide 05-non-retryable-validation`,
`/walk-guide approval-timeout`, `/walk-guide "Arc 1"`). No argument → walk
the whole guide in order, starting at `00`. If the argument is `--static` (with
or without a scope), run the **static mode** below instead.

1. **Confirm a clean baseline.** `make feature-list` should show every
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
   - No Docker → you cannot walk empirically; switch to the **static mode**
     below and label the review as such up front.

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

### Worktree port remapping is never a finding

If you are running in a worktree, `make worktree-ports` writes a
`compose.override.yaml` that remaps the gateway host port to `CASPER_PORT`
(and Temporal off `CASPER_PORT + 1`). So the `make dev` banner, the Web UI
URLs, and any `curl http://localhost:8080/…` will show a **different port**
than the guide's canonical `8080`.

That difference is expected — **do not flag it and do not "correct" the
ports.** The guide is written against the canonical `8080` on purpose; a
worktree remap is a local-environment artifact, not guide drift. To
actually run and observe, substitute the real host port yourself (check
`compose.override.yaml` / `$CASPER_PORT`), but leave every `8080` in the
guide as-is. Only flag a port when it is wrong *independently* of remapping
(e.g. the guide points at `:8081` where the app never listens).

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

## Static mode (read-only audit)

Use this when you cannot bring the stack up, or when invoked with `--static`.
It is a **semantic accuracy audit**: does the prose still describe what the
code actually does? Stale explanations, conceptual claims that no longer hold,
a `NOTE:` the guide summarizes incorrectly, steps whose observed behavior has
changed, ordering/prerequisite contradictions between steps.

Dispatch the **`skillbox:code-reviewer`** subagent (read-only) with this brief:

> Review the learner guide (`guide/**/*.md`) for **semantic** accuracy
> against the reference application, focusing on whether each explanation
> still matches current behavior. Cross-check claims against the source:
> `README.md`, `Makefile`, `tools/features.py`, `payments/*.py`,
> `memory/*.py`, `shared/*.py`, `simulator/*.py`, `.env.example`,
> `compose.yaml`, `gateway/Caddyfile`.
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

If a scope argument was given, focus the brief there but still flag
cross-references that break. Relay the findings to me ranked by severity, then
**wait for me to confirm which fixes to apply** — there is no observation to
justify auto-correcting in static mode. When I approve, apply the fixes using
the routing in "Review, then correct" below, then follow "After correcting".

## Review, then correct

Route each fix by *where the truth is*:

- **Guide is wrong / imprecise** → edit the Markdown in `guide/` directly
  (prose, commands, expected output, tables). This is documentation, so it
  is not delegated to `code-writer`.
- **Guide is right but the code drifted** → the fix touches source; delegate
  it to the **`skillbox:code-writer`** agent per the project conventions.
  Never hand-edit source files.
- **Genuinely ambiguous which should change** → surface it in the review and
  ask me; do not guess.

**In empirical mode**, relay the complete review first (findings ranked by
severity), then apply the corrections without waiting for a separate approval —
the observations are the justification. **In static mode**, relay the findings
and wait for my approval before editing anything (see "Static mode" above).

## After correcting

- Re-run `make check` (runs `tools/test_guide.py`) — it must pass.
- Re-align any Markdown table you touched with
  `skillbox`'s `general-rules/scripts/check_tables.py`.
- If a fix was behavioral, re-walk that one step to confirm the guide now
  matches reality (empirical mode).

## Leave no trace

A learner walkthrough mutates state. Before finishing, restore the clean
baseline a fresh attendee expects, and confirm it (static mode mutates
nothing, so this applies only when you ran empirically):

- `make feature-disable NAME=…` for every feature you enabled.
- Undo every hand-edit the guide told you to make (`_SIMULATE_*` switches,
  scratch `.env` values) — but keep the guide/code *corrections*.
- Tear down the stack (`make app-down` if you used it, and stop the
  backgrounded `make dev`).
- End with `make feature-list` clean and a `git status` that shows only
  your intended corrections. Report what remains changed.
