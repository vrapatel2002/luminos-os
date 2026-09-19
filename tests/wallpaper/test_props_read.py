"""The properties reader, and the three copies of the control-type list.
[CHANGE: claude-code | 2026-09-19] BUG-170, SPEC §3.2

The reader exists because Qt 6.11 will not let QML read a local file through
XMLHttpRequest. The list of control types now lives in three places — the package
layer, this reader, and PropertyStore.qml — and a silent disagreement between
them drops a control from a panel with no error anywhere. That is what the last
test in this file is for.
"""
import json
import os
import pathlib
import re

import pytest

import luminos_wallpaper_props as R

HERE = pathlib.Path(__file__).resolve().parent
REPO = pathlib.Path(os.environ.get("LUMINOS_REPO", HERE.parents[1]))
PLUGIN = pathlib.Path(os.environ.get(
    "LUMINOS_PLUGIN", REPO / "src/wallpapers/org.luminos.livewallpaper/contents"))

GOOD = {"speed": {"type": "slider", "label": "Speed", "value": 1.0},
        "tint": {"type": "color", "value": "#fff"},
        "weird": {"type": "hologram", "value": 1},
        "junk": "not an object"}


# ---- candidate resolution ---------------------------------------------------
def test_scene_specific_file_is_tried_before_the_shared_one():
    got = R.candidates("/x/scenes/Spectrum.qml")
    assert got == ["/x/scenes/Spectrum.properties.json", "/x/scenes/properties.json"]


def test_a_shader_looks_beside_the_shader():
    got = R.candidates("/x/art/cool.frag")
    assert got[0] == "/x/art/cool.properties.json"


def test_a_file_url_is_accepted():
    assert R.candidates("file:///x/s/Spectrum.qml")[0] == "/x/s/Spectrum.properties.json"


@pytest.mark.parametrize("junk", ["", "/", "file://", "  "])
def test_nonsense_input_yields_no_candidates_and_no_crash(junk):
    assert isinstance(R.candidates(junk), list)


# ---- validation -------------------------------------------------------------
def test_unknown_types_and_non_objects_are_skipped_not_fatal():
    ok = R.validate(GOOD)
    assert set(ok) == {"speed", "tint"}


@pytest.mark.parametrize("bad", [None, [], "text", 3, {"a": None}])
def test_validate_never_raises(bad):
    assert isinstance(R.validate(bad), dict)


# ---- read() -----------------------------------------------------------------
def test_missing_file_is_NONE_not_an_error(tmp_path):
    (tmp_path / "Scene.qml").write_text("")
    assert R.read(str(tmp_path / "Scene.qml")) == ("NONE", "")


def test_good_file_returns_one_line_of_json(tmp_path):
    (tmp_path / "Scene.qml").write_text("")
    (tmp_path / "Scene.properties.json").write_text(json.dumps(GOOD))
    status, payload = R.read(str(tmp_path / "Scene.qml"))
    assert status == "OK"
    assert "\n" not in payload
    assert set(json.loads(payload)) == {"speed", "tint"}


def test_malformed_json_is_ERR_and_names_the_file(tmp_path):
    (tmp_path / "Scene.qml").write_text("")
    (tmp_path / "Scene.properties.json").write_text("{ not json")
    status, payload = R.read(str(tmp_path / "Scene.qml"))
    assert status == "ERR"
    assert "Scene.properties.json" in payload and "\n" not in payload


def test_an_unreadable_file_is_ERR_not_silently_empty(tmp_path):
    """BUG-170 in one sentence: this case used to be indistinguishable from
    'this scene declares no settings'."""
    (tmp_path / "Scene.qml").write_text("")
    target = tmp_path / "Scene.properties.json"
    target.write_text(json.dumps(GOOD))
    target.chmod(0o000)
    try:
        status, payload = R.read(str(tmp_path / "Scene.qml"))
    finally:
        target.chmod(0o644)
    if os.geteuid() == 0:
        pytest.skip("root reads anything; the permission case needs a normal user")
    assert status == "ERR" and "cannot read" in payload


# ---- the three copies must agree -------------------------------------------
def _qml_known_types():
    src = (PLUGIN / "ui/props/PropertyStore.qml").read_text()
    block = re.search(r"knownTypes:\s*\[(.*?)\]", src, re.S).group(1)
    return tuple(re.findall(r'"([a-z]+)"', block))


def _pkg_known_types():
    src = (REPO / "scripts/luminos-wallpaper-pkg").read_text()
    block = re.search(r"_KNOWN_PROP_TYPES\s*=\s*\{(.*?)\}", src, re.S).group(1)
    return tuple(re.findall(r'"([a-z]+)"', block))


def test_reader_and_qml_and_package_layer_list_the_same_control_types():
    assert sorted(R.KNOWN) == sorted(_qml_known_types()) == sorted(_pkg_known_types())


def test_there_are_exactly_lively_s_eight():
    assert len(R.KNOWN) == 8
