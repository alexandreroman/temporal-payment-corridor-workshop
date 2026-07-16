---
name: "NOTE: marker flags learner-attention comments"
description: "Use a literal NOTE: prefix to mark the high-value comments a learner should study"
type: feedback
---

# NOTE: marker flags learner-attention comments

Source comments use a literal `NOTE: ` prefix to flag the
passages a learner should slow down and study: non-obvious
durability / determinism / idempotency decisions,
Temporal-concept explanations, and genuine gotchas. Use a
**single** marker — no NOTE/WHY/GOTCHA taxonomy. Applied across
live baseline code AND FEATURE-block prose (a double-hash prose
line becomes `# # NOTE: ...`, keeping NOTE after the second
hash). Comments stay English.

**Why:** this is workshop material where attendees learn by
*reading* the abundantly-commented code. The comments are already
dense, so a consistent marker directs attention to the genuinely
non-obvious teaching moments instead of leaving every comment
equally weighted.

**How to apply:** when adding or reviewing comments, prefix only
the truly non-obvious teaching moments with `NOTE: ` — not every
comment. Insert `NOTE: ` immediately after the leading hash (after
the second hash for `# #` FEATURE prose); change nothing else on
the line. Keep code ≤120 columns. If a NOTE lands in a FEATURE
block, verify the enable→disable round-trip stays idempotent.
Pairs with [[feedback_code_comments]] and
[[project_workshop_audience]]; FEATURE-block rules in
[[reference_feature_block_authoring]].
