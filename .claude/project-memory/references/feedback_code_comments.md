---
name: "Code must be abundantly commented, with sources"
description: "All code carries thorough comments explaining important choices, each with a source link"
type: feedback
---

# Code must be abundantly commented, with sources

All code in this repository is abundantly commented. Comments
explain the important and non-obvious choices — especially
production-grade / durability decisions — and each such comment
cites a **source** (e.g. a Temporal docs link) backing the choice.

**Why:** this is workshop material and attendees learn by
*reading* the code, not writing it. The commented code is the
primary teaching surface; the baseline is production-robust by
default (idempotent activities, resilient fan-out, determinism)
and the comments explain why, with authoritative references.

**How to apply:** when writing or modifying code here, add
thorough explanatory comments for any non-trivial production
choice and include a source URL. Prefer clarity for a learner over
terseness. Pairs with [[project_workshop_audience]].
