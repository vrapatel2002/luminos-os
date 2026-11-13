# tests/sleep/test_lid.py — properties of luminos-lid's decide() (CONTRACTS.md section B).
# [CHANGE: claude-code | 2026-11-06]
import ast
import dataclasses
import itertools
import subprocess
import sys
import threading
import time
from collections import namedtuple
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest import mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "luminos-lid"
SETTINGS = settings(max_examples=400, deadline=None, database=None)


def _forbidden(*_a, **_k):
    raise AssertionError("luminos-lid tried to run a command during a test")


def check_import_safe():
    """The old luminos-lid watches the lid (and can suspend) at import: never load such a file."""
    allowed = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)
    for node in ast.parse(SOURCE.read_text()).body:
        docstring = isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        main_guard = isinstance(node, ast.If) and "__main__" in ast.unparse(node.test)
        assert isinstance(node, allowed) or docstring or main_guard, (
            f"{SOURCE}:{node.lineno}: runs code at import ({type(node).__name__}), refusing to load it"
        )


def load(name="luminos_lid"):
    check_import_safe()
    loader = SourceFileLoader(name, str(SOURCE))
    module = module_from_spec(spec_from_loader(name, loader))
    sys.modules[name] = module  # dataclasses looks its module up here
    written = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # no __pycache__ beside the source
    try:
        with mock.patch("subprocess.Popen", _forbidden), mock.patch("os.system", _forbidden):
            loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = written
    return module


lid = load()
NONE, LOCK, SLEEP = lid.Action.NONE, lid.Action.LOCK_AND_SLEEP, lid.Action.SLEEP


@pytest.fixture(autouse=True, scope="module")
def no_commands():
    """decide() is pure, so no test here can ever reach systemctl — even if that breaks."""
    with mock.patch("subprocess.Popen", _forbidden), mock.patch("os.system", _forbidden):
        yield


Step = namedtuple("Step", "now dt closed resumed_at before action after")


def walk(ticks, start=1000.0):
    """Feed (dt, lid_closed, seconds_since_resume|None) ticks through decide()."""
    now, resumed_at, state, steps = start, None, lid.State(), []
    for dt, closed, ago in ticks:
        now += dt
        if ago is not None:
            resumed_at = max(resumed_at or 0.0, now - ago)
        action, after = lid.decide(now, closed, resumed_at, state)
        steps.append(Step(now, dt, closed, resumed_at, state, action, after))
        state = after
    return steps


def closures(steps):
    return [list(g) for closed, g in itertools.groupby(steps, key=lambda s: s.closed) if closed]


def in_grace(step):
    return step.resumed_at is not None and step.now - step.resumed_at < lid.GRACE


def backoff(attempts):
    return lid.BACKOFF[min(attempts - 1, len(lid.BACKOFF) - 1)]


def really_slept(step):
    """Re-plan 2: a resume newer than the last try means the machine did sleep."""
    last_try, resumed_at = step.before.last_try, step.resumed_at
    return last_try is not None and resumed_at is not None and resumed_at > last_try


# Round numbers land exactly on the >= / < boundaries, the others anywhere between them.
gaps = st.one_of(
    st.sampled_from([0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0]),
    st.floats(0.01, 120.0, allow_nan=False, allow_infinity=False),
)
resumes = st.one_of(st.none(), st.none(), st.none(), st.sampled_from([0.0, 1.0, 5.0]), st.floats(0.0, 40.0))
lids = st.sampled_from([True, True, True, True, True, False])
ticks = st.lists(st.tuples(gaps, lids, resumes), max_size=80)
shut_ticks = st.lists(st.tuples(gaps, st.just(True), st.none()), min_size=1, max_size=80)
times = st.floats(0.0, 1e7, allow_nan=False, allow_infinity=False)
any_state = st.builds(
    lid.State,
    closed_since=st.one_of(st.none(), times),
    attempts=st.integers(0, 10_000),
    last_try=st.one_of(st.none(), times),
)


@given(times, st.one_of(st.none(), times), any_state)
@SETTINGS
def test_lid_open_is_none_and_fresh_state(now, resumed_at, state):
    assert lid.decide(now, False, resumed_at, state) == (NONE, lid.State())


@given(ticks)
@SETTINGS
def test_never_sleeps_within_grace_of_a_resume(sequence):
    for step in walk(sequence):
        if in_grace(step):
            assert step.action is NONE


@given(ticks)
@SETTINGS
def test_grace_leaves_state_alone(sequence):
    for step in walk(sequence):
        if step.closed and in_grace(step):
            assert step.after == step.before


@given(ticks)
@SETTINGS
def test_one_lock_per_closure_and_it_comes_first(sequence):
    for closure in closures(walk(sequence)):
        acted = [s for s in closure if s.action is not NONE]
        allowed = [s for s in closure if not in_grace(s)]
        assert bool(acted) == bool(allowed)  # the first tick out of grace always acts
        if acted:
            assert acted[0] is allowed[0]
            assert acted[0].action is LOCK
            assert all(s.action is SLEEP for s in acted[1:])


@given(shut_ticks)
@SETTINGS
def test_backoff_respected_and_never_gives_up(sequence):
    last = None
    for step in walk(sequence):
        if last is None:
            assert step.action is LOCK  # no resume: the very first tick acts
        elif step.action is NONE:
            assert step.now - last < backoff(step.before.attempts)
        else:
            assert step.now - last >= backoff(step.before.attempts)
        if last is not None:
            assert step.now - last <= max(lid.BACKOFF) + step.dt
        if step.action is not NONE:
            last = step.now


@given(ticks)
@SETTINGS
def test_decide_is_pure(sequence):
    for step in walk(sequence):
        before = dataclasses.replace(step.before)
        first = lid.decide(step.now, step.closed, step.resumed_at, step.before)
        second = lid.decide(step.now, step.closed, step.resumed_at, step.before)
        assert step.before == before
        assert first == second == (step.action, step.after)


@given(ticks)
@SETTINGS
def test_attempts_go_up_by_one_per_action(sequence):
    for closure in closures(walk(sequence)):
        for step in closure:
            if step.action is NONE:
                assert step.after == step.before
            else:
                # a real sleep counts as attempt 1, so the action after it is attempt 2
                assert step.after.attempts == (2 if really_slept(step) else step.before.attempts + 1)
                assert step.after.last_try == step.now


@given(ticks)
@SETTINGS
def test_after_a_real_sleep_the_first_tick_out_of_grace_acts(sequence):
    for closure in closures(walk(sequence)):
        for step in closure:
            if really_slept(step):
                assert step.action is (NONE if in_grace(step) else SLEEP)


@given(ticks)
@SETTINGS
def test_a_closed_lid_only_waits_for_grace_or_backoff(sequence):
    """Never gives up, with resumes in the mix too."""
    for closure in closures(walk(sequence)):
        for step in closure:
            if step.action is NONE and not in_grace(step):
                assert not really_slept(step)
                assert step.now - step.before.last_try < backoff(step.before.attempts)


@given(ticks)
@SETTINGS
def test_closed_since_is_the_first_action_of_the_closure(sequence):
    for closure in closures(walk(sequence)):
        acted = [s for s in closure if s.action is not NONE]
        for step in acted:
            assert step.after.closed_since == acted[0].now


def shut_for(seconds):
    return walk([(1.0, True, None)] * seconds, start=-1.0)


def test_exact_schedule_with_one_second_ticks():
    acted = [s for s in shut_for(200) if s.action is not NONE]
    gaps_seen = [b.now - a.now for a, b in itertools.pairwise(acted)]
    assert acted[0].now == 0.0
    assert gaps_seen[:6] == [2.0, 5.0, 10.0, 30.0, 30.0, 30.0]
    assert [s.action for s in acted[:3]] == [LOCK, SLEEP, SLEEP]
    assert [s.after.attempts for s in acted[:6]] == [1, 2, 3, 4, 5, 6]


def test_first_action_state():
    action, state = lid.decide(50.0, True, None, lid.State())
    assert action is LOCK
    assert state == lid.State(closed_since=50.0, attempts=1, last_try=50.0)


def test_reopening_starts_over():
    action, state = lid.decide(50.0, True, None, lid.State())
    _, state = lid.decide(51.0, False, None, state)
    assert state == lid.State()
    action, _ = lid.decide(52.0, True, None, state)
    assert action is LOCK


def test_grace_boundary():
    state = lid.State(closed_since=0.0, attempts=1, last_try=0.0)
    assert lid.decide(104.9, True, 100.0, state) == (NONE, state)
    assert lid.decide(105.0, True, 100.0, state)[0] is SLEEP


def test_close_right_after_resume_waits_out_the_grace():
    assert lid.decide(101.0, True, 100.0, lid.State()) == (NONE, lid.State())
    assert lid.decide(105.0, True, 100.0, lid.State())[0] is LOCK


def test_spontaneous_wake_resleeps_within_seven_seconds():
    _, state = lid.decide(0.0, True, None, lid.State())
    woke = 3600.0  # BOOTTIME keeps counting through sleep
    acted = None
    for t in range(8):
        action, state = lid.decide(woke + t, True, woke, state)
        if action is not NONE:
            acted = t
            break
    assert action is SLEEP
    assert acted is not None and 5 <= acted <= 7


def test_wake_late_in_the_retries_after_a_short_sleep_restarts_the_schedule():
    state = lid.State(closed_since=0.0, attempts=6, last_try=100.0)
    woke, acted = 110.0, []  # slept 10 s: the old backoff would hold it until 130
    for t in range(60):
        action, state = lid.decide(woke + t, True, woke, state)
        if action is not NONE:
            acted.append((t, state.attempts))
    assert acted == [(5, 2), (10, 3), (20, 4), (50, 5)]


def test_a_resume_at_or_before_the_last_try_changes_nothing():
    state = lid.State(closed_since=0.0, attempts=6, last_try=100.0)
    assert lid.decide(110.0, True, 100.0, state) == (NONE, state)
    assert lid.decide(110.0, True, 90.0, state) == (NONE, state)
    assert lid.decide(130.0, True, 100.0, state)[1].attempts == 7


def test_real_lid_open_during_grace_is_not_fought():
    state = lid.State(closed_since=0.0, attempts=3, last_try=0.0)
    assert lid.decide(3601.0, False, 3600.0, state) == (NONE, lid.State())


def test_never_gives_up_over_a_long_shut_lid():
    steps = walk([(30.0, True, None)] * 5000)
    assert all(s.action is not NONE for s in steps)
    assert steps[-1].after.attempts == 5000


class Stop(BaseException):  # past any `except Exception` in the code under test
    pass


Session = namedtuple("Session", "id type cls locks_after desktop", defaults=("wayland", "user", 0.0, "KDE"))


class World:
    """Everything main() touches, faked: clocks, lid, sessions, suspend_stats, commands. Time only moves when
    the code waits. on_suspend(world) says what a `systemctl suspend` does; by default nothing, as when vetoed.
    Times in `at` flip the lid; times in `naps` put the machine to sleep without being asked, for that long.
    A session's locks_after is how long after its lock-session its LockedHint goes yes; None is never.
    query_error is (text, exception[, until]): a loginctl query containing that text raises it, up to that time.
    hint, if given, is what every LockedHint reads. unlocks maps a time to a session id that stops being locked.
    lock_hangs makes lock-session use up its whole timeout and fail."""

    def __init__(self, seconds, closed=True, on_suspend=lambda world: 0, at=None, lock_code=0, sessions=None,
                 query_error=None, naps=None, hint=None, unlocks=None, lock_hangs=False, blank_listing=False):
        self.start = self.now = 1000.0
        self.end, self.closed, self.on_suspend = self.start + seconds, closed, on_suspend
        self.at, self.naps, self.unlocks = dict(at or {}), dict(naps or {}), dict(unlocks or {})
        self.lock_code, self.query_error, self.locked_at = lock_code, query_error, {}
        self.hint, self.lock_hangs, self.blank_listing = hint, lock_hangs, blank_listing
        self.sessions = [Session("2")] if sessions is None else sessions
        self.asleep, self.success, self.fail, self.polls, self.listings = 0.0, 0, 0, 0, 0
        self.commands, self.timeouts = [], {}

    def sleep(self, seconds):
        self.now = round(self.now + seconds, 6)
        self.asleep += seconds
        self.success += 1
        return 0

    def abort(self):
        self.fail += 1
        return 0

    def advance(self, seconds):
        self.now = round(self.now + seconds, 6)  # 5.0 + ten 0.1s must be 6.0
        if self.now >= self.end:
            raise Stop
        elapsed = self.now - self.start
        for when in sorted(t for t in self.at if t <= elapsed):
            self.closed = self.at.pop(when)
        for when in sorted(t for t in self.unlocks if t <= elapsed):
            self.locked_at.pop(self.unlocks.pop(when), None)
        for when in sorted(t for t in self.naps if t <= elapsed):
            self.sleep(self.naps.pop(when))

    def select(self, _read, _write, _other, timeout):
        self.advance(timeout)
        return [], [], []

    def clock(self, which):
        return self.now if which == time.CLOCK_BOOTTIME else self.now - self.asleep

    def ioctl(self, _fd, request, buffer, *_):
        assert request == (2 << 30) | (len(buffer) << 16) | (ord("E") << 8) | 0x1b  # EVIOCGSW
        buffer[0] = int(self.closed)

    def read_text(self, path, *_a, **_k):
        return {
            "/proc/bus/input/devices": 'N: Name="Lid Switch"\nH: Handlers=event9\n',
            "/sys/power/suspend_stats/success": f"{self.success}\n",
            "/sys/power/suspend_stats/fail": f"{self.fail}\n",
        }[str(path)]

    def locked_hint(self, session):
        if self.hint is not None:
            return self.hint
        locked_at = self.locked_at.get(session.id)
        locked = locked_at is not None and session.locks_after is not None and self.now - locked_at >= session.locks_after
        return "yes" if locked else "no"

    def query(self, cmd, text=False, **_k):
        """`loginctl list-sessions` and `loginctl show-session ID -p NAME... [--value]`, in the real output format."""
        self.listings += cmd[1] == "list-sessions"
        if self.query_error and self.query_error[0] in " ".join(cmd):
            until = self.query_error[2] if len(self.query_error) > 2 else float("inf")
            if self.now - self.start < until:
                raise self.query_error[1]
        if cmd[1] == "list-sessions":
            out = "\n" if self.blank_listing else ""
            out += "".join(f"{s.id} 1000 shawn seat0 1234 {s.cls} tty2 no -\n" for s in self.sessions)
        else:
            session = next(s for s in self.sessions if s.id == cmd[2])
            values = {"Type": session.type, "Class": session.cls, "Desktop": session.desktop,
                      "LockedHint": self.locked_hint(session)}
            names = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-p"]
            self.polls += "LockedHint" in names
            out = "".join((values[n] if "--value" in cmd else f"{n}={values[n]}") + "\n" for n in names)
        return subprocess.CompletedProcess(cmd, 0, stdout=out if text else out.encode())

    def run(self, cmd, *_a, check=False, **kwargs):
        assert "lock-sessions" not in cmd  # Re-plan 9: it starts the greeter that BUG-199 kills
        if cmd[1] in ("list-sessions", "show-session"):
            return self.query(cmd, **{k: v for k, v in kwargs.items() if k == "text"})
        self.commands.append((round(self.now - self.start, 6), tuple(cmd)))
        self.timeouts[cmd[1]] = kwargs.get("timeout")
        if self.lock_hangs and "lock-session" in cmd:
            self.advance(kwargs["timeout"])
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        code = self.on_suspend(self) if "suspend-then-hibernate" in cmd else self.lock_code
        if "lock-session" in cmd and not code:
            self.locked_at[cmd[2]] = self.now
        if check and code:
            raise subprocess.CalledProcessError(code, cmd)
        return subprocess.CompletedProcess(cmd, code)

    def suspends(self):
        return [t for t, cmd in self.commands if "suspend-then-hibernate" in cmd]

    def locks(self):
        return [(t, cmd[2]) for t, cmd in self.commands if "lock-session" in cmd]


def run_main(world):
    def read_text(path, *a, **k):
        return world.read_text(path, *a, **k)

    def block(*_):
        raise BlockingIOError

    with (
        mock.patch("time.clock_gettime", world.clock),
        mock.patch("select.select", world.select),
        mock.patch("time.sleep", world.advance),
        mock.patch("fcntl.ioctl", world.ioctl),
        mock.patch("subprocess.run", world.run),
        mock.patch("os.open", lambda *_a, **_k: 99),
        mock.patch("os.read", block),
        mock.patch.object(Path, "read_text", read_text),
        pytest.raises(Stop),
    ):
        lid.main()
    return world


def near(*times):
    """Within two polls: when exactly a 100 ms poll lands is not the contract."""
    return pytest.approx(list(times), abs=0.21)


def hypr(delay=0.0, sid="2", kind="wayland"):
    """A graphical session KWin will not lock for us."""
    return Session(sid, kind, "user", delay, "Hyprland")


def test_service_start_counts_as_a_resume():
    assert run_main(World(8)).commands == [(5.0, ("/usr/bin/systemctl", "suspend-then-hibernate", "-i"))]


def test_open_lid_never_sleeps():
    assert run_main(World(120, closed=False)).commands == []


def test_attempt_in_flight_is_not_doubled_but_is_retried():
    world = run_main(World(200))  # systemctl returns, suspend_stats never moves
    assert world.suspends() == [5.0, 65.0, 125.0, 185.0]


def test_aborted_attempts_follow_the_backoff():
    world = run_main(World(90, on_suspend=lambda w: w.abort()))
    assert world.suspends() == [5.0, 7.0, 12.0, 22.0, 52.0, 82.0]


def test_goes_back_to_sleep_after_each_spontaneous_wake():
    world = run_main(World(3 * 3610, on_suspend=lambda w: w.sleep(3600)))
    times = world.suspends()
    assert len(times) >= 3
    # The sleep moves the clock, the next tick notices the resume, then GRACE.
    assert [b - (a + 3600) for a, b in itertools.pairwise(times)] == [6.0] * (len(times) - 1)


def test_failed_suspend_arms_no_wait_and_never_exits():
    """Re-plan 3: logind refused, so nothing is in flight: straight to the backoff schedule."""
    assert run_main(World(90, on_suspend=lambda w: 1)).suspends() == [5.0, 7.0, 12.0, 22.0, 52.0, 82.0]


def test_opening_the_lid_ends_the_wait():
    """Re-plan 3: open at 10, shut again at 20, nothing moved suspend_stats: it sleeps at once."""
    world = run_main(World(90, at={10.0: False, 20.0: True}))
    assert world.suspends() == [5.0, 20.0, 80.0]


# Re-plan 9, which replaces section G's lock step. The decision is at 5 in all of these: start counts as a resume.
# KDE sessions: KWin locks them itself before sleep. Other graphical sessions: lock, wait for the hint, settle, sleep.


@pytest.mark.parametrize("kind", ["wayland", "x11"])
def test_a_kde_session_is_not_locked_here_and_sleep_is_immediate(kind):
    world = run_main(World(8, sessions=[Session("2", kind, "user", None, "KDE")]))
    assert world.commands == [(5.0, ("/usr/bin/systemctl", "suspend-then-hibernate", "-i"))]
    assert world.polls == 0


@pytest.mark.parametrize("desktop", ["Hyprland", "GNOME", "sway", "", "kde", "KDE-ish"])
def test_any_other_desktop_is_locked_here(desktop):
    world = run_main(World(12, sessions=[Session("2", "wayland", "user", 0.0, desktop)]))
    assert world.commands[0] == (5.0, ("/usr/bin/loginctl", "lock-session", "2"))
    assert world.suspends() == near(6.0)


@given(st.floats(0.0, 8.0, allow_nan=False), st.sampled_from(["wayland", "x11"]))
@SETTINGS
def test_suspend_waits_for_the_hint_then_settles_within_the_timeout(delay, kind):
    world = run_main(World(12, sessions=[hypr(delay, kind=kind)]))
    first = world.suspends()[0]
    assert first >= min(5 + delay + 1, 10) - 1e-6
    assert first <= min(5 + delay + 0.1 + 1, 10) + 0.101
    assert world.locks() == [(5.0, "2")]


@pytest.mark.parametrize("delay, expected", [(0.0, 6.0), (0.3, 6.3), (2.0, 8.0), (3.9, 9.9)])
def test_settle_is_a_full_second_after_the_hint(delay, expected):
    assert run_main(World(12, sessions=[hypr(delay)])).suspends() == near(expected)


def test_polls_every_100_ms():
    assert 45 <= run_main(World(12, sessions=[hypr(None)])).polls <= 51


def test_timeout_suspends_anyway_and_says_so(capfd):
    assert run_main(World(12, sessions=[hypr(None)])).suspends() == near(10.0)
    assert "lock not confirmed" in capfd.readouterr().out


def test_a_confirmed_lock_is_not_reported_unconfirmed(capfd):
    assert run_main(World(12, sessions=[hypr()])).suspends() == near(6.0)
    assert "lock not confirmed" not in capfd.readouterr().out


def test_a_late_hint_is_still_cut_off_at_five_seconds_total():
    assert run_main(World(12, sessions=[hypr(4.5)])).suspends() == near(10.0)


def test_failed_lock_still_suspends_after_the_timeout():
    assert run_main(World(12, lock_code=1, sessions=[hypr()])).suspends() == near(10.0)


@pytest.mark.parametrize("other", [
    Session("3", "tty", "user", None, ""),
    Session("3", "wayland", "greeter", None, "Hyprland"),
    Session("3", "unspecified", "manager", None, ""),
    Session("3", "tty", "manager", None, ""),
])
def test_only_graphical_user_sessions_count(other):
    assert run_main(World(8, sessions=[other])).commands == [(5.0, ("/usr/bin/systemctl", "suspend-then-hibernate", "-i"))]
    world = run_main(World(12, sessions=[hypr(), other]))
    assert world.locks() == [(5.0, "2")]
    assert world.suspends() == near(6.0)


def test_alongside_kde_only_the_other_session_is_locked_and_waited_for():
    sessions = [Session("2", "wayland", "user", None, "KDE"), hypr(0.3, sid="3")]
    world = run_main(World(12, sessions=sessions))
    assert world.locks() == [(5.0, "3")]
    assert world.suspends() == near(6.3)


def test_every_other_session_must_lock():
    sessions = [hypr(0.3), hypr(2.0, sid="3", kind="x11")]
    assert run_main(World(12, sessions=sessions)).suspends() == near(8.0)
    world = run_main(World(12, sessions=sessions[::-1]))
    assert world.suspends() == near(8.0)
    assert world.locks() == [(5.0, "3"), (5.0, "2")]


def test_no_sessions_at_all_sleeps_at_once():
    assert run_main(World(8, sessions=[])).suspends() == [5.0]


@pytest.mark.parametrize("opens, session", [
    (5.5, hypr()),  # during the settle
    (7.0, hypr(None)),  # still waiting for the hint
])
def test_opening_the_lid_during_the_wait_aborts_the_sleep(opens, session):
    world = run_main(World(30, sessions=[session], at={opens: False}))
    assert world.locks() == [(5.0, "2")]
    assert world.suspends() == []


def test_shutting_it_again_after_an_abort_locks_again():
    world = run_main(World(30, sessions=[hypr()], at={5.5: False, 20.0: True}))
    (first, _), (again, _) = world.locks()
    assert first == 5.0
    assert 20.0 <= again <= 21.1  # the next one-second tick
    assert world.suspends() == near(again + 1.0)


def test_a_sleep_during_the_wait_does_not_suspend_on_waking():
    """PowerDevil asks in the same millisecond, so this is the normal case. BOOTTIME keeps counting through the
    sleep, so the wait's deadline has passed by the time it wakes. The wake still gets its grace."""
    world = run_main(World(3620, sessions=[hypr(None)], naps={5.5: 3600.0}))
    assert world.suspends()[0] - 3605.5 >= 5.0


def test_a_lid_opened_to_wake_it_during_the_wait_is_not_put_back_to_sleep():
    world = run_main(World(3620, sessions=[hypr(None)], naps={5.5: 3600.0}, at={5.5: False}))
    assert world.suspends() == []


# The guard (Re-plan 9 addendum, review5 H1, H2, M1). A nap at 5.5 is noticed on the tick at 3606, which is the
# moment it first runs. It runs again 2 s later. Up to two more only if a query failed.


def guarded(locked=False, **kwargs):
    """One wake from a KDE session's sleep. KWin having locked it is modelled as a lock long before the test."""
    world = World(3620, closed=False, naps={5.5: 3600.0}, **kwargs)
    if locked:
        world.locked_at["2"] = 0.0
    return world


FIRST, SECOND, THIRD, FOURTH = 3606.0, 3608.0, 3610.0, 3612.0


def test_a_kde_session_left_unlocked_is_locked_at_once_and_reported(capfd):
    assert run_main(guarded()).locks() == [(FIRST, "2")]
    assert "WARNING: KDE session 2 was NOT locked after wake — locked it now; check kscreenlockerrc LockOnResume" in capfd.readouterr().out


def test_a_kde_session_kwin_locked_is_left_alone(capfd):
    world = run_main(guarded(locked=True))
    assert world.commands == []
    assert world.polls == 2  # at once and 2 s later, and no more
    assert "WARNING" not in capfd.readouterr().out


def test_the_second_check_catches_a_session_that_reads_unlocked_by_then():
    assert run_main(guarded(locked=True, unlocks={3607.0: "2"})).locks() == [(SECOND, "2")]


def test_the_guard_also_runs_with_the_lid_shut_before_the_sleep_comes_back():
    world = run_main(World(40, on_suspend=lambda w: w.sleep(10.0)))
    assert [cmd[1] for _, cmd in world.commands[:3]] == ["suspend-then-hibernate", "lock-session", "suspend-then-hibernate"]
    assert world.locks()[0][0] < world.suspends()[1]


def test_the_guard_covers_other_desktops_too(capfd):
    assert run_main(guarded(sessions=[hypr()])).locks() == [(FIRST, "2")]
    out = capfd.readouterr().out
    assert "WARNING: session 2 was NOT locked after wake — locked it now" in out
    assert "LockOnResume" not in out


@pytest.mark.parametrize("other", [
    Session("2", "tty", "user", None, ""),
    Session("2", "wayland", "greeter", None, "Hyprland"),
    Session("2", "unspecified", "manager", None, ""),
])
def test_the_guard_only_touches_graphical_user_sessions(other):
    assert run_main(guarded(sessions=[other])).commands == []


def test_the_guard_needs_a_real_wake_not_a_service_start():
    assert run_main(World(60, closed=False)).commands == []


def test_the_guard_checks_twice_per_wake_when_queries_work():
    """The lock is made to fail, so the session keeps reading unlocked: only the plan running out stops a repeat."""
    assert run_main(guarded(lock_code=1)).locks() == [(FIRST, "2"), (SECOND, "2")]
    world = World(3900, closed=False, naps={5.5: 3600.0, 3700.0: 100.0}, lock_code=1)
    assert len(run_main(world).locks()) == 4


def test_the_guard_says_so_when_it_cannot_lock(capfd):
    assert run_main(guarded(lock_code=1)).locks()
    assert "COULD NOT lock it" in capfd.readouterr().out


@pytest.mark.parametrize("hint", ["maybe", "No", " "])
def test_anything_but_yes_counts_as_unlocked(hint, capfd):
    assert run_main(guarded(locked=True, hint=hint)).locks()[0] == (FIRST, "2")
    assert "could not be checked after wake — locked it now" in capfd.readouterr().out


GUARD_ERRORS = [
    FileNotFoundError("loginctl"),
    subprocess.CalledProcessError(1, "loginctl"),
    subprocess.TimeoutExpired("loginctl", 2),
]


@pytest.mark.parametrize("error", GUARD_ERRORS)
def test_a_broken_loginctl_does_not_kill_the_guard_or_the_loop(error, capfd):
    """Fails closed: a LockedHint that cannot be read gets the session locked. Then two retries, and it says it gave up."""
    world = run_main(guarded(locked=True, query_error=("LockedHint", error)))
    assert world.locks() == [(FIRST, "2"), (SECOND, "2"), (THIRD, "2"), (FOURTH, "2")]
    out = capfd.readouterr().out
    assert "could not be checked after wake — locked it now" in out
    assert "gave up" in out


@pytest.mark.parametrize("query", ["list-sessions", "Desktop"])
def test_a_failed_listing_is_retried_and_finds_the_session(query, capfd):
    world = run_main(guarded(query_error=(query, FileNotFoundError("loginctl"), 3607.0)))
    assert world.locks() == [(SECOND, "2")]
    assert world.listings == 2  # it worked, so no further retries
    assert "gave up" not in capfd.readouterr().out


def test_the_last_retry_is_the_third_check_when_the_second_also_failed():
    world = run_main(guarded(query_error=("list-sessions", FileNotFoundError("loginctl"), 3609.0)))
    assert world.locks() == [(THIRD, "2")]
    assert world.listings == 3


@pytest.mark.parametrize("query", ["list-sessions", "Desktop"])
def test_two_retries_at_most_then_it_says_it_gave_up(query, capfd):
    world = run_main(guarded(query_error=(query, FileNotFoundError("loginctl"))))
    assert world.listings == 4
    assert "gave up" in capfd.readouterr().out


def test_a_blank_line_from_loginctl_does_not_kill_the_daemon():
    assert run_main(World(8, blank_listing=True)).suspends() == [5.0]


# review5 M3: a hung lock-session must not hold up the lid loop for the 180 s a suspend may take.


def test_lock_session_has_a_10_s_timeout_and_suspend_keeps_180():
    world = run_main(World(12, sessions=[hypr()]))
    assert world.timeouts == {"lock-session": 10, "suspend-then-hibernate": 180}
    assert run_main(guarded()).timeouts == {"lock-session": 10}


def test_a_hung_lock_session_only_costs_its_timeout():
    world = run_main(World(30, sessions=[hypr()], lock_hangs=True))
    assert world.suspends() == near(20.0)  # 5 + 10 hung + the 5 s cap, as it never reads locked


BROKEN = [
    FileNotFoundError("loginctl"),
    subprocess.CalledProcessError(1, "loginctl"),
    subprocess.TimeoutExpired("loginctl", 2),
]


@pytest.mark.parametrize("error", BROKEN)
@pytest.mark.parametrize("query", ["list-sessions", "Desktop"])
def test_a_broken_loginctl_never_loses_the_sleep(query, error):
    assert run_main(World(8, sessions=[hypr()], query_error=(query, error))).suspends() == [5.0]


@pytest.mark.parametrize("error", BROKEN)
def test_a_broken_hint_query_runs_out_the_timeout(error):
    assert run_main(World(12, sessions=[hypr()], query_error=("LockedHint", error))).suspends() == near(10.0)


def test_retries_do_not_lock_or_wait_again():
    world = run_main(World(9, sessions=[hypr()], on_suspend=lambda w: w.abort()))
    assert world.suspends() == near(6.0, 7.0)
    assert world.locks() == [(5.0, "2")]
    assert world.polls <= 2


def test_contract_constants_and_types():
    assert lid.BACKOFF == (2.0, 5.0, 10.0, 30.0)
    assert lid.GRACE == 5.0
    assert {a.name for a in lid.Action} == {"NONE", "LOCK_AND_SLEEP", "SLEEP"}
    assert lid.State() == lid.State(closed_since=None, attempts=0, last_try=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        lid.State().attempts = 1


def test_import_has_no_side_effects(capfd):
    threads = threading.active_count()
    load("luminos_lid_again")
    out, err = capfd.readouterr()
    assert (out, err) == ("", "")
    assert threading.active_count() == threads


def test_lid_function_budgets():
    blocks = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.Match)

    def depth(node, level=0):
        deepest = level
        for child in ast.iter_child_nodes(node):
            is_elif = isinstance(node, ast.If) and isinstance(child, ast.If) and child.col_offset == node.col_offset
            deepest = max(deepest, depth(child, level + (isinstance(child, blocks) and not is_elif)))
        return deepest

    for node in ast.walk(ast.parse(SOURCE.read_text())):
        if isinstance(node, ast.FunctionDef):
            assert node.end_lineno - node.lineno + 1 <= 40, f"{node.name} is over 40 lines"
            assert depth(node) <= 3, f"{node.name} nests deeper than 3"
