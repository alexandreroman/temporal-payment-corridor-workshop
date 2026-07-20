# Workshop slides

The presenter decks for the three workshop sessions — a
[reveal.js](https://revealjs.com/) presentation dressed in a custom Temporal
brand theme. Slides carry the *why*, the *map*, and the verbal framing; the
hands-on *how* lives in the learner guide under [`../guide/`](../guide/), which
is the source of truth for each step's commands and expected observations. The
slides frame that guide — they never duplicate it.

## Preview

The decks reference their assets (theme CSS, deck JS, images) and load fonts
over relative URLs, so they must be **served over HTTP** — opening an `.html`
file directly (`file://`) leaves reveal.js unable to resolve its assets.

```bash
make slides            # serve on http://127.0.0.1:8000 (no-cache)
make slides PORT=9000  # override the port
```

`make slides` runs [`../tools/slides.py`](../tools/slides.py), a stdlib static
server that sends `Cache-Control: no-store` on every response — without it the
webview caches CSS/JS aggressively and edits appear to do nothing. It prints a
banner linking the landing page and each session. In a Casper worktree the port
is derived from `CASPER_PORT` (offset `+3`) so parallel worktrees never collide.

While presenting: arrow keys navigate, `Esc` opens the slide overview, and `S`
opens the speaker view (current + next slide, notes, and a timer).

## Layout

```
slides/
  index.html        landing page linking the three sessions
  session-1.html    Durable agents: the core        (guide steps 00–03)
  session-2.html    Reliability & control flow      (guide steps 04–08)
  session-3.html    Production & compliance         (guide steps 09–13)
  assets/
    theme.css         Temporal brand theme + per-slide-type layout
    deck.js           shared reveal.js + Mermaid bootstrap
    temporal-mark.png the mark used as corner furniture and on covers
```

Each session is ~22 inline-HTML slides, targeting ~30–40 minutes of
slide-facing time in a 2-hour session. All content is English and timeless (no
dates, headcounts, or engagement-specific detail).

## Slide grammar

Every `<section>` carries a type class that drives its layout (defined in
`theme.css`). Reuse these rather than inventing new ones, so the decks read as
one system:

| Class | Role |
| --- | --- |
| `type-title` | Session cover (centered, the mark enlarged) |
| `section-divider` | Step divider — green `Step NN` kicker + big title |
| `type-objectives` | "By the end you'll be able to…" bullet list |
| `type-content` | Recap / summary card rows (the augmented 3-card layout) |
| `type-framing` | Problem → Temporal concept → Observe, with speaker notes |
| `type-diagram` | One inline Mermaid diagram + legend + caption |
| `type-code` | One signature pseudo-code snippet (neutral panel) |
| `type-handson` | The terminal block a learner runs, + a predict prompt |
| `type-checkpoint` | "What we just saw" checklist + a tie-back line |
| `type-bridge` | Teaser into the next session, with a `deck-next` pill |

Working slides anchor the kicker + title at the top and center the body
beneath; cover-style slides (`type-title`, `section-divider`, `type-bridge`)
are fully centered.

## Diagrams

Diagrams are **inline Mermaid** (`<div class="mermaid">`), colored by role with
`classDef` and paired with a `.legend` and a `.diagram-caption`. The role
palette: client = blue, temporal = teal, activity = amber, store = green,
external = magenta, llm = olive, human = indigo.

`deck.js` renders each diagram with `mermaid.render()` (not `mermaid.run()`,
which fails on the zero-sized non-active slides) after `document.fonts.ready`,
so labels are measured with the final web font. Keep flowcharts `LR` and use
`curve: "linear"`.

## Speaker notes

`type-framing` and most other slides carry verbatim delivery notes in
`<aside class="notes">`, surfaced in the speaker view (`S`). They are written to
be spoken, not read off the slide.

## Editing notes

- **Code appears in exactly one place per snippet:** a `type-code` slide,
  1–2 per session (6–9 lines). It is a neutral bordered panel — deliberately
  not the green-glow terminal `.cmd` — so "code you read" never looks like
  "commands you type". The full code stays in the guide.
- **Terminal blocks** (`.cmd`) prefix each entered command with a green `$` and
  show real captured output in a muted `.out`. Their hyphens stay literal ASCII
  so commands remain copy-pasteable.
- **Typography** is hardened in `theme.css` + `deck.js`: short display blocks
  use `text-wrap: balance` and prose uses `text-wrap: pretty` (no stranded
  last-line words), and `deck.js` swaps intra-word hyphens for the non-breaking
  hyphen (U+2011) so compounds like `long-lived` never break across lines —
  skipping code, terminal, and diagram text.
- **Fonts** load from Google Fonts (Inter + JetBrains Mono). For a fully
  offline deck, vendor the `.woff2` files and swap the `<link>` for
  `@font-face`.
