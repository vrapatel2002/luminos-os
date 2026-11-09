"""BUG-236 — what the TV is given: a cover for music, a video page only for a real video.

[CHANGE: claude-code | 2026-11-08]
SPDX-License-Identifier: GPL-3.0-or-later
"""
import base64

from hypothesis import given, strategies as st

import luminos_wallpaper_nowplaying as N

TITLE = "Lat Lag Gayee Lyrical - Race 2 | Saif Ali Khan"


def test_youtube_watch_is_video_music_is_not():
    assert N.is_video_page("https://www.youtube.com/watch?v=abc&list=x")
    assert N.is_video_page("https://youtu.be/abc")
    assert N.is_video_page("https://m.youtube.com/watch?v=abc")
    assert not N.is_video_page("https://music.youtube.com/watch?v=abc")
    assert not N.is_video_page("https://www.youtube.com/results?search_query=x")
    assert not N.is_video_page("https://evil.example/youtube.com/watch?v=abc")


def test_newest_matching_page_wins():
    rows = [("https://www.youtube.com/watch?v=old", TITLE + " - YouTube", 100),
            ("https://www.youtube.com/watch?v=new", "(3) " + TITLE + " - YouTube", 200),
            ("https://music.youtube.com/watch?v=mus", TITLE, 300),
            ("https://www.youtube.com/watch?v=other", "Something else", 400)]
    assert N.pick_page(rows, TITLE) == "https://www.youtube.com/watch?v=new"


def test_no_match_or_empty_title_means_no_video():
    rows = [("https://www.youtube.com/watch?v=a", "Other", 1)]
    assert N.pick_page(rows, TITLE) is None
    assert N.pick_page(rows, "   ") is None


@given(st.lists(st.tuples(st.sampled_from(["https://www.youtube.com/watch?v=a", "https://music.youtube.com/watch?v=b",
                                           "https://youtu.be/c", "https://x.org/watch"]),
                          st.text(max_size=30), st.integers(0, 10**6)), max_size=8), st.text(max_size=12))
def test_picked_page_is_always_a_matching_video_page(rows, title):
    page = N.pick_page(rows, title)
    if page is not None:
        assert N.is_video_page(page)
        assert any(r[0] == page and title.strip().lower() in (r[1] or "").lower() for r in rows)


def test_thumbnail_reads_local_file_only(tmp_path):
    art = tmp_path / "cover"
    art.write_bytes(b"\x89PNGdata")
    assert base64.b64decode(N.thumbnail("file://" + str(art))) == b"\x89PNGdata"
    assert N.thumbnail("https://example.com/cover.jpg") is None
    assert N.thumbnail("file://" + str(tmp_path / "missing")) is None


def test_main_without_arguments_says_nothing_is_playing(capsys):
    assert N.main(["x"]) == 2
    assert capsys.readouterr().out.strip() == "null"


def test_video_id_is_file_name_safe():
    assert N.video_id("https://www.youtube.com/watch?v=6wkwmDzZ3n4&list=x") == "6wkwmDzZ3n4"
    assert N.video_id("https://youtu.be/6wkwmDzZ3n4") == "6wkwmDzZ3n4"
    assert N.video_id("https://www.youtube.com/watch?v=../../etc") is None
    assert N.video_id("https://www.youtube.com/watch") is None


def test_download_reuses_the_disk_copy_and_keeps_only_the_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(N, "CACHE", str(tmp_path))
    calls = []

    def fake_run(cmd, timeout=5):
        calls.append(cmd)
        open(cmd[cmd.index("-o") + 1], "wb").write(b"mp4")
        return ""
    monkeypatch.setattr(N, "run", fake_run)
    for i in range(N.CACHE_KEEP + 3):
        assert N.download("https://youtu.be/vid%06d" % i).endswith("vid%06d.mp4" % i)
    assert N.download("https://youtu.be/vid%06d" % (N.CACHE_KEEP + 2)) is not None
    assert len(calls) == N.CACHE_KEEP + 3                     # the repeat came from disk
    assert len(list(tmp_path.glob("*.mp4"))) == N.CACHE_KEEP
    assert not list(tmp_path.glob("*.tmp.*"))


def test_music_page_is_never_downloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(N, "CACHE", str(tmp_path))
    monkeypatch.setattr(N, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran yt-dlp")))
    assert N.download("https://music.youtube.com/watch?v=6wkwmDzZ3n4") is None


def test_failed_download_leaves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(N, "CACHE", str(tmp_path))
    monkeypatch.setattr(N, "run", lambda *a, **k: None)
    assert N.download("https://youtu.be/6wkwmDzZ3n4") is None
    assert list(tmp_path.iterdir()) == []
