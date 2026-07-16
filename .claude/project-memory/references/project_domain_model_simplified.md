---
name: "Transfer domain model is intentionally simplified"
description: "The payment/transfer domain is deliberately simplified for the workshop; each anomaly targets a single field"
type: project
---

# Transfer domain model is intentionally simplified

The payment/transfer domain model is deliberately simplified: each
`PaymentAnomaly` targets a single field, and the seeded corridor-memory
pattern is `US->IN` / `WRONG_BIC`, correcting the `bic` field to the
realistic Indian bank BIC `HDFCINBBXXX`. India uses SWIFT/BIC (plus an
account number and branch IFSC) for inbound international transfers and
does **not** use IBAN at all — so the anomaly type is `WRONG_BIC`
(`wrong_bic`), never a wrong IBAN.

**Why:** the workshop teaches durable execution with Temporal, not
payments compliance. A realistic inbound USD→INR transfer would carry
far more than one field — beneficiary account number, SWIFT/BIC, branch
IFSC, an RBI/FEMA purpose code, and often a correspondent bank — but
modelling all of that would bury the durable-workflow lesson. Keeping one
malformed field per anomaly keeps the correction logic easy to follow.

**How to apply:** when adding or adjusting anomalies and corrections, keep
the single-field shape; a `WRONG_BIC` correction produces a valid BIC, not
an IBAN. If you enrich `PaymentAnomaly.details`, do it only to make a
scenario read realistically, not to model full remittance compliance. This
simplification is also documented for learners in `README.md` via a
`> [!NOTE]` callout. See [[implementation-status]] for the memory-miss demo
that exercises the LLM path instead of this seeded hit.
