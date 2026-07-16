---
name: "Enforced format is ruff defaults (88 cols), via a whole-tree pre-commit hook"
description: "The real, enforced line length is ruff's default 88 — not the 120 CLAUDE.md mentions"
type: feedback
---

# Enforced format is ruff defaults (88 cols), via a whole-tree pre-commit hook

Code is formatted and linted with ruff at its **default** settings:
there is no `[tool.ruff]` config in `pyproject.toml` and no
`ruff.toml`, so the line length is **88**, not the 120 that
`CLAUDE.md` lists under Conventions. A `.githooks/pre-commit` hook
runs `ruff format --check .` and `ruff check .` over the **whole
tree**, so any commit fails unless the entire repository is clean —
not just the files being changed.

- **Why:** writing code (or FEATURE-block commented code) at 120
  columns produces a diff that the pre-commit hook rejects, and
  hand-wrapping to guess ruff's wrapping wastes effort. The 120 in
  `CLAUDE.md` is aspirational guidance, not the enforced rule.
- **How to apply:** let `uv run ruff format .` decide wrapping; run
  `uv run ruff format . && uv run ruff check .` before every commit
  and fix the whole tree, not just touched files. Commented FEATURE
  code must match ruff-formatted output at 88 columns too — see
  [[Authoring toggleable FEATURE blocks]].
