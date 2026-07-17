---
name: "search-attributes status lifecycle is terminal-valued"
description: "The status SA must publish a terminal value before every coordinator return; SA-enabled tests must register all three keys"
type: project
---

# search-attributes status lifecycle is terminal-valued

The `status` Search Attribute follows the correction lifecycle
`"processing" -> "awaiting-approval" -> "applied"/"held"`. Because a
Temporal execution freezes its Search Attributes at close,
`PaymentCorrectionCoordinator.run` must publish a **terminal** value via
`_set_status(...)` before every terminal return — `"applied"` on the
apply path, `"held"` on the no-proposal / review / reject / timeout paths.
Otherwise a completed workflow lingers as `"processing"` in Visibility
(Temporal Web UI, `temporal workflow list`, SDK). `_set_status` is a no-op
when the feature is off, so these calls are safe in every toggle
combination and do not change history when disabled. In the
`human-approval-signal` block the `finally` resets only the client-side
flags (`_awaiting`, `_review`); the `"processing"` reset lives on the
approved-resume path so it never clobbers a terminal `"held"`.

Any coordinator test that enables `search-attributes` and passes
`search_attributes=[...]` to `WorkflowEnvironment.start_local` must
register **all three** keys — `corridor`, `anomalyType`, **and**
`status`. Registering only the first two makes the `status` upsert fail
and the workflow time out.

**Why:** the `status` SA is the server-side, filterable view of a
correction's lifecycle; a completed run tagged `"processing"` is wrong and
breaks status-based Visibility queries. See [[project_search_attributes_scope]].

**How to apply:** when adding a terminal return to the coordinator, pair
it with `_set_status("applied")` or `_set_status("held")`. When writing or
copying an SA-aware coordinator test, register the `status` key alongside
`corridor`/`anomalyType`.
