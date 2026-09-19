"""Every properties.json we ship must survive the validator with nothing skipped.
[CHANGE: claude-code | 2026-09-19] DECISION 118 — SPEC §3.2

A schema whose control type is misspelled does not crash: validate_properties()
skips it and the panel renders the rest. That is correct behaviour and it is
exactly why a shipped schema needs a test — the failure is a missing slider, not
an error anybody sees.
"""
import json
import os
import pathlib

import pytest

import luminos_wallpaper_pkg as P

# Repo-relative by default; LUMINOS_SCENES lets the build container point at a
# staged copy, because the repo itself is not mounted there.
SCENES = pathlib.Path(os.environ.get(
    "LUMINOS_SCENES",
    pathlib.Path(__file__).resolve().parents[2]
    / "src/wallpapers/org.luminos.livewallpaper/contents/ui/scenes",
))


def _schemas():
    return sorted(SCENES.glob("*.properties.json"))


def test_we_actually_ship_some():
    assert _schemas(), "no properties.json found — did the scenes move?"


@pytest.mark.parametrize("path", _schemas(), ids=lambda p: p.name)
def test_shipped_schema_is_fully_valid(path):
    schema = json.loads(path.read_text())
    ok, skipped = P.validate_properties(schema)
    assert skipped == [], f"{path.name} has unknown control types: {skipped}"
    assert set(ok) == set(schema)


@pytest.mark.parametrize("path", _schemas(), ids=lambda p: p.name)
def test_every_control_has_what_its_type_needs(path):
    schema = json.loads(path.read_text())
    for key, entry in schema.items():
        t = entry["type"]
        if t == "label":
            continue  # read-only text, no value to deliver
        assert "value" in entry, f"{path.name}:{key} ({t}) has no default value"
        if t == "slider":
            assert entry["min"] < entry["max"], f"{path.name}:{key} min >= max"
            assert entry["min"] <= entry["value"] <= entry["max"], (
                f"{path.name}:{key} default {entry['value']} is outside {entry['min']}..{entry['max']}"
            )
        if t == "dropdown":
            assert entry["items"], f"{path.name}:{key} dropdown has no items"
            assert 0 <= entry["value"] < len(entry["items"]), (
                f"{path.name}:{key} default index {entry['value']} is not a valid item"
            )


@pytest.mark.parametrize("path", _schemas(), ids=lambda p: p.name)
def test_defaults_survive_a_round_trip_through_merge(path):
    schema = json.loads(path.read_text())
    merged = P.merge_props(schema, {})
    assert set(merged) == set(schema)
    for key, entry in schema.items():
        assert merged[key] == entry.get("value")
