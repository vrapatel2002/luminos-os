"""BUG-237 — a YouTube video wallpaper becomes a file that is downloaded once and kept while in use.

[CHANGE: claude-code | 2026-11-08]
SPDX-License-Identifier: GPL-3.0-or-later
"""
import os
import time

import luminos_wallpaper_ytfile as Y


def test_ids_from_every_youtube_link_shape():
    assert Y.youtube_id("https://www.youtube.com/watch?v=6wkwmDzZ3n4&t=10") == "6wkwmDzZ3n4"
    assert Y.youtube_id("https://youtu.be/6wkwmDzZ3n4") == "6wkwmDzZ3n4"
    assert Y.youtube_id("https://www.youtube.com/shorts/abcDEF12345") == "abcDEF12345"
    assert Y.youtube_id("https://music.youtube.com/watch?v=6wkwmDzZ3n4") is None
    assert Y.youtube_id("https://evil.example/watch?v=6wkwmDzZ3n4") is None
    assert Y.youtube_id("https://www.youtube.com/watch?v=../../x") is None


def fake_download(calls):
    def run(cmd, timeout=5):
        calls.append(cmd)
        open(cmd[cmd.index("-o") + 1], "wb").write(b"mp4")
        return ""
    return run


def test_downloaded_once_then_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(Y, "CACHE", str(tmp_path))
    calls = []
    monkeypatch.setattr(Y.N, "run", fake_download(calls))
    a = Y.fetch("https://youtu.be/6wkwmDzZ3n4")
    b = Y.fetch("https://www.youtube.com/watch?v=6wkwmDzZ3n4&list=x")
    assert a == b == "file://" + str(tmp_path / "6wkwmDzZ3n4.mp4")
    assert len(calls) == 1
    assert calls[0][-1] == "https://www.youtube.com/watch?v=6wkwmDzZ3n4"   # never the raw, untrusted URL


def test_only_the_newest_are_kept_and_the_current_one_survives(tmp_path, monkeypatch):
    monkeypatch.setattr(Y, "CACHE", str(tmp_path))
    monkeypatch.setattr(Y.N, "run", fake_download([]))
    first = Y.fetch("https://youtu.be/vid000001")
    for i in range(2, Y.KEEP + 4):
        time.sleep(0.01)
        Y.fetch("https://youtu.be/vid%06d" % i)
        time.sleep(0.01)
        assert Y.fetch("https://youtu.be/vid000001") == first          # in use → touched → kept
    left = sorted(f.name for f in tmp_path.glob("*.mp4"))
    assert len(left) == Y.KEEP and "vid000001.mp4" in left


def test_failed_download_gives_nothing_and_leaves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(Y, "CACHE", str(tmp_path))
    monkeypatch.setattr(Y.N, "run", lambda *a, **k: None)
    assert Y.fetch("https://youtu.be/6wkwmDzZ3n4") is None
    assert os.listdir(tmp_path) == []
