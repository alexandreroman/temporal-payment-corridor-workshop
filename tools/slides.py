"""Serve the reveal.js workshop decks over HTTP with caching disabled.

The decks under ``slides/`` are reveal.js presentations with relative asset
references (theme CSS, deck JS, images) and inline Mermaid diagrams. They only
render correctly when served over HTTP: opening ``index.html`` via a
``file://`` URL leaves reveal.js unable to resolve its relative assets and
blocks the fetches Mermaid relies on.

A plain ``python -m http.server`` would serve the files, but the Casper webview
(and browsers generally) cache CSS/JS aggressively, so an edit to the theme or
deck script keeps showing stale output until the cache is busted. This server
exists to send ``Cache-Control: no-store`` on every response, so a browser
refresh always reflects the latest edit.
"""

from __future__ import annotations

import argparse
import os
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Resolve the decks relative to this file, not the current working directory,
# so `make slides` works no matter where make is invoked from. tools/ sits at
# the repo root, so the slides directory is a sibling of tools/.
SLIDES_DIR = Path(__file__).resolve().parent.parent / "slides"

# Bind to loopback only. These decks are a local authoring/preview aid, never a
# public server, so there is no reason to listen on all interfaces.
HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class NoCacheHandler(SimpleHTTPRequestHandler):
    """Static file handler that forbids all client-side caching.

    ``end_headers`` is the documented extension point for injecting response
    headers before the blank line that ends the header block.
    See https://docs.python.org/3/library/http.server.html#http.server.BaseHTTPRequestHandler.end_headers
    """

    def end_headers(self) -> None:
        # NOTE: this no-store header is the whole reason this server exists
        # instead of `python -m http.server` — the Casper/webview cache is
        # aggressive enough that edited CSS/JS otherwise appears to do nothing.
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control#no-store
        self.send_header("Cache-Control", "no-store")
        # Pragma is the legacy HTTP/1.0 equivalent, harmless to send alongside.
        self.send_header("Pragma", "no-cache")
        super().end_headers()


def _session_urls(base_url: str) -> list[str]:
    """URLs for each session deck, discovered by globbing so new decks appear.

    Sessions follow the ``session-*.html`` naming convention; sorting keeps
    them in numeric order (session-1, session-2, ...).
    """
    sessions = sorted(SLIDES_DIR.glob("session-*.html"))
    return [f"{base_url}{path.name}" for path in sessions]


def _print_banner(base_url: str) -> None:
    """Print where to reach the decks, matching the Makefile banner's tone."""
    print("")
    print("Serving the workshop slides (no cache).")
    print("Open:")
    print(f"  Landing page      {base_url}")
    for url in _session_urls(base_url):
        print(f"  Session           {url}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="slides",
        description="Serve the reveal.js workshop decks over HTTP (no cache).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SLIDES_PORT", DEFAULT_PORT)),
        help="port to listen on (default: $SLIDES_PORT, then 8000)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="open the landing page in the default browser on startup",
    )
    args = parser.parse_args(argv)

    base_url = f"http://{HOST}:{args.port}/"

    # Pin the handler to the slides directory via `directory=` rather than
    # chdir-ing, so the process CWD is left untouched. partial pre-binds the
    # keyword because ThreadingHTTPServer instantiates the handler itself.
    handler = partial(NoCacheHandler, directory=str(SLIDES_DIR))
    with ThreadingHTTPServer((HOST, args.port), handler) as httpd:
        _print_banner(base_url)
        if args.open:
            webbrowser.open(base_url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            # Ctrl-C is the expected way to stop this foreground server, so
            # exit quietly instead of dumping a traceback.
            print("\nStopped serving the slides.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
