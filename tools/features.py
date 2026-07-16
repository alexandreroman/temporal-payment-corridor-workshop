"""Toggle the workshop's commented feature blocks on or off by name.

Feature blocks let the full application ship up front while individual
capabilities stay dormant until a learner enables them. A block is delimited
by VS Code folding-region marker comments:

    # region FEATURE-ON: <name>
    # <commented-out code>
    # endregion FEATURE-ON: <name>

Enabling a FEATURE-ON region uncomments its body (the code that goes live when
the feature is on); disabling re-comments it. An optional inverse pairs with
it:

    # region FEATURE-OFF: <name>
    <live starting-point code>
    # endregion FEATURE-OFF: <name>

which is the base code active while the feature is off: commented out on enable
and restored on disable, so a feature that *replaces* live code swaps cleanly
both ways.

VS Code recognizes ``# region`` / ``# endregion`` as folding markers, so a
learner sees the base application with every feature block folded away and
expands a region to study it.

Design note: parsing is deliberately line-based over the marker grammar, not a
Python parse, so it works on commented code that is not (yet) valid Python.
See the Temporal workshop convention in CLAUDE.md.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Marker grammar. `FEATURE-ON` and `FEATURE-OFF` diverge at ON vs OFF, so
# neither is a prefix of the other and alternation order does not matter.
MARKER_RE = re.compile(
    r"^(?P<indent>[ \t]*)# (?P<end>end)?region "
    r"(?P<kind>FEATURE-ON|FEATURE-OFF): (?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)[ \t]*$"
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
        kind = "default" if m["kind"] == "FEATURE-OFF" else "feature"
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

    A feature is enabled when every FEATURE-ON region is live and every
    FEATURE-OFF region is commented; disabled when the inverse holds;
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

    FEATURE-ON regions follow ``enable``; FEATURE-OFF regions are the inverse.
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
    originals: dict[Path, str] = {}  # pre-change text, for rollback
    new_texts: dict[Path, str] = {}  # post-change text, for validation
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
            originals[path] = text
            new_texts[path] = new
            path.write_text(new, encoding="utf-8")

    if dry_run or not changed:
        return changed

    # Validate every rewritten file parses as Python. A feature body may be
    # prose that only looks like code once uncommented; if any file no longer
    # compiles, roll the whole tree back so no file is left corrupted.
    for path in changed:
        try:
            compile(new_texts[path], str(path), "exec")
        except SyntaxError as exc:
            for restore_path in changed:
                restore_path.write_text(originals[restore_path], encoding="utf-8")
            raise MalformedError(
                f"feature '{name}': enabling it produced invalid Python in "
                f"{path}: {exc}"
            ) from exc

    if do_format:
        result = subprocess.run(
            ["uv", "run", "ruff", "format", *(str(p) for p in changed)], check=False
        )
        if result.returncode != 0:
            print(f"warning: ruff format exited {result.returncode}", file=sys.stderr)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="features", description="Toggle workshop feature blocks by name."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list every feature and its state")
    for cmd in ("status", "diff", "enable", "disable"):
        p = sub.add_parser(cmd)
        p.add_argument("name")
        if cmd in ("enable", "disable"):
            p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = Path.cwd()
    try:
        features = collect(root)
    except MalformedError as exc:
        print(f"malformed feature markers: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "list":
        for name in sorted(features):
            state = feature_state([r for _, r in features[name]])
            print(f"{state:<12} {name}")
        return 0

    if args.name not in features:
        known = ", ".join(sorted(features)) or "(none)"
        print(f"unknown feature '{args.name}'. Known: {known}", file=sys.stderr)
        return 2

    if args.cmd == "status":
        for path, r in features[args.name]:
            print(f"{region_state(r):<9} {r.kind:<8} {path}:{r.start + 1}-{r.end + 1}")
        return 0

    if args.cmd == "diff":
        sys.stdout.write(feature_diff(root, args.name))
        return 0

    enable = args.cmd == "enable"
    changed = set_feature(
        root,
        args.name,
        enable,
        dry_run=args.dry_run,
        do_format=os.environ.get("FEATURES_NO_FORMAT") != "1",
    )
    verb = "enable" if enable else "disable"
    if not changed:
        print(f"'{args.name}' already {verb}d; nothing to do.")
    elif not args.dry_run:
        joined = ", ".join(str(p) for p in changed)
        print(f"{verb}d '{args.name}' in {len(changed)} file(s): {joined}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
