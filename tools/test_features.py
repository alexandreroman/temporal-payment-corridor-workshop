from tools.features import MalformedError, parse_regions

FEATURE_SAMPLE = """\
x = 1
    # --- FEATURE: demo ---
    # y = 2
    # --- END FEATURE: demo ---
z = 3
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
