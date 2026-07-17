---
name: "Guide screenshots come from real runs, cropped or composed to the caption"
description: "how to produce any guide/images/ screenshot"
type: feedback
---

# Guide screenshots come from real runs, cropped or composed to the caption

Every `guide/images/` screenshot is captured from real elements on the
running stack and framed to the exact subject named in the manifest caption
(`guide/images/README.md`, "What to capture") — never mocked, hand-drawn, or
left stale. Crop out the nav sidebar and browser chrome. When the subject
spans more than one viewport (e.g. a status header plus a timeline separated
by a JSON panel), stitch real regions from the *same* page with
`magick a.png b.png -append` rather than settling for a partial view.

Any screenshot that needs a workshop feature follows a **leave-no-trace**
cycle: enable the feature, produce the data, capture, then complete or
approve any held run and disable the feature — so only the new PNG remains
changed and the baseline other steps depend on is intact.

**Why:** the guide teaches Temporal through the real Web UI, so fake or
stale images mislead learners; a left-enabled feature or a half-finished
running workflow pollutes the clean baseline every other step assumes.

**How to apply:** follow the `capture-guide-screenshots` skill for the
mechanics — real ports via `$CASPER_PORT`, produce data with
`make simulator` (memory-hit is offline; other scenarios need a provider
key), Casper `open` → `wait` → `screenshot`, then crop/compose. The manifest
is the spec: match filenames byte-for-byte. Related: [[project_casper_port_remap]].
