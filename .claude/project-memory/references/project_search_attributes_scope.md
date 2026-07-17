---
name: "search-attributes feature is tagging-only"
description: "The search-attributes feature only upserts SA in the workflow; it must not rewire the API or Web UI listing"
type: project
---

# search-attributes feature is tagging-only

The `search-attributes` feature's scope is limited to **tagging
workflows** — it upserts the `corridor` / `anomalyType` / `status` search
attributes in the coordinator (`payments/workflows.py`) and nothing more.
It deliberately does **not** touch `payments/api.py` or the Web UI: the
listing and detail endpoints always read each correction directly via the
`describe_anomaly` query, so the payment context shown on every row
(amount, beneficiary, received `details`) survives whether or not the
feature is enabled.

Fleet-wide filtering by corridor / anomaly type / status is an
operator-facing concern, demonstrated through the Temporal CLI
(`temporal workflow list --query "..."`) and the Temporal Web UI — not
through the payments API. An earlier design swapped the API listing to a
server-side Visibility query (the "kill N+1" angle); it was dropped
because removing `describe_anomaly` broke the Web UI's payment context.

**Why:** the Web UI must keep showing the payment context in every feature
combination; Search Attributes are additive visibility, not an API rewrite.

**How to apply:** keep `describe_anomaly` un-gated (always available) in
both `workflows.py` and `api.py`. When extending Search Attributes, add
keys and the upsert in the workflow only — never reintroduce
`search-attributes` FEATURE regions in `api.py`.
