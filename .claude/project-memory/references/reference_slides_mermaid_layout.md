---
name: "Controlling Mermaid nested-subgraph layout in the decks"
description: "Fixed outer-title band, the invisible-inner-subgraph spacer, subgraph direction, density, and tuning by measuring SVG geometry"
type: reference
---

# Controlling Mermaid nested-subgraph layout in the decks

Layout levers for nested `subgraph` clusters in the reveal decks — e.g. the
Session 1 architecture diagram, a "Temporal" box wrapping the payments and
memory namespaces. See [[reference_slides_mermaid_render]],
[[reference_slides_authoring_workflow]].

- **The outer subgraph's title sits in a fixed band above its children.** A
  nested cluster starts ~20 SVG units below the parent border regardless of
  `flowchart.padding` or `subGraphTitleMargin`, so the parent title overlaps
  the first child cluster. `subGraphTitleMargin.top` only moves the title
  text within that band (toward/into the child); `.bottom` inflates the
  title's label box, not the gap. Neither widens the band.
- **Spacer workaround:** wrap the child subgraphs in one extra invisible
  subgraph (`classDef invis fill:none,stroke:none,color:none;`, empty `" "`
  title). Its own empty title band pushes the children down, clearing the
  parent title with balanced room — this is how the "Temporal" title gets air
  above the namespace boxes.
- **`direction LR`/`TB` inside a subgraph IS honored** even when an external
  edge targets the subgraph by id (`API -->|...| T`). Put two child subgraphs
  side-by-side with parent `direction LR` plus a cross edge between their
  nodes; declaration order and edge direction set left vs right. Route each
  data-flow edge from the node that owns the I/O (HTTP edge from the
  coordinator/worker, not the store) so ranks read left→right.
- **Density:** set `nodeSpacing`/`rankSpacing` per-diagram via a leading
  `%%{init: {'flowchart': {...}}}%%` directive; lower values pack components
  tighter without touching the cluster structure.

**Why:** Mermaid exposes no per-side cluster padding, so these are the only
reliable levers, and each was found by trial rather than docs.

**How to access:** tune by MEASURING, not eyeballing — `casper browser eval`
reading a `.cluster rect` `getAttribute('y'|'height')` (SVG units) or
`getBoundingClientRect()` gives the exact border/title/child gaps to iterate
against, then screenshot to confirm. Every diagram/UI edit must be verified
against a real screenshot; assumptions about what a config change "should"
do are unreliable here.
