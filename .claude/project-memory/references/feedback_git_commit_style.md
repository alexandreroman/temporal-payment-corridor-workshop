---
name: "Git commit messages: imperative verb-first"
description: "Commit subjects start with a capitalized imperative verb; no conventional-commit type prefix"
type: feedback
---

# Git commit messages: imperative verb-first

Commit subject lines start with a **capitalized imperative verb**
and no type prefix. Match the repository's existing history —
e.g. "Add versioned ruff pre-commit hook", "Simplify config".

Do **not** use conventional-commit prefixes like `feat(...)`,
`fix:`, `refactor:`, `docs:`.

**Why:** the repo's commit history is uniformly imperative and
prefix-free; consistency keeps `git log` readable.

**How to apply:** write subjects like "Parse feature marker
regions", "Add make targets for feature toggling", "Rename STEP
markers to FEATURE". When writing implementation plans, use this
style in every `git commit -m` example, and pass it as a binding
constraint to implementer subagents.
