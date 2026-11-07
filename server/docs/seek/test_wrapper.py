import contextlib
import importlib.util
import io
import json
import os
import random
import shlex
import signal
import sqlite3
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src" / "luminos-jf-ffmpeg"

SAMPLE = shlex.split(
    '-analyzeduration 200M -probesize 1G -ss 00:01:36.500 -readrate 10 -fflags +genpts -f matroska '
    '-i file:"/srv/media/tv/VisionQuest/Season 1/VisionQuest - S01E03 - Reboot WEBDL-2160p.mkv" '
    '-map_metadata -1 -map_chapters -1 -threads 0 -map 0:0 -map 0:1 -map -0:s -codec:v:0 copy '
    '-tag:v:0 dvh1 -strict -2 -bsf:v hevc_mp4toannexb -start_at_zero -codec:a:0 copy -copyts '
    '-avoid_negative_ts disabled -max_muxing_queue_size 2048 -f hls -max_delay 5000000 -hls_time 5 '
    '-hls_segment_type mpegts -start_number 19 -hls_segment_filename "/var/cache/jellyfin/transcodes/3cd3%d.ts" '
    '-hls_playlist_type vod -hls_list_size 0 -y "/var/cache/jellyfin/transcodes/3cd3.m3u8"')
MEDIA = "/srv/media/tv/VisionQuest/Season 1/VisionQuest - S01E03 - Reboot WEBDL-2160p.mkv"
PATTERN = "/var/cache/jellyfin/transcodes/3cd3%d.ts"
OUT = "/var/cache/jellyfin/transcodes/3cd3.m3u8"
REMOVED = ["-hls_time", "-hls_segment_type", "-start_number", "-hls_segment_filename",
           "-hls_playlist_type", "-hls_list_size"]
SEC = 10_000_000


def load():
    sys.dont_write_bytecode = True  # no pyc under src/, and no stale pyc after a same-second edit
    loader = SourceFileLoader("jfw", str(SRC))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("jfw", loader))
    loader.exec_module(mod)
    return mod


_mod = None


def jfw():
    global _mod
    if _mod is None:
        _mod = load()
    return _mod


def ref_starts(kfs, total, L):
    """Independent copy of the C# ComputeSegments loop (start ticks only)."""
    if kfs and total < kfs[-1]:
        raise ValueError
    step = L * SEC
    cut, out = step, [0]
    for k in kfs:
        if k >= cut:
            out.append(k)
            cut += step
    return out


def random_keyframes(rng):
    kfs = [0] if rng.random() < 0.5 else []
    t = 0
    for _ in range(rng.randint(0, 80)):
        t += rng.randint(1, 3 * SEC) if rng.random() < 0.9 else rng.randint(3 * SEC, 30 * SEC)
        kfs.append(t)
    return kfs


def has_pair(args, a, b):
    return any(args[i] == a and args[i + 1] == b for i in range(len(args) - 1))


def hms(x):
    return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{x % 60:06.3f}"


def expected_rewrite(args, plan, starts):
    N = plan["N"]
    base = starts[N] / 1e7
    body, kept, i = args[:-2], [], 0
    while i < len(body):
        a = body[i]
        if a in REMOVED or (a == "-f" and body[i + 1] == "hls"):
            i += 2
            continue
        kept.append(a)
        if a == "-ss":
            kept.append(f"{base + 0.15:.3f}")
            i += 1
        i += 1
    times = [f"{s / 1e7 - base - 0.02:.3f}" for s in starts[N + 1:]]
    tail = ["-f", "segment", "-segment_format", "mpegts"]
    if times:
        tail += ["-segment_times", ",".join(times)]
    tail += ["-segment_start_number", str(N), "-segment_list", plan["out"],
             "-segment_list_type", "m3u8", "-y", plan["pattern"]]
    return kept, kept + tail


ANCHORS = {"-readrate", "-threads", "-map", "-copyts", "-max_delay", "-hls_time",
           "-start_number", "-hls_list_size", "-y"}


def random_case(rng):
    starts = [0]
    for _ in range(rng.randint(0, 59)):
        starts.append(starts[-1] + rng.randint(400_000, 120_000_000))
    N = rng.randrange(len(starts))
    L = rng.randint(1, 10)
    base = starts[N] / 1e7
    ss = None if N == 0 else base + rng.choice([0, 0.5]) + rng.uniform(-0.0019, 0.0019)
    pattern = f"/tmp/t{rng.randrange(10**6)}/seg%d.ts"
    out = f"/tmp/t{rng.randrange(10**6)}/main.m3u8"
    args = list(SAMPLE)
    args[args.index("-hls_time") + 1] = str(L)
    args[args.index("-start_number") + 1] = str(N)
    args[args.index("-hls_segment_filename") + 1] = pattern
    args[-1] = out
    i = args.index("-ss")
    if ss is None:
        del args[i:i + 2]
    else:
        args[i + 1] = hms(ss)
    for _ in range(rng.randint(0, 3)):
        pos = rng.choice([j for j, a in enumerate(args) if a in ANCHORS])
        args[pos:pos] = ["-metadata", f"k{rng.randrange(1000)}=v"]
    plan = {"L": L, "N": N, "ss": ss, "path": MEDIA, "pattern": pattern, "out": out}
    return args, plan, starts


def make_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE BaseItems(Id TEXT, Path TEXT)")
    con.execute("CREATE TABLE KeyframeData(ItemId TEXT, TotalDuration INTEGER, KeyframeTicks TEXT)")
    for item_id, media, ticks, total in rows:
        con.execute("INSERT INTO BaseItems VALUES (?, ?)", (item_id, media))
        con.execute("INSERT INTO KeyframeData VALUES (?, ?, ?)", (item_id, total, json.dumps(ticks)))
    con.commit()
    con.close()


class SegmentStarts(unittest.TestCase):
    def test_worked_example(self):
        kfs = [s * SEC for s in (2, 4, 6, 8, 10, 12, 13, 20, 21, 22)]
        self.assertEqual(jfw().segment_starts(kfs, 23 * SEC, 5), [s * SEC for s in (0, 6, 10, 20, 21)])

    def test_empty(self):
        self.assertEqual(jfw().segment_starts([], 5 * SEC, 5), [0])

    def test_properties(self):
        rng = random.Random(1234)
        for _ in range(400):
            kfs = random_keyframes(rng)
            L = rng.randint(1, 10)
            total = (kfs[-1] if kfs else 0) + rng.randint(0, 10 * SEC)
            got = jfw().segment_starts(kfs, total, L)
            self.assertEqual(got[0], 0)
            self.assertTrue(all(a < b for a, b in zip(got, got[1:])), got)
            self.assertTrue(set(got[1:]) <= set(kfs))
            for i, s in enumerate(got):
                self.assertGreaterEqual(s, i * L * SEC)
            self.assertEqual(got, ref_starts(kfs, total, L))

    def test_total_before_last_keyframe_raises(self):
        rng = random.Random(1234)
        for _ in range(300):
            kfs = random_keyframes(rng)
            if not kfs or kfs[-1] == 0:
                continue
            with self.assertRaises(ValueError):
                jfw().segment_starts(kfs, kfs[-1] - rng.randint(1, kfs[-1]), rng.randint(1, 10))


class Parse(unittest.TestCase):
    def test_sample(self):
        self.assertEqual(jfw().parse(list(SAMPLE)), {
            "L": 5, "N": 19, "ss": 96.5, "path": MEDIA, "pattern": PATTERN, "out": OUT})

    def test_ss_optional_and_formats(self):
        args = list(SAMPLE)
        i = args.index("-ss")
        del args[i:i + 2]
        self.assertIsNone(jfw().parse(args)["ss"])
        args[i:i] = ["-ss", "00:00:10"]
        self.assertEqual(jfw().parse(args)["ss"], 10.0)

    def test_ss_after_input_ignored(self):
        args = list(SAMPLE)
        i = args.index("-ss")
        del args[i:i + 2]
        j = args.index("-max_delay")
        args[j:j] = ["-ss", "00:00:10.000"]
        self.assertIsNone(jfw().parse(args)["ss"])

    def test_missing_required_pair(self):
        for flag in ["-hls_segment_type", "-codec:v:0", "-hls_time", "-start_number",
                     "-hls_segment_filename", "-i"]:
            args = list(SAMPLE)
            i = args.index(flag)
            del args[i:i + 2]
            self.assertIsNone(jfw().parse(args), flag)
        args = list(SAMPLE)
        i = args.index("hls") - 1
        del args[i:i + 2]
        self.assertIsNone(jfw().parse(args), "-f hls")
        self.assertIsNone(jfw().parse(SAMPLE[:-2]), "-y OUT")

    def test_unknown_hls_option_or_non_vod(self):
        rng = random.Random(1234)
        for _ in range(100):
            for extra in (["-hls_base_url", "x"], ["-hls_flags", "y"]):
                args = list(SAMPLE)
                pos = rng.choice([j for j, a in enumerate(args) if a in ANCHORS])
                args[pos:pos] = extra
                self.assertIsNone(jfw().parse(args), (extra, pos))
        args = list(SAMPLE)
        args[args.index("-hls_playlist_type") + 1] = "event"
        self.assertIsNone(jfw().parse(args))

    def test_wrong_values(self):
        for flag, value in [("-hls_segment_type", "fmp4"), ("-codec:v:0", "h264_vaapi"),
                            ("-hls_time", "x"), ("-hls_time", "0"), ("-start_number", "-1"),
                            ("-i", MEDIA)]:
            args = list(SAMPLE)
            args[args.index(flag) + 1] = value
            self.assertIsNone(jfw().parse(args), (flag, value))

    def test_last_two_not_y_out(self):
        self.assertIsNone(jfw().parse(SAMPLE + ["-loglevel", "error"]))
        self.assertIsNone(jfw().parse(SAMPLE[:-2] + ["-n", OUT]))

    def test_random_single_token_deletion(self):
        hls = SAMPLE.index("hls")
        required = [hls - 1, hls, len(SAMPLE) - 2, len(SAMPLE) - 1]
        for flag in ["-hls_segment_type", "-codec:v:0", "-hls_time", "-start_number", "-i"]:
            required += [SAMPLE.index(flag), SAMPLE.index(flag) + 1]
        required.append(SAMPLE.index("-hls_segment_filename"))
        rng = random.Random(1234)
        for _ in range(300):
            i = rng.choice(required)
            args = SAMPLE[:i] + SAMPLE[i + 1:]
            self.assertIsNone(jfw().parse(args), SAMPLE[i])


class Rewrite(unittest.TestCase):
    def test_random_valid_plans(self):
        rng = random.Random(1234)
        for _ in range(400):
            args, plan, starts = random_case(rng)
            N, base = plan["N"], starts[plan["N"]] / 1e7
            out = jfw().rewrite(list(args), plan, starts)
            kept, full = expected_rewrite(args, plan, starts)
            for flag in REMOVED:
                self.assertNotIn(flag, out)
            self.assertFalse(has_pair(out, "-f", "hls"))
            self.assertEqual(out[-2:], ["-y", plan["pattern"]])
            self.assertEqual(out[:len(kept)], kept)
            if "-ss" in args:
                self.assertEqual(out[out.index("-ss") + 1], f"{base + 0.15:.3f}")
            if N + 1 < len(starts):
                times = out[out.index("-segment_times") + 1].split(",")
                self.assertEqual(len(times), len(starts) - N - 1)
                self.assertTrue(all(float(a) < float(b) for a, b in zip(times, times[1:])))
                self.assertEqual(times, [f"{starts[N + 1 + j] / 1e7 - base - 0.02:.3f}"
                                         for j in range(len(times))])
            else:
                self.assertNotIn("-segment_times", out)
            self.assertEqual(out, full)

    def test_none_cases(self):
        rng = random.Random(1234)
        for _ in range(300):
            args, plan, starts = random_case(rng)
            N = plan["N"]
            self.assertIsNone(jfw().rewrite(args, dict(plan, N=len(starts) + rng.randint(0, 3)), starts))
            if N > 0:
                self.assertIsNone(jfw().rewrite(args, dict(plan, ss=None), starts))
                near = rng.choice([0, 0.5]) + rng.choice([-1, 1]) * rng.choice(
                    [rng.uniform(0.0025, 0.01), rng.uniform(0.01, 0.2)])  # outside both 2 ms bands
                for off in (near, 0.25, 0.503, 0.497, -0.5, rng.choice([-1, 1]) * rng.uniform(1, 5)):
                    self.assertIsNone(jfw().rewrite(args, dict(plan, ss=starts[N] / 1e7 + off), starts), off)
            else:
                self.assertIsNone(jfw().rewrite(args, dict(plan, ss=rng.uniform(0, 1)), starts))


class LoadKeyframes(unittest.TestCase):
    def test_lookup(self):
        weird = "/srv/média/Été 2024/Ça va — “Quotes” 'n' spaces.mkv"
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, "jellyfin.db")
            make_db(db, [("a1", MEDIA, [0, 20_000_000, 70_000_000], 90_000_000),
                         ("b2", weird, [0, 12_345_678_901], 12_500_000_000)])
            self.assertEqual(jfw().load_keyframes(db, weird), ([0, 12_345_678_901], 12_500_000_000))
            self.assertEqual(jfw().load_keyframes(db, MEDIA), ([0, 20_000_000, 70_000_000], 90_000_000))
            self.assertIsNone(jfw().load_keyframes(db, "/srv/media/missing.mkv"))


class Main(unittest.TestCase):
    KFS = [15_000_000 + 50_000_000 * i for i in range(40)]  # 1.5 s, 6.5 s, ... 196.5 s
    TOTAL = 2_000_000_000

    def run_main(self, db, args):
        env = {"LUMINOS_JF_FFMPEG_REAL": "/bin/true", "LUMINOS_JF_FFMPEG_DB": db}
        err, calls = io.StringIO(), mock.Mock()  # one parent mock records signal/execv order
        with mock.patch.dict(os.environ, env), mock.patch("os.execv", calls.execv), \
                mock.patch("signal.signal", calls.signal), contextlib.redirect_stderr(err):
            load().main(["/usr/local/bin/luminos-jf-ffmpeg"] + list(args))
        self.assertTrue(calls.execv.called)
        self.calls = calls.mock_calls
        return calls.execv.call_args_list[0].args, err.getvalue()

    def assert_sigpipe_reset_before_exec(self):
        first_exec = next(i for i, c in enumerate(self.calls) if c[0] == "execv")
        self.assertIn(mock.call.signal(signal.SIGPIPE, signal.SIG_DFL), self.calls[:first_exec])

    def test_sigpipe_reset_before_every_exec(self):
        corrupt = os.path.join(self.tmp.name, "corrupt.db")
        Path(corrupt).write_bytes(b"not sqlite" * 100)
        for db, args, rewritten in ((self.db, ["-version"], False), (self.db, SAMPLE, True),
                                    (corrupt, SAMPLE, False)):
            argv = self.run_main(db, args)[0][1]
            self.assertEqual(argv != ["/bin/true"] + args, rewritten)
            self.assert_sigpipe_reset_before_exec()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "jellyfin.db")
        make_db(self.db, [("a1", MEDIA, self.KFS, self.TOTAL)])

    def tearDown(self):
        self.tmp.cleanup()

    def test_non_matching_passthrough(self):
        for args in (["-version"], ["-hide_banner", "-i", "file:/x.mkv", "-f", "null", "-"]):
            self.assertEqual(self.run_main(self.db, args)[0], ("/bin/true", ["/bin/true"] + args))

    def with_ss(self, value):
        args = list(SAMPLE)
        args[args.index("-ss") + 1] = value
        return args

    def test_matching_rewritten(self):
        for ss in ("00:01:36.500", "00:01:37.000"):  # piece start, and piece start + Jellyfin's 0.5 s
            args = self.with_ss(ss)
            (real, argv), err = self.run_main(self.db, args)
            m = jfw()
            expected = m.rewrite(list(args), m.parse(list(args)), m.segment_starts(self.KFS, self.TOTAL, 5))
            self.assertIsNotNone(expected, ss)
            self.assertEqual((real, argv), ("/bin/true", ["/bin/true"] + expected))
            self.assertEqual(argv[argv.index("-ss") + 1], "96.650")
            self.assertTrue(argv[argv.index("-segment_times") + 1].startswith("4.980,9.980,"))
            ours = [l for l in err.splitlines() if l.startswith("luminos-jf-ffmpeg")]  # ignore Python warnings
            self.assertEqual(ours, ["luminos-jf-ffmpeg: aligned start=19 cuts=20"])

    def test_no_row_or_bad_ss_passthrough(self):
        other = list(SAMPLE)
        other[other.index("-i") + 1] = "file:/srv/media/other.mkv"
        for args in (other, self.with_ss("00:01:36.750"), self.with_ss("00:01:37.003")):
            self.assertEqual(self.run_main(self.db, args)[0], ("/bin/true", ["/bin/true"] + args))

    def test_missing_or_corrupt_db_passthrough(self):
        corrupt = os.path.join(self.tmp.name, "corrupt.db")
        Path(corrupt).write_bytes(b"this is not a sqlite database\x00" * 200)
        for db in (os.path.join(self.tmp.name, "nope.db"), corrupt):
            self.assertEqual(self.run_main(db, SAMPLE)[0], ("/bin/true", ["/bin/true"] + SAMPLE))


if __name__ == "__main__":
    unittest.main()
