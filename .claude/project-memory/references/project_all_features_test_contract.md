---
name: "All-features test suite is green except the intentional replay failure"
description: "With every workshop feature enabled, the whole suite passes except test_replay, which is designed to fail on any shape-changing feature"
type: project
---

# All-features test suite is green except the intentional replay failure

With all eight workshop features enabled at once, `make check` (ruff +
pytest) is clean except for a single failure:
`payments/test_replay.py::test_coordinator_replays_captured_history`.

That replay failure is **by design**, documented in `guide/12-testing.md`:
enabling any shape-changing feature (e.g. `search-attributes`, which makes the
coordinator's first command an `upsert_search_attributes`) diverges from the
committed baseline history fixture, and the lesson is that production would use
versioning/patching instead of silently recapturing. A single committed fixture
can only match one feature configuration; the baseline is the chosen one, so
the fixture cannot be green in both baseline and all-features states.

Beyond replay, every other test is expected to pass in the baseline, in each
single-feature-from-baseline state, AND with all features on together. Several
tests carry `FEATURE-OFF`/`FEATURE-ON` forks or unconditional test-env setup so
they hold across toggle states — notably: workflow test envs register the
`status` search attribute; the payments-API stub answers the `awaiting_approval`
query with a real bool; the fake instruction agent emits a valid BIC via
`TestModel(custom_output_args=...)`; and `test_coordinator_holds`/`applies`
signal a rejection and register `confirm_settlement` respectively.

**Why:** the workshop guide runs one feature at a time from a reset baseline, so
multi-feature and even some single-feature test interactions are easy to miss;
the suite is nonetheless meant to stay green in every combination except the
intentional replay break.

**How to apply:** when verifying "all tests with all features," treat the lone
`test_replay` failure as expected, not a regression. To make replay green while
a shape-changing feature stays on, recapture the fixture from a live run
(`make simulator` + `make capture-history`, see
[[reference_capture_history_cli]]) — but that breaks the baseline replay, so it
is a deliberate trade-off, never a silent fix. See also
[[project_search_attributes_scope]] and [[project_implementation_status]].
