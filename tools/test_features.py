from tools.features import (
    MalformedError,
    feature_state,
    parse_regions,
    region_state,
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
