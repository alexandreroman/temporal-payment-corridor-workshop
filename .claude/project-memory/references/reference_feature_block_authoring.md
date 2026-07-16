---
name: "Authoring toggleable FEATURE blocks"
description: "How to write FEATURE/FEATURE-DEFAULT blocks so they enable to valid, ruff-clean Python and round-trip"
type: reference
---

# Authoring toggleable FEATURE blocks

`tools/features.py` toggles `# --- FEATURE: <name> ---` /
`# --- FEATURE-DEFAULT: <name> ---` regions. Rules learned
from fixing broken blocks:

- **Enable strips exactly one leading `# `** per body line
  (`_uncomment`). So distinguish line kinds:
  - **Code** that must go live: single-comment it
    (`# client = ...` → `client = ...`).
  - **Prose** that must stay a comment after enabling:
    double-comment it (`# # note` → `# note`).
- **A region must yield at least one live Python line** when
  uncommented, else it still reads as disabled.
- **A feature that REPLACES live code needs a paired
  `FEATURE-DEFAULT`** wrapping the starting-point code; enable
  comments the DEFAULT and uncomments the FEATURE, disable does
  the inverse. Without the DEFAULT the old path stays live and
  both run.
- **Never put a FEATURE block after a `return`** — it becomes
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
- **On any SyntaxError after enable, `features.py` rolls the
  whole tree back**, so a malformed block makes the feature
  impossible to enable at all.

Verify a block with: enable → `ast.parse` the touched files →
disable → confirm no spurious `git diff`.
