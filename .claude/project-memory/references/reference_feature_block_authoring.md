---
name: "Authoring toggleable FEATURE blocks"
description: "How to write FEATURE-ON/FEATURE-OFF blocks so they enable to valid, ruff-clean Python and round-trip"
type: reference
---

# Authoring toggleable FEATURE blocks

`tools/features.py` toggles `# region FEATURE-ON: <name>` /
`# region FEATURE-OFF: <name>` regions (VS Code folding
markers, closed by `# endregion <KIND>: <name>`). `FEATURE-ON` is
the block that goes live when the feature is enabled; `FEATURE-OFF`
is the base code live when it is off. Rules for authoring these blocks
so they enable cleanly and round-trip:

- **Enable strips exactly one leading `# `** per body line
  (`_uncomment`). So distinguish line kinds:
  - **Code** that must go live: single-comment it
    (`# client = ...` → `client = ...`).
  - **Prose** that must stay a comment after enabling:
    double-comment it (`# # note` → `# note`).
- **A region must yield at least one live Python line** when
  uncommented, else it still reads as disabled.
- **A feature that REPLACES live code needs a paired
  `FEATURE-OFF`** wrapping the starting-point code; enable
  comments the `FEATURE-OFF` block and uncomments the `FEATURE-ON`
  block, disable does the inverse. Without the `FEATURE-OFF` block
  the old path stays live and both run.
- **Never put a `FEATURE-ON` block after a `return`** — it becomes
  dead/unreachable once live. Put the toggle before the shared
  tail and keep `return` reachable in both states.
- **Enable runs `uv run ruff format`** on changed files, so the
  commented body must already match ruff's output for the code
  when live; otherwise enable→disable is not idempotent (a
  spurious diff appears). Notably ruff inserts a blank line
  before a comment that trails a class method, and keeps long
  calls on one line up to the configured width. Author the
  commented form to match, then verify with an enable→disable
  round-trip (`diff` the files).
- **A block whose body ends in a top-level `def`/`class`** gets
  two blank lines inserted before its `# endregion FEATURE-ON:`
  marker on enable (ruff's blank-lines-after-top-level-def/class
  rule). So the canonical shipped (disabled) form must already
  carry the matching two `#` blank-comment lines before the END
  marker; otherwise enable→disable is not a byte-identical
  fixpoint. Author it that way, or run one enable→disable to
  canonicalize the block.
- **On any SyntaxError after enable, `features.py` rolls the
  whole tree back**, so a malformed block makes the feature
  impossible to enable at all.

Verify a block with: enable → `ast.parse` the touched files →
disable → confirm no spurious `git diff`.
