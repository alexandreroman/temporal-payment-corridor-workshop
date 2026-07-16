---
name: "Payments component naming vs Temporal Worker primitive"
description: "In prose call the deployable component payments; reserve Worker/worker for the Temporal SDK primitive"
type: project
---

# Payments component naming vs Temporal Worker primitive

The deployable payment-correction component is named functionally
**payments**: the make target, Compose service, Temporal namespace, and
`PAYMENTS_*` env vars all use that name.

In prose, comments, and docs, refer to that component as "payments",
"the payments component/service/process", or "the payments worker" — not
generically as "the worker".

Reserve the word `Worker`/`worker` for the Temporal SDK primitive and its
identifiers. Leave these untouched: `from temporalio.worker import
Worker`, `Worker(...)`, `Replayer`, `build_worker`, the files
`payments/worker.py` and `payments/test_worker.py`, `worker.run()`,
`_run_worker`, `worker.task_queue`, any `worker` variable, and the
`workerVersion` field in `payments/testdata/coordinator-history.json`
(Temporal-generated).
