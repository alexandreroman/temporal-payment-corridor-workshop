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

**Not every guide figure is a screenshot.** Two subjects are authored as live
Markdown, not PNGs, and are deliberately *absent* from the manifest: the
component-topology diagram in step `00` is an inline **Mermaid `graph`**, and
CLI/text output (the `/metrics` scrape in step `11`) is a fenced **Markdown
code block**. Do not try to capture these, and never add manifest rows for
them. When editing such a text block, use only real `corridor_*` metric
*base* names — `test_guide.py` asserts every `corridor_*` token in the guide
appears verbatim in source, so Prometheus suffixes (`_bucket`, `_sum`,
`_count`) that only exist at scrape time break the build.

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
   Many shots need a feature enabled first (`make feature-enable NAME=<f>`)
   and some need a hand fault-switch flipped — see "Feature-gated and
   fault-switch shots" below. For `payload-encryption`, `.env` must carry
   `CODEC_ENCRYPTION_KEY` (copy it from `.env.example`); without it the worker
   and API refuse to start.

3. **Locate the workflow / runId.** List with the CLI inside the Temporal
   container, or grab the runId from the UI:
   `docker exec <temporal-container> temporal workflow list --namespace payments --address localhost:7233`.
   The coordinator is `PaymentCorrectionCoordinator` (`correction-<id>`);
   its children are `InstructionAgentWorkflow` (`…-instruction`) and
   `ComplianceAgentWorkflow` (`…-compliance`).

4. **Navigate to the exact view the caption names.** Examples: the
   **Relationships** tab of a coordinator renders the coordinator + two
   child-workflow tree; **Event History** for event-level captures;
   **Workflows** list filtered by a Search Attribute for filter captures. In
   Event History, the **Compact** view collapses a run to its meaningful
   units (best for the memory-hit shape: two child workflows + one activity),
   while the **All** view shows every raw event (needed to frame a specific
   `Timer Started` or `Activity Task` event). A still-running workflow's live
   state — a retrying or heartbeating activity — lives under **Pending
   Activities**, not Event History (see "Transient live states").

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
- Prefer clicking by **text/selector** over pixel coordinates. The screenshot
  is a 2× (retina) raster while `eval` works in CSS pixels, so a click via
  `document.elementFromPoint(x,y)` needs the screenshot coordinate **halved**.
- After changing UI state that affects fetched data (e.g. the codec setting),
  the already-rendered panels are cached — **reload** (`open` the URL again)
  so payloads re-fetch, then re-screenshot.

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

Every guide image gets a **rounded card frame** as its last transformation
— after cropping and after any compose/stack step, on the final
`guide/images/<name>.png`. Three steps: pad, cut the corners, stroke the
border. Radius **24 px**, padding **24 px**:

1. **Pad the image** — a dark-card matte gives the content breathing room
   inside the border (so the stroke doesn't hug the screenshot). The
   screenshots are dark, so a near-black matte blends into the content
   edge:

   ```bash
   magick guide/images/<name>.png -bordercolor '#0d1117' -border 24 guide/images/<name>.png
   ```

2. **Cut the corners** — round the padded canvas, making the corners
   transparent (the PNGs carry an alpha channel):

   ```bash
   magick guide/images/<name>.png \
     \( +clone -alpha extract \
        -draw "fill black polygon 0,0 0,24 24,0 fill white circle 24,24 24,0" \
        \( +clone -flip \) -compose Multiply -composite \
        \( +clone -flop \) -compose Multiply -composite \) \
     -alpha off -compose CopyOpacity -composite guide/images/<name>.png
   ```

3. **Stroke a rounded border** — the guide is plain Markdown viewed on
   **either** a light *or* a dark background (GitHub theme, VS Code
   preview). On a dark background the transparent corners reveal dark ≈ the
   matte, so the rounding is invisible without an outline. A thin dark-gray
   border follows the arc and reads on both:

   ```bash
   # Two $(...) captures, not `read W H < <(identify …)`: identify emits no
   # trailing newline, so `read` returns non-zero and aborts a `set -e` script.
   W=$(magick identify -format "%w" guide/images/<name>.png)
   H=$(magick identify -format "%h" guide/images/<name>.png)
   magick guide/images/<name>.png -fill none -stroke '#374151' -strokewidth 2 \
     -draw "roundrectangle 1,1 $((W-2)),$((H-2)) 24,24" guide/images/<name>.png
   ```

   These three steps recur on every capture, so keep them in a small helper
   script (`round.sh <src> <dst>`) and call it as the last step each time.

All three steps run **in place** and are dimension-independent (steps 2–3
touch only the four corners), so they also frame an **existing** screenshot
after the fact — point them at the current file and run in order; no capture
needed. None of the steps is idempotent (re-padding grows the matte,
re-cutting deepens the corner, re-stroking double-draws), so apply each
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

## Feature-gated and fault-switch shots

Most steps after `02` need their feature on. Follow a **leave-no-trace**
cycle: `make feature-reset`, `make feature-enable NAME=<f>`, produce data,
capture, then revert — `make feature-disable NAME=<f>` (and `make
feature-reset` at the end), so only the new PNGs change and the baseline the
other steps depend on stays intact. Confirm with `git status --short` that
only `guide/images/` changed.

Two shots need a **hand fault-switch** in `payments/activities.py` — the
app's built-in learner toggles, meant to be flipped:

- `05` non-retryable: `_SIMULATE_INVALID_CORRECTION`
- `06` retry-alerting: `_SIMULATE_TRANSIENT_RAIL_OUTAGE`

Flip with `sed`, then restore so nothing is committed:

```bash
sed -i '' 's/^_SIMULATE_INVALID_CORRECTION = False/_SIMULATE_INVALID_CORRECTION = True/' payments/activities.py
# … wait ~6s for hot reload, run make simulator, capture …
sed -i '' 's/^_SIMULATE_INVALID_CORRECTION = True/_SIMULATE_INVALID_CORRECTION = False/' payments/activities.py
git checkout payments/activities.py   # belt-and-braces revert
```

**Approval shots (`03`/`04`) need a provider key** (`needs-approval`
scenario). Note the API's `status` field is the *workflow execution* status
(`running`) even while the app shows **awaiting-approval** — the held state is
signalled by `review` being non-null, so poll on that, not on `status`. The
`awaiting_approval` **Query** (Queries tab → Run Query → `true`) is the
cleanest "paused, awaiting a decision" evidence. For `04-app-held`, let the
1-minute timer elapse (auto-reject) before capturing the app row.

## Transient live states (retries, heartbeats)

Retries and heartbeats are **not** separate history events — Temporal records
one `ActivityTaskStarted` carrying the *final* attempt number, so the "climb"
is invisible in Event History. The live view is **Pending Activities** while
the workflow still runs: it shows `Attempt N of M`, the last failure, and
`Heartbeat Details`. These windows are short, so either:

- **Race it.** Fire `make simulator`, `open` the workflow immediately, then
  loop: click the Pending Activities tab and `screenshot` every ~0.4s until a
  frame catches the state (Read the frames, keep the good one).
- **Slow the cadence** so the state is easy to catch — e.g. append
  `CORRIDOR_SETTLEMENT_POLL_INTERVAL_SECONDS=2.5` to `.env`, `touch` a source
  file to trigger a reload, capture, then remove the line. (Config via env is
  the documented knob; leave `.env` as you found it.)

Crop out any stack-trace panel — it leaks the local filesystem path.

## Ciphertext vs decoded (step 09)

With `payload-encryption` on, the dev server points the Web UI at the codec,
so Event History shows **cleartext by default**. To capture the *ciphertext*
before/after pair from the same run's Input/Result panels:

- **Decoded** (`09-decoded`): the default view — capture as-is.
- **Ciphertext** (`09-ciphertext`): open the **Codec Server** modal (the
  glasses icon, top-right), choose *"Use my browser setting and ignore
  Cluster-level setting"*. Apply is disabled with an empty endpoint, so paste
  an **unreachable** endpoint (e.g. `http://127.0.0.1:9/codec`); decoding then
  fails and payloads render as `metadata.encoding` + base64 `data`. **Reload**
  the page so payloads re-fetch. Crop out the red *"Codec Server could not
  connect"* banner — frame only the Input/Result panels. Restore the modal to
  *"Use Cluster-level setting"* afterward.

Verify encryption is real (not a UI artifact) via the CLI without a codec:
`docker exec <temporal> temporal workflow show --workflow-id <wf> --namespace
payments --address localhost:7233 -o json` shows no plaintext when encrypted.

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
| Feature-gated shot | `feature-enable NAME=<f>` → data → capture → `feature-disable`/`feature-reset`; check `git status` is images-only |
| Fault-switch shot (05/06) | `sed` flip `_SIMULATE_*` in `payments/activities.py`, capture, `git checkout` to revert |
| Retry / heartbeat shot | **Pending Activities** while running (race screenshots, or slow cadence via env) — not Event History |
| Ciphertext vs decoded (09) | Codec Server modal → browser setting + unreachable endpoint → **reload** → crop out the error banner |
| Compact vs All history | Compact = run shape (memory-hit); All = a specific `Timer Started` / `Activity Task` event |
| Round corners (last step) | 24 px: pad `#0d1117` (24 px) → cut transparent corners → stroke a `#374151` border — see "Round the corners" (also frames an existing PNG) |
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
- **Forgetting to frame the corners** — pad + round + border is the last
  step on every guide image; a square-cornered PNG is unfinished. But run
  each step only **once** per file — none is idempotent.
- **Cutting corners without the border** — transparent corners vanish on a
  dark background (the screenshots are dark, and the guide is viewed on
  dark themes too). The `#374151` stroke is what makes the arc visible on
  both light and dark; do not skip it.
- **Treating every figure as a screenshot** — the step `00` topology is a
  Mermaid graph and the step `11` `/metrics` listing is a Markdown block;
  they are not PNGs and not in the manifest.
- **`read W H < <(magick identify …)` in a `set -e` helper** — `identify`
  emits no trailing newline, so `read` returns non-zero and aborts the
  script. Use two `$(…)` captures instead.
- **Capturing "decoded" when you wanted ciphertext** — the codec is on by
  default; you must set an unreachable browser endpoint *and reload* before
  the payloads render as ciphertext.
- **Hunting Event History for per-retry events** — they don't exist; the
  attempt count and last failure live in Pending Activities while running.
- **Leaving a feature or fault switch enabled** — always revert
  (`feature-disable`/`git checkout`) so the baseline other steps assume holds.
