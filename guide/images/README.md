# Guide screenshots

This folder holds the screenshots referenced by the learner guide. They
are captured separately; until a file is added, the guide shows the image
caption in its place.

Add each image with the exact filename the guide references, so the links
resolve. Expected files, by step:

| File                              | Step                                    | What to capture                                                     |
| --------------------------------- | --------------------------------------- | ------------------------------------------------------------------- |
| `00-architecture.png`             | [00](../00-application-overview.md)     | Component topology with the gateway as the single entry point       |
| `01-make-dev-banner.png`          | [01](../01-getting-started.md)          | The `make dev` banner listing reachable URLs                        |
| `01-webui-workflow-tree.png`      | [01](../01-getting-started.md)          | Coordinator + two agent child workflows in the Web UI               |
| `02-event-history-memory-hit.png` | [02](../02-durable-agents.md)           | A memory-hit coordinator's Event History                            |
| `03-awaiting-approval.png`        | [03](../03-human-approval-signal.md)    | A coordinator paused, awaiting a human decision                     |
| `04-durable-timer.png`            | [04](../04-approval-timeout.md)         | A durable Timer event in Event History                              |
| `05-non-retryable-failure.png`    | [05](../05-non-retryable-validation.md) | `apply_correction` failing on attempt 1, no retries                 |
| `06-retry-attempts.png`           | [06](../06-retry-alerting.md)           | `apply_correction` climbing through retry attempts, then succeeding |
| `07-heartbeat-settlement.png`     | [07](../07-settlement-confirmation.md)  | The heartbeating `confirm_settlement` activity                      |
| `08-search-attribute-filter.png`  | [08](../08-search-attributes.md)        | Filtering executions by the `corridor` Search Attribute             |
| `09-ciphertext.png`               | [09](../09-payload-encryption.md)       | Encrypted (ciphertext) payloads in Event History                    |
| `09-decoded.png`                  | [09](../09-payload-encryption.md)       | The same payloads decoded via the codec                             |
| `10-entity-workflow.png`          | [10](../10-memory-workflow.md)          | The `corridor-memory` Entity Workflow in the `memory` namespace     |
| `11-metrics-endpoint.png`         | [11](../11-observability.md)            | `/metrics` showing `temporal_*` and `corridor_*` series             |

## Conventions

- Use PNG, cropped to the relevant region, at a legible resolution.
- Redact any real keys or tokens before capturing.
- Keep the filenames exactly as above — they are hard-coded in the guide.
