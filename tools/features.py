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

import difflib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

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


def _is_commented(line: str, indent: str) -> bool:
    """True if ``line`` is blank or a comment at the region's base indent."""
    if line.strip() == "":
        return True
    return line.startswith(indent) and line[len(indent) :].startswith("#")


def region_state(region: Region) -> str:
    """Return "disabled" (body commented out), "enabled" (live), or "empty"."""
    non_blank = [ln for ln in region.body if ln.strip() != ""]
    if not non_blank:
        return "empty"
    if all(_is_commented(ln, region.indent) for ln in non_blank):
        return "disabled"
    return "enabled"


def _comment(line: str, indent: str) -> str:
    if line.strip() == "":
        return indent + "#"
    return indent + "# " + line[len(indent) :]


def _uncomment(line: str, indent: str) -> str:
    if line.strip() in ("", "#"):
        return ""
    rest = line[len(indent) :]
    if rest.startswith("# "):
        return indent + rest[2:]
    if rest.startswith("#"):
        return indent + rest[1:]
    return line


def feature_state(regions: list[Region]) -> str:
    """Aggregate the state of all regions sharing a name.

    A feature is enabled when every FEATURE region is live and every
    FEATURE-DEFAULT region is commented; disabled when the inverse holds;
    otherwise the regions are out of sync ("inconsistent").
    """
    feats = [r for r in regions if r.kind == "feature"]
    defs = [r for r in regions if r.kind == "default"]
    if not feats and not defs:
        return "empty"
    is_enabled = all(region_state(r) == "enabled" for r in feats) and all(
        region_state(r) == "disabled" for r in defs
    )
    is_disabled = all(region_state(r) == "disabled" for r in feats) and all(
        region_state(r) == "enabled" for r in defs
    )
    if is_enabled and not is_disabled:
        return "enabled"
    if is_disabled and not is_enabled:
        return "disabled"
    return "inconsistent"


def set_feature_in_text(text: str, name: str, enable: bool) -> str:
    """Return ``text`` with feature ``name`` set to the requested state.

    FEATURE regions follow ``enable``; FEATURE-DEFAULT regions are the inverse.
    Bodies are transformed 1:1, so line indices stay valid; a region already in
    the target state is left untouched (idempotent).
    """
    lines = text.split("\n")
    regions = [r for r in parse_regions(text) if r.name == name]
    for r in sorted(regions, key=lambda r: r.start, reverse=True):
        want_commented = (not enable) if r.kind == "feature" else enable
        already_commented = region_state(r) == "disabled"
        if already_commented == want_commented:
            continue
        # Validate that every non-blank body line has proper indentation.
        # A line under-indented from the marker's base indent would be corrupted
        # during transformation (characters would be silently dropped).
        for body_line in r.body:
            if body_line.strip() != "" and not body_line.startswith(r.indent):
                raise MalformedError(
                    f"region '{r.name}': body line at column 0 is under-indented "
                    f"from marker's base indent {len(r.indent)}"
                )
        transform = _comment if want_commented else _uncomment
        lines[r.start + 1 : r.end] = [transform(ln, r.indent) for ln in r.body]
    return "\n".join(lines)


ROOTS: tuple[str, ...] = ("shared", "worker", "webui", "simulator")


def iter_source_files(root_dir: Path) -> list[Path]:
    """All ``.py`` files under the scanned application packages, sorted."""
    files: list[Path] = []
    for name in ROOTS:
        base = root_dir / name
        if base.is_dir():
            files.extend(sorted(base.rglob("*.py")))
    return files


def collect(root_dir: Path) -> dict[str, list[tuple[Path, Region]]]:
    """Map each feature name to its (file, region) occurrences across the repo."""
    result: dict[str, list[tuple[Path, Region]]] = {}
    for path in iter_source_files(root_dir):
        for r in parse_regions(path.read_text(encoding="utf-8")):
            result.setdefault(r.name, []).append((path, r))
    return result


def _files_with_feature(root_dir: Path, name: str) -> list[Path]:
    return [
        path
        for path in iter_source_files(root_dir)
        if any(r.name == name for r in parse_regions(path.read_text(encoding="utf-8")))
    ]


def set_feature(
    root_dir: Path,
    name: str,
    enable: bool,
    *,
    dry_run: bool,
    do_format: bool = True,
) -> list[Path]:
    """Set feature ``name`` across the repo. Returns the files that changed.

    With ``dry_run`` the planned unified diff is printed and no file is written.
    Otherwise changed files are re-formatted with ruff so uncommented code lands
    clean (see the Temporal Python style guidance).
    """
    changed: list[Path] = []
    for path in _files_with_feature(root_dir, name):
        text = path.read_text(encoding="utf-8")
        new = set_feature_in_text(text, name, enable)
        if new == text:
            continue
        changed.append(path)
        if dry_run:
            sys.stdout.writelines(
                difflib.unified_diff(
                    text.splitlines(keepends=True),
                    new.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile=str(path),
                )
            )
        else:
            path.write_text(new, encoding="utf-8")
    if changed and not dry_run and do_format:
        subprocess.run(
            ["uv", "run", "ruff", "format", *(str(p) for p in changed)], check=False
        )
    return changed


def feature_diff(root_dir: Path, name: str) -> str:
    """Return a unified diff of the disabled→enabled change ``name`` introduces."""
    out: list[str] = []
    for path in _files_with_feature(root_dir, name):
        text = path.read_text(encoding="utf-8")
        disabled = set_feature_in_text(text, name, enable=False)
        enabled = set_feature_in_text(text, name, enable=True)
        if disabled != enabled:
            out.extend(
                difflib.unified_diff(
                    disabled.splitlines(keepends=True),
                    enabled.splitlines(keepends=True),
                    fromfile=f"{path} (disabled)",
                    tofile=f"{path} (enabled)",
                )
            )
    return "".join(out)
