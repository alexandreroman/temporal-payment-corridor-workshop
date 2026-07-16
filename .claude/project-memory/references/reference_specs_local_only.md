---
name: "Design specs are intentionally not version-controlled"
description: "docs/ (design specs) is gitignored on purpose; specs stay local, not a mistake"
type: reference
---

# Design specs are intentionally not version-controlled

The design / spec documents live under `docs/` (e.g.
`docs/superpowers/specs/*.md`) and are **deliberately excluded from
version control**. `.gitignore` ignores `docs/` with the note
"Local design docs / specs (never commit)". Their absence from
`git status` and from commits is **expected and normal**, not an
oversight.

**Why:** specs are working design artifacts kept local to the
author's machine. Only the application code, tests, tracked docs
(e.g. `README.md`), and project memory are under configuration
management.

**How to access:** read the files directly on disk under
`docs/superpowers/specs/`. Do not `git add -f` them or otherwise
try to "fix" their untracked state.
