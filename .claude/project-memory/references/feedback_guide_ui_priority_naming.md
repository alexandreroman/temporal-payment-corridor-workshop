---
name: "Guide: app-first for interactions, explicit UI naming"
description: "In the guide, interact via the app; name Temporal vs app UIs explicitly."
type: feedback
---

# Guide: app-first for interactions, explicit UI naming

When a guide step involves *interacting* with a correction, lead with the
**app** (the static Web UI served at the gateway root) as the primary path;
keep the Temporal equivalent only when it teaches a Temporal concept. Name
the surfaces explicitly: use **"Temporal Web UI"** (or just **"Temporal"** to
avoid repetition, e.g. "open the coordinator in Temporal") for Temporal's UI,
and call the app's own UI **"the app"** — never a bare "Web UI".

**Why:** The app's only interactive surface is Approve / Reject, so that is
where an operator acts; a bare "Web UI" is ambiguous between the app and
Temporal's own UI and hid which surface a step meant.

**How to apply:**
- Approvals: lead with the app's Approve / Reject buttons; then show the raw
  `temporal workflow signal` CLI as the pedagogical "it's just a Signal"
  equivalent. Drop redundant curl-to-API approval variants.
- Leave on their real surface what the app cannot do: submitting an anomaly
  is the simulator (`make simulator`) only; cancelling a workflow is Temporal
  only.
- Add an app screenshot where the app reflects the **business outcome**
  (statuses `applied` / `failed` / `awaiting-approval`, the approval panel);
  use Temporal or `/metrics` captures for durable-execution internals.

Related: [[feedback_guide_screenshots]], [[project_gateway_topology]].
