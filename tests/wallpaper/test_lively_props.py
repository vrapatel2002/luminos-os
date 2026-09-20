"""Lively's property vocabulary, translated — BUG-183, SPEC §3.3.

[CHANGE: claude-code | 2026-09-20]
SPDX-License-Identifier: GPL-3.0-or-later

The map under test is transcribed from Lively's own source
(src/Lively/Lively.Models/LivelyControls/*.cs and Lively.Common/Helpers/
LivelyPropertyUtil.cs). BUG-181 was an invented map with a test that pinned the
invention, so these tests assert the BEHAVIOUR Lively's player has — what value
reaches the page — rather than re-stating the table.
"""
import json
import os
import pathlib

import pytest

import luminos_wallpaper_lively as L
import luminos_wallpaper_props as P

HERE = pathlib.Path(__file__).resolve().parent
REPO = pathlib.Path(os.environ.get("LUMINOS_REPO", HERE.parents[1]))


def test_slider_keeps_range_and_becomes_our_slider():
    out = L.lively_control_to_ours(
        {"type": "slider", "text": "Intensity", "value": 40, "min": 0, "max": 100})
    assert out == {"type": "slider", "value": 40, "label": "Intensity", "min": 0, "max": 100}


def test_livelys_text_becomes_our_label():
    """Two projects, two names for the same string. A control with no caption is
    how a settings panel ends up showing a raw key."""
    assert L.lively_control_to_ours({"type": "checkbox", "text": "Panning",
                                     "value": False})["label"] == "Panning"


def test_dropdown_value_stays_an_index():
    out = L.lively_control_to_ours(
        {"type": "dropdown", "value": 2, "items": ["Off", "Low", "High"]})
    assert out["value"] == 2 and out["items"] == ["Off", "Low", "High"]


def test_scaler_dropdown_is_a_dropdown():
    """Lively has two index-valued dropdowns; only one of them has a name we share."""
    assert L.lively_control_to_ours(
        {"type": "scalerDropdown", "value": 1, "items": ["a", "b"]})["type"] == "dropdown"


def test_folder_dropdown_carries_its_folder_and_indexes_its_items():
    out = L.lively_control_to_ours(
        {"type": "folderDropdown", "value": "b.jpg", "folder": "media"},
        listdir=lambda f: ["c.jpg", "a.jpg", "b.jpg"])
    assert out["items"] == ["a.jpg", "b.jpg", "c.jpg"]     # sorted, so the index is stable
    assert out["value"] == 1                               # b.jpg
    assert out["livelyFolder"] == "media"


def test_folder_dropdown_with_a_missing_file_falls_back_rather_than_crashing():
    out = L.lively_control_to_ours(
        {"type": "folderDropdown", "value": "gone.jpg", "folder": "media"},
        listdir=lambda f: ["a.jpg"])
    assert out["value"] == 0


def test_folder_dropdown_survives_an_unreadable_folder():
    out = L.lively_control_to_ours(
        {"type": "folderDropdown", "value": "a.jpg", "folder": "media"},
        listdir=lambda f: (_ for _ in ()).throw(OSError("nope")))
    assert out["items"] == [] and out["value"] == 0


def test_unknown_control_is_skipped_not_fatal():
    raw = {"good": {"type": "slider", "value": 1}, "odd": {"type": "hologram", "value": 1}}
    assert list(L.lively_props_to_schema(raw)) == ["good"]


def test_garbage_input_is_an_empty_schema():
    assert L.lively_props_to_schema(None) == {}
    assert L.lively_props_to_schema({"x": "not a dict"}) == {}


# ---- the reader ------------------------------------------------------------

def test_reader_finds_lively_properties(tmp_path):
    pkg = tmp_path / "wp"
    (pkg / "media").mkdir(parents=True)
    (pkg / "media" / "a.jpg").write_text("x")
    (pkg / "index.html").write_text("<html>")
    (pkg / "LivelyProperties.json").write_text(json.dumps(
        {"bg": {"type": "folderDropdown", "value": "a.jpg", "folder": "media"}}))
    status, payload = P.read(str(pkg / "index.html"))
    assert status == "OK"
    assert json.loads(payload)["bg"]["livelyFolder"] == "media"


def test_our_own_properties_json_still_wins(tmp_path):
    """A package that ships both is ours to read first — a converted schema must
    never quietly replace one somebody wrote for this plugin."""
    pkg = tmp_path / "wp"
    pkg.mkdir()
    (pkg / "index.html").write_text("<html>")
    (pkg / "properties.json").write_text(json.dumps({"ours": {"type": "slider", "value": 3}}))
    (pkg / "LivelyProperties.json").write_text(json.dumps({"theirs": {"type": "slider", "value": 9}}))
    status, payload = P.read(str(pkg / "index.html"))
    assert status == "OK" and list(json.loads(payload)) == ["ours"]


def test_a_package_with_no_properties_is_still_NONE(tmp_path):
    pkg = tmp_path / "wp"
    pkg.mkdir()
    (pkg / "index.html").write_text("<html>")
    assert P.read(str(pkg / "index.html"))[0] == "NONE"


# ---- the real thing --------------------------------------------------------

STOCK = pathlib.Path(os.path.expanduser("~/.local/share/luminos/wallpapers/rain"))


@pytest.mark.skipif(not (STOCK / "LivelyProperties.json").is_file(),
                    reason="Lively's stock Rain is not installed here")
def test_rain_converts_to_the_sixteen_controls_it_ships():
    status, payload = P.read(str(STOCK / "index.html"))
    schema = json.loads(payload)
    assert status == "OK" and len(schema) == 16
    # The one that mattered: no background texture, no picture (BUG-183).
    media = schema["mediaSelect"]
    assert media["livelyFolder"] == "media"
    assert media["items"][media["value"]].endswith(".jpg")
