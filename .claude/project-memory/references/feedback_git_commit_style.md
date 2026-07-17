---
name: "Git commit messages: imperative verb-first"
description: "Commit subjects start with a capitalized imperative verb (≤50 chars); no prefix at all — neither conventional-commit types nor scope prefixes like webui:"
type: feedback
---

# Git commit messages: imperative verb-first

Commit subject lines start with a **capitalized imperative verb**,
stay ≤ 50 characters, and carry no trailing period. Match the
repository's existing history — e.g. "Add versioned ruff pre-commit
hook", "Simplify config". Explain the *why* in the body, wrapped at
72 columns (see the general-rules skill `references/git.md`).

Do **not** prefix the subject with anything. This means no
conventional-commit types (`feat(...)`, `fix:`, `refactor:`,
`docs:`) **and** no scope/area prefixes such as `webui:`,
`webui+api:`, or `api:`. The subject is just the verb + action.

**Why:** the repo's commit history is uniformly imperative and
prefix-free; consistency keeps `git log` readable.

**How to apply:** write subjects like "Parse feature marker
regions", "Add make targets for feature toggling", "Rename STEP
markers to FEATURE". When writing implementation plans, use this
style in every `git commit -m` example, and pass it as a binding
constraint to implementer subagents.
