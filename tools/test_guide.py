"""Docs<->code contract tests: fail when the learner guide drifts from the code.

The guide under ``guide/`` teaches the app by pointing at real features, make
targets, simulator scenarios, metrics, source files, and screenshots. Any of
those can be renamed or removed in the codebase while the prose keeps naming
the old thing — a silent drift a reader only discovers mid-workshop. These
tests turn every such reference into a build-time assertion, so a rename that
forgets the guide fails ``make check`` instead.

Each test guards one kind of reference and, on failure, names the offending
file and token so the fix is obvious. The source of truth is always the code
(``tools.features``, ``simulator.scenarios``, the ``Makefile``, the source
packages), never a second hand-maintained list.

Style note: this mirrors ``tools/test_features.py`` — plain pytest functions,
repo root derived from ``__file__`` so it runs from any working directory.
"""

from __future__ import annotations

import re
from pathlib import Path

from simulator.scenarios import SCENARIOS
from tools.features import ROOTS, collect, iter_source_files

# Repo root = the directory that holds guide/, Makefile, and pyproject.toml.
# Derived from __file__ (this file lives in tools/) so the suite is CWD-agnostic.
ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guide"

# --- Reference extraction patterns -----------------------------------------

# Feature / scenario names share the workshop's lowercase-hyphen grammar. The
# grammar excludes "<", so placeholder examples like `NAME=<feature>` in the
# guide are ignored rather than mistaken for a real reference.
_NAME_RE = re.compile(r"NAME=([a-z0-9]+(?:-[a-z0-9]+)*)")
_SCENARIO_RE = re.compile(r"SCENARIO=([a-z0-9]+(?:-[a-z0-9]+)*)")

# A `make <target>` invocation. Extracted only from code context (see
# `_split_code_and_prose`), so prose such as "any change you make is ..." never
# looks like a target.
_MAKE_RE = re.compile(r"\bmake\s+([a-z][a-z-]*)")

# Custom metric names all live under the `corridor_` namespace.
_METRIC_RE = re.compile(r"(corridor_[a-z_]+)")

# A Markdown link or image: group 1 is "!" for an image, group 2 is the target.
_LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)]+)\)")

# A single-backtick inline code span.
_INLINE_CODE_RE = re.compile(r"`[^`]*`")

# A Makefile target definition line, e.g. "check: lint test". Dotted special
# targets (.PHONY, .venv) start with "." and so never match.
_MAKE_TARGET_DEF_RE = re.compile(r"^([a-z][a-z-]*):")

# A `<name>.png` filename quoted in the screenshot manifest table.
_MANIFEST_PNG_RE = re.compile(r"`([a-z0-9][a-z0-9-]*\.png)`")


# --- Markdown helpers ------------------------------------------------------


def _guide_files() -> list[Path]:
    """Every Markdown file under guide/, sorted for stable failure order."""
    return sorted(GUIDE.rglob("*.md"))


def _split_code_and_prose(text: str) -> tuple[str, str]:
    """Split Markdown into its code text and its prose text.

    Code text is every fenced-block line plus every inline backtick span; prose
    text is everything else, with inline spans blanked out. This mirrors how
    Markdown actually renders: a `make ...` command shown in backticks is code,
    while a link written inside backticks (e.g. the ``![caption](...)`` example
    in guide/README.md) is *not* a live link. Splitting lets each extractor read
    only the half where its tokens are real.
    """
    code_parts: list[str] = []
    prose_parts: list[str] = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence  # the fence marker line itself has no body
            continue
        if in_fence:
            code_parts.append(line)
        else:
            code_parts.extend(_INLINE_CODE_RE.findall(line))
            prose_parts.append(_INLINE_CODE_RE.sub("  ", line))
    return "\n".join(code_parts), "\n".join(prose_parts)


def _tokens(
    pattern: re.Pattern[str], *, code_only: bool = False
) -> list[tuple[Path, str]]:
    """Collect ``(file, capture-group-1)`` for ``pattern`` across the guide.

    With ``code_only`` the pattern runs against code context only; otherwise it
    runs against the raw file (fine for tokens like ``NAME=`` or ``corridor_``
    that only ever appear verbatim).
    """
    found: list[tuple[Path, str]] = []
    for path in _guide_files():
        text = path.read_text(encoding="utf-8")
        if code_only:
            text, _ = _split_code_and_prose(text)
        found.extend((path, m.group(1)) for m in pattern.finditer(text))
    return found


def _links() -> list[tuple[Path, bool, str]]:
    """Collect ``(file, is_image, target)`` for every live link in the guide.

    Links are read from prose only, so backtick-wrapped example links are
    correctly skipped (they render as literal text, not links).
    """
    found: list[tuple[Path, bool, str]] = []
    for path in _guide_files():
        _, prose = _split_code_and_prose(path.read_text(encoding="utf-8"))
        found.extend(
            (path, m.group(1) == "!", m.group(2)) for m in _LINK_RE.finditer(prose)
        )
    return found


def _makefile_targets() -> set[str]:
    """Every target name defined in the Makefile."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    return {
        m.group(1)
        for line in text.splitlines()
        if (m := _MAKE_TARGET_DEF_RE.match(line))
    }


def _manifest_screenshots() -> set[str]:
    """Every ``<name>.png`` filename listed in the screenshot manifest table."""
    text = (GUIDE / "images" / "README.md").read_text(encoding="utf-8")
    return set(_MANIFEST_PNG_RE.findall(text))


def _rel(path: Path) -> str:
    """Repo-relative path string for readable assertion messages."""
    return str(path.relative_to(ROOT))


# --- Contract tests --------------------------------------------------------


def test_guide_feature_names_reference_real_features():
    """A `NAME=<x>` in the guide must name a real workshop feature."""
    real = set(collect(ROOT))
    for path, name in _tokens(_NAME_RE):
        assert name in real, (
            f"{_rel(path)}: `NAME={name}` is not a workshop feature; "
            f"known features: {sorted(real)}"
        )


def test_every_feature_is_documented_in_the_guide():
    """Every real feature must be referenced, so adding one without documenting
    it (or renaming one and forgetting the guide) fails the build."""
    referenced = {name for _, name in _tokens(_NAME_RE)}
    for feature in collect(ROOT):
        assert feature in referenced, (
            f"feature '{feature}' has no `make feature-* NAME={feature}` "
            f"reference anywhere under guide/"
        )


def test_guide_make_targets_are_defined():
    """Every `make <target>` shown in the guide must exist in the Makefile."""
    targets = _makefile_targets()
    for path, target in _tokens(_MAKE_RE, code_only=True):
        assert target in targets, (
            f"{_rel(path)}: `make {target}` has no matching target in the Makefile"
        )


def test_guide_scenarios_are_defined():
    """Every `SCENARIO=<x>` must be a key of simulator.scenarios.SCENARIOS."""
    for path, scenario in _tokens(_SCENARIO_RE):
        assert scenario in SCENARIOS, (
            f"{_rel(path)}: `SCENARIO={scenario}` is not in "
            f"simulator.scenarios.SCENARIOS ({sorted(SCENARIOS)})"
        )


def test_guide_metric_names_exist_in_source():
    """Every `corridor_*` metric named in the guide must appear in the source,
    catching a renamed or removed metric."""
    source = "\n".join(p.read_text(encoding="utf-8") for p in iter_source_files(ROOT))
    for path, metric in _tokens(_METRIC_RE):
        assert metric in source, (
            f"{_rel(path)}: metric '{metric}' appears in no source file under {ROOTS}"
        )


def test_internal_links_resolve():
    """Every internal (non-external) link target must resolve to a real file.

    Placeholder screenshots under images/ are intentionally absent, so their
    existence is checked by the manifest tests below rather than here.
    """
    for path, is_image, target in _links():
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        # Strip a "#anchor" or a "#Lnn-Lnn" GitHub line range before resolving.
        base = target.split("#", 1)[0]
        if not base:
            continue  # pure in-page anchor, nothing to resolve
        if is_image and base.startswith("images/") and base.endswith(".png"):
            continue  # placeholder screenshot — see the manifest tests
        resolved = (path.parent / base).resolve()
        assert resolved.exists(), (
            f"{_rel(path)}: link target '{target}' does not resolve ({resolved})"
        )


def test_referenced_screenshots_are_listed_in_the_manifest():
    """Every screenshot the guide embeds must be listed in the manifest table,
    so a new screenshot reference cannot skip the capture checklist."""
    manifest = _manifest_screenshots()
    for path, is_image, target in _links():
        base = target.split("#", 1)[0]
        if not (is_image and base.startswith("images/") and base.endswith(".png")):
            continue
        name = Path(base).name
        assert name in manifest, (
            f"{_rel(path)}: screenshot '{name}' is not listed in guide/images/README.md"
        )


def test_manifest_screenshots_are_referenced():
    """Every screenshot listed in the manifest must be embedded somewhere, so a
    stale manifest row (a screenshot no step uses) fails the build."""
    referenced = {
        Path(target.split("#", 1)[0]).name
        for _, is_image, target in _links()
        if is_image and target.split("#", 1)[0].startswith("images/")
    }
    for name in _manifest_screenshots():
        assert name in referenced, (
            f"guide/images/README.md lists '{name}' but no guide file "
            f"references images/{name}"
        )
