---
name: "How to author & preview the workshop slides"
description: "Serving, previewing with Casper, and the repo facts the decks quote"
type: reference
---

# How to author & preview the workshop slides

Workflow used to build and review the reveal.js decks under `slides/`. See
[[project_workshop_slides]], [[feedback_slides_style_conventions]],
[[reference_slides_mermaid_render]].

**Serve over HTTP with no caching.** The deck must be served (not opened via
`file://`) so relative assets + fonts load. The Casper/webview caches assets
aggressively — a plain `python3 -m http.server` will keep serving stale
CSS/JS. Use `make slides` (PORT=<n> to override), which runs
`tools/slides.py` — a stdlib no-cache server that sends
`Cache-Control: no-store` on every response and prints a banner of the
landing + per-session URLs. `python -m tools.slides --open` opens the
landing page in a browser; `--port`/`SLIDES_PORT` set the port. The port
defaults to 8000, but in a Casper worktree the Makefile derives it from
`GATEWAY_PORT` (= `CASPER_PORT`) at offset +3 and exports `SLIDES_PORT`, so
parallel worktrees never collide (see [[Casper worktree port remap]]).
Symptom of a stale view: your CSS/JS edit "does nothing" until you
cache-bust.

**Preview + verify with the Casper browser.** `casper browser open
http://127.0.0.1:<port>/session-N.html#/<i>` jumps to a slide by reveal hash;
or `casper browser eval "Reveal.slide(i)"`. **Wait ~1s after navigating
before screenshotting** — reveal transitions, and an immediate capture
grabs the previous slide. The browser panel is portrait, so the 16:9 stage
is letterboxed: crop the screenshot to 16:9 for review, e.g.
`magick shot.png -crop ${W}x$((W*9/16))+0+$(((H-W*9/16)/2)) out.png`. Check
`casper browser console --level error` after reloads (Mermaid errors surface
there).

**Authoring split.** Slide artifacts (`slides/**` HTML/CSS/JS, content) were
authored directly — the reveal.js skill is a hands-on edit→screenshot loop.
Real source/build files (e.g. `Makefile`, app code) still go through
`skillbox:code-writer` per the repo's CLAUDE.md.

**Repo facts the decks quote (verify before reuse; keep timeless):**
- Gateway is the single entry at `localhost:8080`; `/temporal` = Temporal
  Web UI. `make dev` prints these via the Makefile `show_urls` banner.
- Default `make simulator` scenario is `memory-hit` (offline, no model
  call); payment ids are `pmt-<8 hex>`, workflow id `correction-<payment_id>`.
- `make feature-enable NAME=<feature>` toggles the guide features
  (session 2: approval-timeout, non-retryable-validation, retry-alerting,
  settlement-confirmation, search-attributes; session 3: payload-encryption,
  memory-workflow, observability, testing, wrap-up).

**How to access:** the guide steps `guide/00..13-*.md` are the source of
truth for each session's content, commands, and expected observations; the
slides frame them (why/map/verbal), never duplicate them.
