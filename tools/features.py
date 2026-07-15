"""Toggle the workshop's commented feature blocks on or off by name.

Feature blocks let the full application ship up front while individual
capabilities stay dormant until a learner enables them. A block is delimited
by marker comments:

    # --- FEATURE: <name> ---
    # <commented-out code>
    # --- END FEATURE: <name> ---

Enabling a FEATURE region uncomments its body; disabling re-comments it. An
optional inverse pairs with it:

    # --- FEATURE-DEFAULT: <name> ---
    <live starting-point code>
    # --- END FEATURE-DEFAULT: <name> ---

which is commented out on enable and restored on disable, so a feature that
*replaces* live code swaps cleanly both ways.

Design note: parsing is deliberately line-based over the marker grammar, not a
Python parse, so it works on commented code that is not (yet) valid Python.
See the Temporal workshop convention in CLAUDE.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Marker grammar. `FEATURE-DEFAULT` must come before `FEATURE` in the
# alternation so the longer token wins.
MARKER_RE = re.compile(
    r"^(?P<indent>[ \t]*)# --- (?P<end>END )?"
    r"(?P<kind>FEATURE-DEFAULT|FEATURE): (?P<name>[a-z0-9][a-z0-9-]*) ---[ \t]*$"
)


class MalformedError(Exception):
    """Raised when feature markers are structurally invalid."""


@dataclass
class Region:
    """One marker-delimited region in a single file."""

    name: str
    kind: str  # "feature" or "default"
    indent: str
    start: int  # index of the start marker line
    end: int  # index of the end marker line
    body: list[str]  # lines strictly between the markers


def parse_regions(text: str) -> list[Region]:
    """Parse every feature region in ``text``.

    Raises ``MalformedError`` on an unmatched or mismatched marker.
    """
    lines = text.split("\n")
    regions: list[Region] = []
    open_stack: list[tuple[str, str, str, int]] = []  # (kind, name, indent, start)
    for i, line in enumerate(lines):
        m = MARKER_RE.match(line)
        if not m:
            continue
        kind = "default" if m["kind"] == "FEATURE-DEFAULT" else "feature"
        name = m["name"]
        if m["end"]:
            if not open_stack:
                raise MalformedError(f"line {i + 1}: END for '{name}' without a start")
            okind, oname, oindent, ostart = open_stack.pop()
            if (okind, oname) != (kind, name):
                raise MalformedError(
                    f"line {i + 1}: END '{name}' does not match open '{oname}'"
                )
            regions.append(
                Region(name, kind, oindent, ostart, i, lines[ostart + 1 : i])
            )
        else:
            open_stack.append((kind, name, m["indent"], i))
    if open_stack:
        _, oname, _, ostart = open_stack[-1]
        raise MalformedError(f"line {ostart + 1}: region '{oname}' is never closed")
    return regions
