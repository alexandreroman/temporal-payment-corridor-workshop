---
name: "Slide layout & style conventions (keep across sessions)"
description: "The visual/content rules the Session 1 deck settled on; apply verbatim to Sessions 2 & 3"
type: feedback
---

# Slide layout & style conventions (keep across sessions)

These conventions were tuned through review on Session 1
(`slides/session-1.html`). Sessions 2 & 3 must match them exactly so the
decks read as one system. See [[project_workshop_slides]] and
[[reference_slides_authoring_workflow]].

**Per-slide vertical layout — the title never jumps.**
- Working slides (objectives, motivation/overview cards, framing, all
  diagrams, hands-on, checkpoint): the **kicker + title stay anchored at the
  top**; the body sits in a `<div class="body">` that fills and centres in
  the space beneath. Content is wrapped in `.body`, not placed directly.
- Statement slides (session title `type-title`, `section-divider`,
  `type-bridge`): fully centred.
- Reveal sets the active slide `display: block` with high specificity, which
  defeats per-type flex. theme.css forces `display: flex !important` on every
  layout type class — keep that when adding types.

**Spacing.** Lists (`type-objectives`, `type-checkpoint`) use a **fixed
comfortable gap (~1.6rem)** anchored under the title — NOT `space-evenly`
(too airy for short bullets; the user rejected it). Framing's 3 sentences
DO use `space-evenly`. Card slides anchor the card row just under the title
(`padding-top`, not vertical-centre). Checkpoint's tie-back is pinned to the
bottom (`margin-top:auto`).

**Every step gets a `section-divider`** (Steps 00–03 each have one). Divider
kicker is just `Step NN` — no feature-toggle name.

**Kickers are plain uppercase green labels** (e.g. `Human approval`,
`Architecture`, `Checkpoint`). Do NOT put the hyphenated feature-toggle name
(`human-approval-signal`) in a kicker — it reads badly uppercased. The exact
toggle name lives in the guide, not the slides.

**Terminal / hands-on blocks.** `.cmd` is a **full-width** terminal panel
(green border glow). Each entered command line is prefixed with a green `$`
(`<span class="prompt">$</span>`); comment (`#`) and continuation lines carry
no prompt. Show **real captured output** beneath commands in a muted
`<span class="out">` (`white-space: pre-wrap` preserves column alignment).
Example facts: `make dev` prints the URL banner ("The stack is up." / "Open:"
/ Web UI + Temporal Web UI at `localhost:8080`); default `make simulator`
runs the `memory-hit` scenario and prints `scenario/payment/workflow
(correction-<id>)/accepted`.

**Predict-then-observe prompts** break at sentence boundaries (`<br>`) so a
long prompt never wraps mid-sentence.

**Session title** is session-specific (`Durable agents: the core`), white
title with a green keyword, the Temporal mark on it; NO "Session X of 3"
line and NO separate general workshop cover slide (both were removed).

**Bridge (`type-bridge`)** = white session name + a green `→` at the end of
the title, no "Next:" prefix (the kicker already says "Next session"); teaser
centred and width-constrained (`max-width` ~60%).

**Backdrop.** The cosmic aurora gradient lives on `.reveal` (not
`.reveal-viewport`, which `.reveal` paints over and would hide it).

**Logo.** Mark-only PNG (`assets/temporal-mark.png`, no wordmark): 38px
bottom-left furniture, 64px on the title slide; the corner furniture is
hidden on cover-style slides via `data-state="cover"`.

**Pseudo-code slides (`type-code`, added in Session 2).** The decks show
code in exactly ONE place: a dedicated `type-code` slide (kicker + title
anchored top, snippet centred beneath). When a `.diagram-caption` note is
present it is a **direct child of the section** (a sibling of `.body`, NOT
inside it) so it pins to the bottom while the `.body` grows and vertically
centres the `<pre>` in the space above — same pattern as the diagram slides'
caption.
It is a **neutral bordered panel** (`--t-border`), deliberately NOT the
green-glow terminal `.cmd`, so "code you read in the guide" never looks like
"commands you type". Keep it to **1–2 signature snippets per session**
(6–9 lines each); the full code stays in the guide. Wrap the one signature
API line in `<span class="hl">` (mint green) and inline comments in
`<span class="c">` (muted). Escape `<`/`&` as entities. `type-code` is in the
`display:flex !important` activation list in `theme.css`.

**Why:** every one of these is a user correction from the Session 1 review or
a Session 2 design decision; re-deriving them wastes time and risks an
inconsistent deck.

**How to apply:** copy `session-1.html` as the template for Session 2/3,
reuse `assets/theme.css` + `assets/deck.js` unchanged, and keep the same
class vocabulary and per-type structure.
