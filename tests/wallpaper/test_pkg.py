"""Property tests for the wallpaper package layer.

Written BEFORE the implementation. These state what must hold for ANY input, not
for three examples. Contracts: docs/wallpaper/CONTRACTS.md sections 4 and 5.
"""
import json
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

import luminos_wallpaper_pkg as P
import luminos_wallpaper_lively as L

CONTROL_TYPES = ["slider", "color", "dropdown", "textbox", "checkbox", "file", "button", "label"]

# ---- strategies -------------------------------------------------------------
json_scalar = st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False, allow_infinity=False), st.text())
json_val = st.recursive(json_scalar, lambda c: st.one_of(st.lists(c, max_size=4), st.dictionaries(st.text(), c, max_size=4)), max_leaves=12)
arbitrary_dict = st.dictionaries(st.text(), json_val, max_size=8)

good_control = st.fixed_dictionaries({
    "type": st.sampled_from(CONTROL_TYPES),
    "label": st.text(max_size=20),
    "value": json_scalar,
})
schema = st.dictionaries(st.text(min_size=1, max_size=12), good_control, max_size=6)

# ---- properties: validate_properties ---------------------------------------
@given(arbitrary_dict)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=150)
def test_validate_properties_never_raises(d):
    """Any JSON object at all. A hostile manifest must not crash the desktop."""
    ok, skipped = P.validate_properties(d)
    assert isinstance(ok, dict) and isinstance(skipped, list)

@given(schema)
def test_validate_properties_keeps_known_types(s):
    ok, skipped = P.validate_properties(s)
    assert set(ok) == set(s), "every well-formed control must survive"
    assert skipped == []

@given(st.dictionaries(st.text(min_size=1), st.fixed_dictionaries({"type": st.text(min_size=1).filter(lambda t: t not in CONTROL_TYPES)}), min_size=1, max_size=4))
def test_unknown_control_type_is_skipped_not_fatal(s):
    """CONTRACTS 4: unknown control type -> skipped, rest still rendered."""
    ok, skipped = P.validate_properties(s)
    assert ok == {} and set(skipped) == set(s)

# ---- properties: merge_props -----------------------------------------------
@given(schema, arbitrary_dict)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=150)
def test_merge_props_shape(s, saved):
    """Result is exactly the schema's keys — defaults under saved, nothing invented."""
    out = P.merge_props(s, saved)
    assert set(out) == set(s), "never invent a key, never drop a declared one"

@given(schema)
def test_merge_props_defaults_when_nothing_saved(s):
    out = P.merge_props(s, {})
    for k, c in s.items():
        assert out[k] == c["value"]

@given(schema)
def test_merge_props_saved_wins(s):
    saved = {k: "SENTINEL" for k in s}
    out = P.merge_props(s, saved)
    for k in s:
        assert out[k] == "SENTINEL"

# ---- properties: lively import ---------------------------------------------
@given(arbitrary_dict)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=150)
def test_lively_import_never_raises(d):
    """Third-party manifests are untrusted input."""
    m = L.lively_to_manifest(d, pkg_id="x")
    assert isinstance(m, dict)
    for required in ("id", "title", "type", "source"):
        assert required in m
    assert m["source"] == "lively"

# Lively's REAL WallpaperType enum order, transcribed from its own source at
# src/Lively/Lively.Models/Enums/WallpaperType.cs. The table this replaces was
# invented, and pinning it meant the suite DEFENDED a mapping in which a Lively
# video wallpaper imported as "unsupported" and a web one imported as a gif.
# [CHANGE: claude-code | 2026-09-19] BUG-181
LIVELY_ENUM = ["app", "web", "webaudio", "url", "bizhawk", "unity", "godot",
               "video", "gif", "unityaudio", "videostream", "picture"]
LIVELY_TO_OURS = {"app": "producer", "web": "web", "webaudio": "web", "url": "web",
                  "bizhawk": "producer", "unity": "producer", "godot": "producer",
                  "video": "video", "gif": "gif", "unityaudio": "producer",
                  "videostream": "video", "picture": "image"}


@given(st.integers(min_value=-5, max_value=20))
def test_lively_type_index_maps_to_livelys_own_enum(t):
    """SPEC 6: import it, mark it unsupported, do not pretend."""
    m = L.lively_to_manifest({"Title": "t", "Type": t, "FileName": "f"}, pkg_id="x")
    if 0 <= t < len(LIVELY_ENUM):
        assert m["type"] == LIVELY_TO_OURS[LIVELY_ENUM[t]]
        assert m.get("unsupported") is not True
        assert m["livelyType"] == LIVELY_ENUM[t]
    else:
        assert m.get("unsupported") is True


@given(st.sampled_from(LIVELY_ENUM))
def test_lively_type_name_is_accepted_too(name):
    """Newer Lively files write Type as the NAME, older ones as the index."""
    m = L.lively_to_manifest({"Title": "t", "Type": name, "FileName": "f"}, pkg_id="x")
    assert m["type"] == LIVELY_TO_OURS[name]
    assert m.get("unsupported") is not True


@given(st.sampled_from(["", "nonsense", "WEB ", "Video"]))
def test_lively_type_name_tolerates_case_and_space_but_is_not_credulous(name):
    m = L.lively_to_manifest({"Title": "t", "Type": name, "FileName": "f"}, pkg_id="x")
    if name.strip().lower() in LIVELY_TO_OURS:
        assert m["type"] == LIVELY_TO_OURS[name.strip().lower()]
    else:
        assert m.get("unsupported") is True

# ---- properties: manifest parsing ------------------------------------------
@given(arbitrary_dict)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=150)
def test_parse_manifest_never_raises(d):
    m, errs = P.parse_manifest(d)
    assert isinstance(errs, list)
    assert (m is None) == (len(errs) > 0), "a manifest is either valid or has named errors"

def test_parse_manifest_minimal_valid():
    m, errs = P.parse_manifest({"id": "a", "title": "A", "type": "scene", "entry": "s.qml"})
    assert errs == [] and m["interactive"] is False and m["source"] == "native"

@pytest.mark.parametrize("missing", ["id", "title", "type", "entry"])
def test_parse_manifest_names_the_missing_field(missing):
    d = {"id": "a", "title": "A", "type": "scene", "entry": "s.qml"}
    del d[missing]
    m, errs = P.parse_manifest(d)
    assert m is None and any(missing in e for e in errs)

def test_parse_manifest_rejects_path_escape():
    """entry/preview must stay inside the package dir."""
    for bad in ("../../etc/passwd", "/etc/passwd", "a/../../b"):
        m, errs = P.parse_manifest({"id": "a", "title": "A", "type": "scene", "entry": bad})
        assert m is None and errs, f"{bad} must be rejected"


# ---- security: added after review, 2026-09-19 ------------------------------
@pytest.mark.parametrize("bad", [
    "~/.ssh/id_rsa",          # not absolute, no '..' — expanduser downstream escapes the package
    "~root/.bashrc",
    "a\x00b",                 # NUL truncates the path in any C-level open()
    "\\\\server\\share",      # UNC
])
def test_parse_manifest_rejects_sneaky_paths(bad):
    m, errs = P.parse_manifest({"id": "a", "title": "A", "type": "scene", "entry": bad})
    assert m is None and errs, f"{bad!r} must be rejected"

@given(st.text())
def test_path_safe_never_raises(s):
    assert isinstance(P._path_safe(s), bool)
