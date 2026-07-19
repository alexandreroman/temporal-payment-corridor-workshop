---
name: "Crash & resume demo lives in guide step 02"
description: "How the make dev Ctrl-C crash demo works and why memory-miss is required"
type: reference
---

# Crash & resume demo lives in guide step 02

`guide/02-durable-agents.md` has a `## Live demo: crash & resume` section
(baseline, no feature) that stages a worker crash and durable recovery:
`make simulator SCENARIO=memory-miss` → Ctrl-C the terminal running
`make dev` → `make dev` again → the same coordinator resumes and reaches
Completed.

The recipe relies on two verified operational facts. First, `make dev`
runs Temporal + codec + gateway as detached containers and the worker +
API + memory as host processes; Ctrl-C sends SIGINT only to the host
process group, so the Temporal server (and all durable workflow state)
survives the crash. Second, the demo must use `memory-miss`, not the
default `memory-hit`: the offline happy path finishes in well under a
second, whereas `memory-miss` runs the LLM `agent__*__model_request`
activity, which leaves a ~20–30 s window to interrupt. On a real run the
child's model activity showed a multi-second gap between `Scheduled` and
`Started` spanning the outage — the pending activity waited durably in the
task queue with no worker, then the restarted worker drained it.

**Why:** this is the workshop's most compelling live moment; a future
facilitator page or another crash demo can reuse the exact same mechanism
instead of rediscovering it.

**How to access:** read the section in `guide/02-durable-agents.md`;
requires a provider API key (for the LLM activity) and a clean baseline
(`make feature-reset`). See [[feedback_dev_workflow]] and
[[project_casper_port_remap]].
