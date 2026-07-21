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

Not every figure is a screenshot. Two subjects are **not** captured as PNGs:
the component-topology diagram in step 00 is an inline Mermaid `graph`
(themeable, version-controlled — no `00-architecture.png`), and any CLI/text
output such as the `/metrics` scrape in step 11 is a fenced Markdown code
block, not a screenshot. When adding such a text block, only use real
`corridor_*` metric base names — `tools/test_guide.py` asserts every
`corridor_*` token in the guide exists verbatim in source, so Prometheus
suffixes like `_bucket`/`_sum`/`_count` (absent from source) break the build.

App-state PNGs cover each distinct outcome pill: applied (`01-app-homepage`),
awaiting-approval (`03-approval-panel`), applied-after-approval
(`03-app-applied`), held-after-timeout (`04-app-held`), failed
(`05-app-failed`). Every finished PNG is framed as a rounded dark card
(pad `#0d1117` → cut transparent corners → stroke `#374151`, 24px, once each).

Frame tight — **no wide empty space** in the final image. The app card is a
wide, full-width container: its status pill is pinned to the card's right
edge while row content stays left, so a screenshot taken at a wide viewport
leaves a large empty right region. Render the app at a **narrower viewport**
so content fills the frame: `casper browser screenshot --url <app> --width
<W> --height <H>` renders off-screen at that CSS width independent of the
panel. Roughly `--width ~1040` for the two-column approval panel (keeps both
columns side by side and full) and `~720` for the single-row homepage; then
crop to the card bounds. Read the crop back and confirm the subject fills it.

**Why:** the guide teaches Temporal through the real Web UI, so fake or
stale images mislead learners; a left-enabled feature or a half-finished
running workflow pollutes the clean baseline every other step assumes; a
diagram or CLI listing reads better as live Markdown than a static image.

**How to apply:** follow the `capture-guide-screenshots` skill for the
mechanics — real ports via `$CASPER_PORT`, produce data with
`make simulator` (memory-hit is offline; other scenarios need a provider
key), Casper `open` → `wait` → `screenshot`, then crop/compose. The manifest
is the spec: match filenames byte-for-byte. Related: [[project_casper_port_remap]].
