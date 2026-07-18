---
name: capture-guide-screenshots
description: Use when generating, regenerating, or updating a screenshot in guide/images/ for the learner guide — capturing the Temporal Web UI or app Web UI from a live stack with Casper, then cropping to the caption's subject. Covers finding the real (worktree-remapped) port, producing real workflow data, and the Casper capture loop (wait for the SPA to render, then screenshot).
---

# Capture guide screenshots

Produce the PNGs the learner guide references, **from real elements** on a
live stack, cropped to the subject each caption promises.

## The manifest is the spec

`guide/images/README.md` lists every expected file: its **exact filename**
(hard-coded in the guide), the step that references it, and a **"What to
capture"** column that is the subject you must frame. Read that row first —
it tells you the view and what the crop must focus on.

`make check` (`tools/test_guide.py`) enforces the two-way link: every image
referenced by a guide file must be listed in the manifest, and vice versa.
Keep filenames byte-for-byte. Do **not** add a manifest row unless you are
introducing a genuinely new screenshot.

## Find the real ports (worktree remapping)

In a Casper worktree, `make worktree-ports` writes `compose.override.yaml`
remapping the gateway off the canonical `8080`. Do not assume `8080` — it is
not mapped here. Use `$CASPER_PORT`:

- App Web UI: `http://localhost:$CASPER_PORT`
- Temporal Web UI: `http://localhost:$CASPER_PORT/temporal`
- Temporal gRPC: `$CASPER_PORT + 1`

Namespaces are `payments` (corrections + agents) and `memory`. Confirm the
real mapping any time with `cat compose.override.yaml` / `docker ps`.

## Procedure

1. **Stack up.** The user usually already ran `make dev`. Verify with
   `curl -sS -o /dev/null -w '%{http_code}' http://localhost:$CASPER_PORT/`.

2. **Produce real data.** Screenshots need a real execution. For the
   `memory-hit` path (no API key): `make simulator`. It prints the
   `payment` and `workflow` IDs. Other scenarios need a provider key — see
   step `01` of the guide. Wait for completion, e.g.
   `curl -sS http://localhost:$CASPER_PORT/api/payments/v1/anomalies/<id> | jq`.

3. **Locate the workflow / runId.** List with the CLI inside the Temporal
   container, or grab the runId from the UI:
   `docker exec <temporal-container> temporal workflow list --namespace payments --address localhost:7233`.
   The coordinator is `PaymentCorrectionCoordinator` (`correction-<id>`);
   its children are `InstructionAgentWorkflow` (`…-instruction`) and
   `ComplianceAgentWorkflow` (`…-compliance`).

4. **Navigate to the exact view the caption names.** Examples: the
   **Relationships** tab of a coordinator renders the coordinator + two
   child-workflow tree; **Event History** for event-level captures;
   **Workflows** list filtered by a Search Attribute for filter captures.

5. **Capture with Casper** (see loop below).

6. **Crop to the subject** (see cropping below).

7. **Round the corners** — the final step on every guide image (see
   rounding below).

8. **Verify.** Read the cropped PNG back and confirm it matches the
   manifest's "What to capture". PNG, cropped, corners rounded, legible;
   redact any real key or token before capturing.

## Casper capture loop

The Temporal Web UI is a client-rendered SPA, so **wait for content to
render before you screenshot** — capture the page into a real browser, wait
on a selector that only exists once the view is drawn, then screenshot:

```bash
URL="http://localhost:$CASPER_PORT/temporal/namespaces/payments/workflows/<wfid>/<runid>/relationships"
casper browser open "$URL"          # renders in the VISIBLE panel — respects the user's window size
casper browser wait "svg" --timeout 8000   # wait for the graph/content to render
casper browser screenshot --out /tmp/shot.png   # plain screenshot captures the rendered page
```

- `open` uses the **visible panel**, so it honours the window size the user
  set (they may enlarge it for a bigger capture — re-run `open` +
  `screenshot` after they do).
- `load` is a **background page** with its own viewport (useful for setup
  without disturbing the user's view).
- `casper browser eval "location.href"` / `eval "document.querySelectorAll('svg').length"`
  confirm you are on the right view with content rendered.
- To reach a tab without knowing the runId, `open` the workflow URL, then
  `eval` a click on the tab link and read its `href`:
  `casper browser eval "[...document.querySelectorAll('a')].find(e=>/Relationships/.test(e.textContent)).click()"`.

## Crop to the caption's subject

Read the full screenshot first to see the layout, then crop out the left
nav sidebar and top browser chrome so only the subject remains:

```bash
magick /tmp/shot.png -crop <W>x<H>+<X>+<Y> +repage guide/images/<exact-name>.png
```

Get `WxH+X+Y` by eyeballing the full PNG (Read it — the tool reports the
displayed→original scale factor), then **Read the crop and iterate** until
it is tight on the subject. `sips -g pixelWidth -g pixelHeight <png>` prints
dimensions. `magick`/`convert` and Python PIL are available.

## Round the corners

Every guide image gets **rounded corners** as its last transformation —
after cropping and after any compose/stack step, on the final
`guide/images/<name>.png`. Two steps, both at a **24 px** radius:

1. **Cut the corners** — make them transparent (the PNGs carry an alpha
   channel):

   ```bash
   magick guide/images/<name>.png \
     \( +clone -alpha extract \
        -draw "fill black polygon 0,0 0,24 24,0 fill white circle 24,24 24,0" \
        \( +clone -flip \) -compose Multiply -composite \
        \( +clone -flop \) -compose Multiply -composite \) \
     -alpha off -compose CopyOpacity -composite guide/images/<name>.png
   ```

2. **Stroke a rounded border** — the screenshots are dark-themed, and the
   guide is plain Markdown viewed on **either** a light *or* a dark
   background (GitHub theme, VS Code preview). On a dark background the
   transparent corners reveal dark ≈ the image's own dark edge, so the
   rounding is invisible without an outline. A thin neutral-gray border
   follows the arc and reads on both:

   ```bash
   read W H < <(magick identify -format "%w %h" guide/images/<name>.png)
   magick guide/images/<name>.png -fill none -stroke '#6b7280' -strokewidth 2 \
     -draw "roundrectangle 1,1 $((W-2)),$((H-2)) 24,24" guide/images/<name>.png
   ```

Both steps run **in place** and are dimension-independent, so they also
round an **existing** screenshot after the fact — point them at the current
file and run; no capture needed. Neither step is idempotent (re-running
step 1 deepens the corner, step 2 double-draws the stroke), so apply each
exactly once per file.

Do **not** verify the result by flattening onto white (`-background white
-flatten`) — a dark screenshot can render misleadingly. Flatten onto a
dark matte instead (`-background '#1e1e1e' -flatten`) to see it as VS Code /
GitHub-dark shows it.

## Compose when the subject spans more than one view

Sometimes the caption's subject is two regions of the same page separated by
content you don't want — e.g. "a paused coordinator **and** its timeline",
where the **Running** header and the **Timeline** are pushed apart by the
tall Input/Result JSON and never fit one viewport together. Stitch the two
real regions into one image instead of settling for either alone:

1. Screenshot the page with the first region visible; scroll (see the scroll
   trick below) so the second region is fully visible and screenshot again.
   Both come from the **same run/page** — this is cropping, not fabrication;
   you're only omitting the stuff in between.
2. Crop each region to the **same width** (same `X` and `W`) so they align.
3. Stack them: `magick top.png bottom.png -append out.png` (vertical) or
   `+append` (horizontal). On the dark UI the seam is invisible.

```bash
magick full.png    -crop 2400x288+115+237  +repage /tmp/head.png   # Running header
magick scrolled.png -crop 2400x454+115+1024 +repage /tmp/tl.png     # Timeline
magick /tmp/head.png /tmp/tl.png -append guide/images/<name>.png
```

**Scroll trick:** the Temporal page scrolls inside nested containers, not
`window`. To reveal a below-the-fold region, scroll every scrollable node:
`casper browser eval "document.querySelectorAll('*').forEach(n=>{if(n.scrollHeight>n.clientHeight+80 && /auto|scroll/.test(getComputedStyle(n).overflowY)) n.scrollTop=n.scrollHeight})"`,
then Read the screenshot to confirm the region is in frame.

## Quick reference

| Need | Do |
| --- | --- |
| Real port | `$CASPER_PORT` (gateway); Temporal UI at `/temporal`; gRPC `$CASPER_PORT+1` |
| Which subject to frame | the "What to capture" cell in `guide/images/README.md` |
| Memory-hit data, no key | `make simulator` |
| List workflows | `docker exec <temporal> temporal workflow list --namespace payments --address localhost:7233` |
| Coordinator tree view | workflow's **Relationships** tab |
| Capture | `casper browser open` → `wait "svg"` → `screenshot --out` |
| Crop | `magick in.png -crop WxH+X+Y +repage guide/images/<name>.png` |
| Subject spans two views | crop each region to the same width, `magick a.png b.png -append out.png` |
| Round corners (last step) | 24 px radius: cut transparent corners **then** stroke a `#6b7280` border — see "Round the corners" (also rounds an existing PNG) |
| Enforce filenames | `make check` (manifest two-way link) |

## Common mistakes

- **Using `8080`** — not mapped in a worktree; use `$CASPER_PORT`.
- **Screenshotting before the SPA renders** — `wait` on a view-specific
  selector first, or you capture an empty page.
- **Renaming the file** — filenames are hard-coded in the guide and checked
  against the manifest; keep them exact.
- **Capturing before data exists** — run the scenario first; an empty
  Workflows list has nothing to show.
- **Leaving the nav sidebar / browser chrome in the crop** — frame only the
  caption's subject.
- **Forgetting to round the corners** — it is the last step on every guide
  image; a square-cornered PNG is unfinished. But round each file only
  **once** — neither step is idempotent.
- **Cutting corners without the border** — transparent corners vanish on a
  dark background (the screenshots are dark, and the guide is viewed on
  dark themes too). The `#6b7280` stroke is what makes the arc visible on
  both light and dark; do not skip it.
