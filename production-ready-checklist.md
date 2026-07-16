# Production-Ready Checklist

A one-page checklist to run against Temporal application code before
calling it production-ready. Each section links to the relevant Temporal
documentation for further reading.

## Correctness

Docs: https://docs.temporal.io/activities#idempotency

- [ ] Activities are idempotent: key derives from a stable id, not a hash.
- [ ] Failures are classified via `ApplicationError(non_retryable=True)`.
- [ ] Workflow code stays deterministic: `workflow.now`/`sleep`, no
      wall-clock, randomness, or I/O.

## Resilience

Docs: https://docs.temporal.io/encyclopedia/retry-policies

- [ ] Every activity and child workflow has a timeout and a tuned
      `RetryPolicy`.
- [ ] Fan-out uses `gather(return_exceptions=True)` to degrade, not fail.

## Data

Docs: https://docs.temporal.io/workflow-execution/limits,
https://docs.temporal.io/production-deployment/data-encryption

- [ ] Payloads and event history stay under the platform's size limits.
- [ ] PII crossing the boundary is encrypted via a `PayloadCodec`, paired
      with a codec server for the UI.
- [ ] The codec server is authenticated (mTLS or a bearer token) and
      TLS-terminated: otherwise it is an unauthenticated decryption oracle
      that lets anyone who can reach it decrypt any payload (the reference
      codec server requires a bearer token).

## Observability

Docs: https://docs.temporal.io/develop/python/observability

- [ ] Logging goes through `workflow.logger`/`activity.logger`, never
      `print`.
- [ ] SDK and custom metrics are exported to a monitoring stack.
- [ ] Search attributes let the fleet be queried by business dimension.

## Testing

Docs: https://docs.temporal.io/develop/python/testing-suite

- [ ] Failure paths are tested: retries exhausted, worker restart,
      cancellation.
- [ ] A replay test replays captured history through `Replayer` to
      catch determinism regressions.
- [ ] The model/LLM is mocked in agent tests: no network calls.
