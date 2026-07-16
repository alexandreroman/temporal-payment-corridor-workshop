---
name: "Default to subagent-driven implementation"
description: "Prefer subagent-driven development for executing implementation plans"
type: feedback
---

# Default to subagent-driven implementation

When executing an implementation plan in this project, default to
**subagent-driven development** (a fresh subagent per task with
review between tasks) rather than inline execution — unless asked
otherwise for a specific task.

**Why:** the user prefers the tighter task-by-task review loop and
isolation that subagent-driven execution gives.

**How to apply:** after a plan is approved, proceed with the
`superpowers:subagent-driven-development` skill by default; still
route source edits through the `skillbox:code-writer` agent per
the project rule. Only fall back to inline execution when the user
requests it.
