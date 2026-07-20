# Guide screenshots

This folder holds the screenshots referenced by the learner guide. They
are captured separately; until a file is added, the guide shows the image
caption in its place.

Add each image with the exact filename the guide references, so the links
resolve. Expected files, by step:

| File                              | Step                                    | What to capture                                                            |
| --------------------------------- | --------------------------------------- | -------------------------------------------------------------------------- |
| `00-app-homepage.png`             | [00](../00-application-overview.md)     | The app homepage: an anomalous payment repaired from memory and applied    |
| `01-app-homepage.png`             | [01](../01-getting-started.md)          | The app homepage: the first payment corrected from memory (applied)        |
| `01-webui-workflow-tree.png`      | [01](../01-getting-started.md)          | Coordinator + two agent child workflows in the Temporal Web UI             |
| `02-event-history-memory-hit.png` | [02](../02-durable-agents.md)           | A memory-hit coordinator's Event History (compact)                         |
| `03-awaiting-approval.png`        | [03](../03-human-approval-signal.md)    | A coordinator paused, its `awaiting_approval` query returning `true`       |
| `03-approval-panel.png`           | [03](../03-human-approval-signal.md)    | The app's approval panel: a compliant correction awaiting a human decision |
| `03-app-applied.png`              | [03](../03-human-approval-signal.md)    | The app homepage: the correction applied after a human approved it         |
| `04-durable-timer.png`            | [04](../04-approval-timeout.md)         | A durable Timer event in Event History                                     |
| `04-app-held.png`                 | [04](../04-approval-timeout.md)         | The app homepage: a correction held after the approval window elapsed      |
| `05-non-retryable-failure.png`    | [05](../05-non-retryable-validation.md) | `apply_correction` failing on attempt 1, no retries                        |
| `05-app-failed.png`               | [05](../05-non-retryable-validation.md) | The app homepage: a correction that failed (no valid fix applied)          |
| `06-retry-attempts.png`           | [06](../06-retry-alerting.md)           | `apply_correction` retrying (Attempt 2 of 3) with its last failure         |
| `07-heartbeat-settlement.png`     | [07](../07-settlement-confirmation.md)  | The heartbeating `confirm_settlement` activity                             |
| `08-search-attribute-filter.png`  | [08](../08-search-attributes.md)        | Filtering executions by the `corridor` Search Attribute                    |
| `09-ciphertext.png`               | [09](../09-payload-encryption.md)       | Encrypted (ciphertext) payloads in Event History                          |
| `09-decoded.png`                  | [09](../09-payload-encryption.md)       | The same payloads decoded via the codec                                    |
| `10-entity-workflow.png`          | [10](../10-memory-workflow.md)          | The `corridor-memory` Entity Workflow in the `memory` namespace            |
| `10-memory-namespace.png`         | [10](../10-memory-workflow.md)          | The `memory` namespace Workflows list, with the singleton execution        |

## Conventions

- Use PNG, cropped to the relevant region, at a legible resolution.
- Redact any real keys or tokens before capturing.
- Keep the filenames exactly as above — they are hard-coded in the guide.
- Each image is framed as a rounded dark card (see the
  `capture-guide-screenshots` skill for the exact steps).
