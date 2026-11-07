# tests/sleep/test_poster.py — scripts/luminos-wallpaper-poster with a fake browser on PATH (Re-plan 8, section H).
# The real Chromium never runs here; ffmpeg does, for the flat-frame check. live.sh looks at the real poster.
# [CHANGE: claude-code | 2026-11-07]
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_png_stats import noise_rows, png

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "luminos-wallpaper-poster"
FAKE_BROWSER = """#!/bin/sh
printf '%s\\n' "$@" >"$(dirname "$0")/args"
for a in "$@"; do
    case "$a" in --screenshot=*) [ ! -e "$(dirname "$0")/shot.png" ] || cp "$(dirname "$0")/shot.png" "${a#--screenshot=}" ;; esac
done
"""

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


@pytest.fixture
def box(tmp_path):
    """A browser that 'renders' noise, and a wallpaper whose page Lively names."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "chromium").write_text(FAKE_BROWSER)
    (bin_dir / "chromium").chmod(0o755)
    png(bin_dir / "shot.png", noise_rows(32, 32, 3), 32, 3)
    wallpaper = tmp_path / "wp"
    (wallpaper / "sub").mkdir(parents=True)
    (wallpaper / "sub" / "page.html").write_text("<html></html>")
    (wallpaper / "LivelyInfo.json").write_text(json.dumps({"FileName": "sub/page.html"}))
    return bin_dir, wallpaper


def poster(bin_dir, *args):
    path = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          env=dict(os.environ, PATH=path), timeout=60)


def test_writes_the_poster_beside_the_html(box):
    bin_dir, wallpaper = box
    assert poster(bin_dir, wallpaper).returncode == 0
    assert (wallpaper / "sub" / "poster.png").is_file()
    assert not (wallpaper / "poster.png").exists()


def test_default_size_and_six_seconds_of_animation(box):
    bin_dir, wallpaper = box
    poster(bin_dir, wallpaper)
    args = (bin_dir / "args").read_text().split()
    assert "--window-size=2880,1800" in args
    assert any(a.startswith("--virtual-time-budget=") and int(a.split("=")[1]) >= 5000 for a in args)


def test_the_size_can_be_given(box):
    bin_dir, wallpaper = box
    assert poster(bin_dir, wallpaper, "2560x1600").returncode == 0
    assert "--window-size=2560,1600" in (bin_dir / "args").read_text().split()


def test_opens_the_page_as_a_file_url(box):
    bin_dir, wallpaper = box
    poster(bin_dir, wallpaper)
    assert (wallpaper / "sub" / "page.html").as_uri() in (bin_dir / "args").read_text().split()


def test_needs_a_wallpaper_dir(box):
    assert poster(box[0]).returncode != 0


def test_no_page_no_poster(box):
    bin_dir, wallpaper = box
    (wallpaper / "sub" / "page.html").unlink()
    assert poster(bin_dir, wallpaper).returncode != 0
    assert not list(wallpaper.rglob("poster.png"))


def test_no_browser_says_so(box, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    env = dict(os.environ, PATH=str(empty))
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(box[1])], capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_a_browser_that_writes_nothing_is_a_failure(box):
    bin_dir, wallpaper = box
    (bin_dir / "shot.png").unlink()
    assert poster(bin_dir, wallpaper).returncode != 0
    assert not list(wallpaper.rglob("poster.png"))


def test_no_ffmpeg_says_so(box):
    bin_dir, wallpaper = box
    env = dict(os.environ, PATH=str(bin_dir))
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(wallpaper)], capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode != 0
    assert "no ffmpeg" in result.stderr  # with the space: pytest's tmp_path has this test's name in it
    assert "Traceback" not in result.stderr


# The thumbnail lookup is a python3 one-liner inside WebMode.qml's read(). This runs the real text of it.


def thumbnail_program():
    qml = (SCRIPT.parents[1] / "src/wallpapers/org.luminos.livewallpaper/contents/ui/WebMode.qml").read_text()
    body = re.search(r'connectSource\("python3 -c \'(.*?)\' \'"', qml, re.S).group(1)
    pieces = re.findall(r'^(?:\s*\+ ")?(.*?)"?$', body, re.M)
    return "".join(p for p in pieces).replace('\\"', '"')


def thumbnail(page):
    return subprocess.run([sys.executable, "-c", thumbnail_program(), str(page)], capture_output=True, text=True, timeout=30)


def lively(root, thumb="thumb.jpg", bom=False):
    prefix = "﻿" if bom else ""
    (root / "LivelyInfo.json").write_text(prefix + json.dumps({"Thumbnail": thumb} if thumb else {}), encoding="utf-8")


def test_thumbnail_beside_the_page(tmp_path):
    lively(tmp_path)
    assert thumbnail(tmp_path / "page.html").stdout.strip() == (tmp_path / "thumb.jpg").as_uri()


def test_thumbnail_for_a_page_in_a_subfolder_is_in_the_wallpaper_root(tmp_path):
    (tmp_path / "sub" / "deep").mkdir(parents=True)
    lively(tmp_path)
    assert thumbnail(tmp_path / "sub" / "deep" / "page.html").stdout.strip() == (tmp_path / "thumb.jpg").as_uri()


def test_thumbnail_survives_a_lively_bom_and_odd_names(tmp_path):
    root = tmp_path / "it's a wallpaper #1"
    root.mkdir()
    lively(root, "my thumb #2.jpg", bom=True)
    assert thumbnail(root / "page.html").stdout.strip() == (root / "my thumb #2.jpg").as_uri()


def test_thumbnail_missing_prints_nothing(tmp_path):
    lively(tmp_path, thumb=None)
    assert thumbnail(tmp_path / "page.html").stdout.strip() == ""


def test_no_lively_info_prints_nothing(tmp_path):
    assert thumbnail(tmp_path / "page.html").stdout.strip() == ""


@pytest.mark.parametrize("colour", [(0, 0, 0), (40, 40, 40)])
def test_a_flat_frame_never_replaces_a_good_poster(box, colour):
    """A flat poster.png would beat the thumbnail in WebMode and bring back the very black screen."""
    bin_dir, wallpaper = box
    (wallpaper / "sub" / "poster.png").write_bytes(b"the good one")
    png(bin_dir / "shot.png", [bytes(colour) * 32] * 32, 32, 3)
    assert poster(bin_dir, wallpaper).returncode != 0
    assert (wallpaper / "sub" / "poster.png").read_bytes() == b"the good one"
