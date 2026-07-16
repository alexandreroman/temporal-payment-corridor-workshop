---
name: "retry-alerting metric is tagged with field + source"
description: "Why corridor_correction_retries_alerted is tagged field/source, not corridor/anomaly type"
type: reference
---

# retry-alerting metric is tagged with field + source

The `retry-alerting` FEATURE block in `payments/activities.py`
emits the counter `corridor_correction_retries_alerted` tagged
with `field` (proposal.field_to_fix) and `source`
(proposal.source), NOT with corridor / anomaly type.

The design spec's wording asks for "corridor / anomaly type"
tags, but `apply_correction` receives only a
`CorrectionProposal`, which does not carry `corridor` or
`anomaly_type` (those live on `PaymentAnomaly`, upstream in the
coordinator workflow). Tagging with `field` + `source` matches
exactly how the sibling `corridor_corrections_applied` and
`corridor_correction_confidence` metrics in the same activity
are tagged, keeping the metric series consistent and avoiding
threading extra data across the Temporal boundary just for a
label. An in-code `NOTE:` comment records this at the emission
site.

If corridor / anomaly-type labels are ever required, the clean
fix is to widen the activity's input (or add the labels via the
workflow's search attributes), not to reconstruct them inside
the activity.
