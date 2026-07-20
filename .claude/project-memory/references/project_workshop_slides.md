---
name: "Workshop slides live in slides/, reveal.js + Temporal theme"
description: "Slide deck tooling, location, structure, and the A–G slide grammar"
type: project
---

# Workshop slides live in slides/, reveal.js + Temporal theme

The workshop slides are a reveal.js deck under `slides/`, generated with
the `revealjs` plugin skill's scaffold (`create-presentation.js`) but
dressed in a custom **Temporal brand theme** (`slides/assets/theme.css`).
Slides are authored as **inline HTML** sections (one `.html` per session),
not Markdown. Shared bootstrap is `slides/assets/deck.js`
(`TemporalDeck.init()`); the Temporal mark is `slides/assets/temporal-mark.png`.
`slides/index.html` is a themed landing page linking the three sessions.

Theme mirrors Temporal's "Temporal for AI" brand deck: dark navy background
(`--t-bg #0b0d1a`), mint-green accent (`--t-green #4ce0a0`), Inter (thin
titles) + JetBrains Mono, mark bottom-left, slide numbers bottom-right, and
uppercase green kickers. Diagrams are **inline Mermaid coloured by
role** via `classDef` (client=blue, temporal=teal, activity=amber,
store=green, external=magenta, llm=olive, human=indigo) with a legend +
caption panel — the style of the brand deck's architecture slides.

Guiding principle: **slides never duplicate the learner guide**. They carry
the why, the map, and the verbal framing; the guide carries the how. Target
~15–18 lean slides per 2-hour session; ~30–40 min slide-facing time.

Seven reusable slide types (the "grammar"), as CSS classes on `<section>`:
`type-title`, `section-divider`, `type-objectives` (A), `type-recap` (B),
`type-framing` (C, **verbatim speaker notes** in `<aside class="notes">` —
highest-value artifact because delivery is in English, a non-native
language), `type-diagram` (D), `type-handson` (E), `type-checkpoint` (F),
`type-bridge` (G).

Three-session split (4/5/5): S1 "Durable agents: the core" (steps 00–03 +
crash&resume demo); S2 "Reliability & control flow" (04–08); S3 "Production
& compliance" (09–13).

Status: **Sessions 1 and 2 built and validated.** Session 1
(`slides/session-1.html`, 22 slides) covers steps 00–03 and now includes two
`type-code` pseudo-code slides (the `asyncio.gather` fan-out after the fan-out
diagram; the `@workflow.signal`/`@workflow.query`/`wait_condition`
human-in-the-loop trio in Step 03), matching Session 2's use of the element.
Session 2
(`slides/session-2.html`, 22 slides) covers steps 04–08: title → recap (B,
built as a `type-content` slide with 3 cards) → objectives, then a
`section-divider` + hands-on per step, three role-coloured diagrams (a
retryable/non-retryable decision tree, a retry timeline, a Search-Attributes
visibility index) and two dedicated **pseudo-code** slides (`type-code`, see
[[feedback_slides_style_conventions]]). Versioning/patching AND the
replay-test/Event-History-change theme are deliberately absent from the slides
— see [[feedback_versioning_out_of_scope]] (the only Event-History mention left
is observing a durable Timer in Step 04). `index.html` links both. Session 3 (steps 09–13) and `slides/README.md` are still to build
— copy `session-2.html` as the richest template. All content is English and
timeless. Before building Session 3, read
[[feedback_slides_style_conventions]] (layout/style rules incl. `type-code`),
[[reference_slides_authoring_workflow]] (serve + preview), and
[[reference_slides_mermaid_render]] (diagram rendering).
