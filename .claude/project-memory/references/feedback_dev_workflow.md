---
name: "Dev workflow: hot reload and HTML preview"
description: "Run via hot-reload make targets; preview HTML pages with Casper Browser when available"
type: feedback
---

# Dev workflow: hot reload and HTML preview

Run the app through the hot-reload make targets rather than invoking
commands by hand: `make dev` runs the whole hot-reload dev stack —
Temporal and the gateway in containers, plus the payments worker, its
HTTP API, and the corridor memory service on the host with hot reload.
The Web UI is static and served by the gateway, so a frontend edit is
seen by simply refreshing the browser — there is no reload process for
it.

To render or preview HTML pages, prefer Casper Browser when available.
Its own skill defines how to drive it — do not hard-code commands here.

**Why:** hot reload keeps the edit→see loop tight without manual
restarts; Casper Browser is the in-workspace way to actually render a
page and confirm a UI change instead of asking the user to eyeball it.

**How to apply:** when starting or iterating on the app, use the make
targets; after a frontend edit, render the page in Casper Browser and
confirm it before declaring the change done. Fall back to sharing the
URL when Casper is not available.
