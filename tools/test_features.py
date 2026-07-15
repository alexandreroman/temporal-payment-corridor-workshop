from pathlib import Path

from tools.features import (
    MalformedError,
    collect,
    feature_diff,
    feature_state,
    iter_source_files,
    main,
    parse_regions,
    region_state,
    set_feature,
    set_feature_in_text,
)

FEATURE_SAMPLE = """\
x = 1
    # --- FEATURE: demo ---
    # y = 2
    # --- END FEATURE: demo ---
z = 3
"""

PAIRED = """\
def run():
    # --- FEATURE-DEFAULT: swap ---
    return "old"
    # --- END FEATURE-DEFAULT: swap ---
    # --- FEATURE: swap ---
    # return "new"
    # --- END FEATURE: swap ---
"""


def test_parse_regions_finds_one_feature_region():
    regions = parse_regions(FEATURE_SAMPLE)
    assert len(regions) == 1
    r = regions[0]
    assert r.name == "demo"
    assert r.kind == "feature"
    assert r.indent == "    "
    assert r.body == ["    # y = 2"]


def test_parse_regions_flags_unclosed_region():
    import pytest

    with pytest.raises(MalformedError):
        parse_regions("    # --- FEATURE: demo ---\n    # y = 2\n")


def test_region_state_reads_commented_and_live_bodies():
    default_region, feature_region = parse_regions(PAIRED)
    assert region_state(default_region) == "enabled"  # live code
    assert region_state(feature_region) == "disabled"  # commented code


def test_feature_state_is_disabled_when_default_live_and_feature_commented():
    assert feature_state(parse_regions(PAIRED)) == "disabled"


def test_enable_swaps_default_out_and_feature_in():
    enabled = set_feature_in_text(PAIRED, "swap", enable=True)
    regions = {r.kind: r for r in parse_regions(enabled)}
    assert region_state(regions["default"]) == "disabled"
    assert region_state(regions["feature"]) == "enabled"
    assert feature_state(parse_regions(enabled)) == "enabled"


def test_enable_then_disable_round_trips_exactly():
    enabled = set_feature_in_text(PAIRED, "swap", enable=True)
    assert set_feature_in_text(enabled, "swap", enable=False) == PAIRED


def test_enable_is_idempotent():
    once = set_feature_in_text(PAIRED, "swap", enable=True)
    twice = set_feature_in_text(once, "swap", enable=True)
    assert once == twice


def test_set_feature_rejects_body_line_less_indented_than_marker():
    import pytest

    text = "    # --- FEATURE: demo ---\nx = 1\n    # --- END FEATURE: demo ---\n"
    with pytest.raises(MalformedError):
        set_feature_in_text(text, "demo", enable=False)


CROSS_FILE_A = """\
class C:
    def __init__(self):
        # --- FEATURE: multi ---
        # self.on = True
        # --- END FEATURE: multi ---
        pass
"""

CROSS_FILE_B = """\
def helper():
    # --- FEATURE: multi ---
    # return 1
    # --- END FEATURE: multi ---
    return 0
"""


def _make_repo(root: Path) -> None:
    (root / "worker").mkdir()
    (root / "worker" / "a.py").write_text(CROSS_FILE_A, encoding="utf-8")
    (root / "worker" / "b.py").write_text(CROSS_FILE_B, encoding="utf-8")


def test_iter_source_files_scans_only_known_roots(tmp_path):
    _make_repo(tmp_path)
    (tmp_path / "notes.py").write_text("# ignored\n", encoding="utf-8")  # not in ROOTS
    files = iter_source_files(tmp_path)
    assert [p.name for p in files] == ["a.py", "b.py"]


def test_collect_groups_a_feature_across_files(tmp_path):
    _make_repo(tmp_path)
    features = collect(tmp_path)
    assert set(features) == {"multi"}
    assert len(features["multi"]) == 2


def test_set_feature_enables_across_files_and_reverts(tmp_path):
    _make_repo(tmp_path)
    changed = set_feature(
        tmp_path, "multi", enable=True, dry_run=False, do_format=False
    )
    assert len(changed) == 2
    assert "self.on = True" in (tmp_path / "worker" / "a.py").read_text()
    set_feature(tmp_path, "multi", enable=False, dry_run=False, do_format=False)
    assert (tmp_path / "worker" / "a.py").read_text() == CROSS_FILE_A


def test_set_feature_dry_run_writes_nothing(tmp_path):
    _make_repo(tmp_path)
    changed = set_feature(tmp_path, "multi", enable=True, dry_run=True, do_format=False)
    assert len(changed) == 2  # would-change files reported
    assert (tmp_path / "worker" / "a.py").read_text() == CROSS_FILE_A  # untouched


def test_feature_diff_shows_the_change(tmp_path):
    _make_repo(tmp_path)
    diff = feature_diff(tmp_path, "multi")
    assert "+        self.on = True" in diff
    assert "-        # self.on = True" in diff


def test_cli_list_prints_state_and_name(tmp_path, capsys, monkeypatch):
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["list"]) == 0
    assert "disabled" in capsys.readouterr().out.replace("  ", " ")


def test_cli_unknown_name_exits_2(tmp_path, capsys, monkeypatch):
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["enable", "nope"]) == 2
    assert "unknown feature 'nope'" in capsys.readouterr().err


def test_cli_enable_reports_changed_files(tmp_path, capsys, monkeypatch):
    _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FEATURES_NO_FORMAT", "1")  # skip ruff in tests
    assert main(["enable", "multi"]) == 0
    assert "enabled 'multi'" in capsys.readouterr().out
