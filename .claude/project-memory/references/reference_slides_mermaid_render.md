---
name: "Mermaid rendering in the reveal decks uses render(), not run()"
description: "How deck.js renders inline Mermaid reliably, and the gotchas it avoids"
type: reference
---

# Mermaid rendering in the reveal decks uses render(), not run()

`slides/assets/deck.js` renders each inline `<div class="mermaid">` with
`mermaid.render(id, source)` (which draws in Mermaid's off-DOM sandbox) and
injects the returned SVG — it does **not** use `mermaid.run({querySelector})`.

Three gotchas this avoids, all learned empirically:

- **run() fails on non-active slides.** reveal keeps non-current slides at
  zero size, so in-place `run()` makes dagre throw
  "Could not find a suitable point for the given distance". `render()` is
  size-independent, so every diagram renders up front regardless of which
  slide is showing.
- **Clipped node labels.** Mermaid measures label boxes before the web font
  loads, then Inter paints wider and clips. `deck.js` `await`s
  `document.fonts.ready` before rendering.
- **Source must be de-mangled.** The source is read from the div's
  `innerHTML` and passed through `decodeEntities()` (`&amp;`→`&`, `&lt;`→`<`,
  `&gt;`→`>`, …) so Mermaid gets clean text; `<br/>` is preserved for
  multi-line labels.

Also: flowchart `curve: "linear"` (not `basis`) — basis curves break
edge-label placement. Keep tall diagrams as `flowchart LR`, not `TB`; a TB
fan-out overflowed the slide. Serve the deck over HTTP (a no-cache static
server helps during authoring — the webview caches assets aggressively, so
bump the port or disable cache when JS/CSS changes do not appear).

This inline-HTML path has none of the Markdown-plugin pitfalls (the
`RevealHighlight` plugin injects `<span>` markup that corrupts
```mermaid fenced source), which is why the decks author diagrams as inline
HTML rather than Markdown. See [[project_workshop_slides]].
