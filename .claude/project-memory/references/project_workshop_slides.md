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

Status: **Session 1 built and validated** (`slides/session-1.html`, 20
slides incl. a Step divider before each of steps 00–03). Each step has a
`section-divider`; hands-on command blocks are full-width terminal panels
with a green `$` prompt. Sessions 2 & 3 and `slides/README.md` are still to
build. All content is English and timeless. See
[[reference_slides_mermaid_render]].
