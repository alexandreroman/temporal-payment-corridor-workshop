---
name: "Regenerating the replay fixture via the temporal CLI"
description: "make capture-history captures a completed memory-hit run through the temporal CLI + jq (two-step WORKFLOW_ID flow), no standalone memory service"
type: reference
---

# Regenerating the replay fixture via the temporal CLI

`make capture-history WORKFLOW_ID=correction-pmt-XXXX` regenerates
`payments/testdata/coordinator-history.json` from an already-completed
workflow: it runs `temporal workflow show --namespace payments -o json` and
reshapes the output with `jq` into `{workflow_id, history}`. It captures a run
that happened on the live stack — it does NOT start its own worker or memory
service.

**Why:** the whole dev stack (coordinator worker + corridor-memory service) is
already running under `make dev`, so capturing from a real `make simulator`
run removes the old standalone-capture footgun (a separately started memory
service on the wrong port yielding a broken `applied:false` fixture).
`temporal workflow show -o json` emits `{"events":[...]}`, which
`temporalio.client.WorkflowHistory.from_json` accepts natively as the
`history` value (enum fixup + `ignore_unknown_fields`), so no Python reshaping
is needed. The fixture format stays `{"workflow_id": <str>, "history":
{"events":[...]}}` and `payments/test_replay.py` is unchanged.

**How to access:** with `make dev` up, run `make simulator` (default
`memory-hit` scenario: seeded `US->IN`/`WRONG_BIC`, guaranteed memory hit,
zero LLM calls, closes in under a second), note the printed
`workflow: correction-pmt-XXXX` id, then
`make capture-history WORKFLOW_ID=correction-pmt-XXXX`. Needs the `temporal`
CLI and `jq` on PATH. Confirm the fixture is `applied:true` (`proposed_value`
`HDFCINBBXXX`), then `uv run pytest payments/test_replay.py`. See
[[project_domain_model_simplified]] for the seeded pattern
and [[project_casper_port_remap]] for the port remap mechanism.
