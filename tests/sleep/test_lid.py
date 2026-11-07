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


class Stop(Exception):
    pass


class World:
    """Everything main() touches, faked: clocks, lid, suspend_stats, commands. One select() is 1 s.
    on_suspend(world) says what a `systemctl suspend` does; by default nothing, as when vetoed."""

    def __init__(self, seconds, closed=True, on_suspend=lambda world: 0, at=None, lock_code=0):
        self.start = self.now = 1000.0
        self.end, self.closed, self.on_suspend, self.at = self.start + seconds, closed, on_suspend, at or {}
        self.lock_code = lock_code
        self.asleep, self.success, self.fail = 0.0, 0, 0
        self.commands = []

    def sleep(self, seconds):
        self.now += seconds
        self.asleep += seconds
        self.success += 1
        return 0

    def abort(self):
        self.fail += 1
        return 0

    def select(self, *_):
        self.now += 1.0
        if self.now >= self.end:
            raise Stop
        self.closed = self.at.get(self.now - self.start, self.closed)
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

    def run(self, cmd, *_a, check=False, **_k):
        self.commands.append((self.now - self.start, tuple(cmd)))
        code = self.on_suspend(self) if "suspend" in cmd else self.lock_code
        if check and code:
            raise subprocess.CalledProcessError(code, cmd)
        return subprocess.CompletedProcess(cmd, code)

    def suspends(self):
        return [t for t, cmd in self.commands if "suspend" in cmd]

    def locks(self):
        return [t for t, cmd in self.commands if "lock-sessions" in cmd]


def run_main(world):
    def read_text(path, *a, **k):
        return world.read_text(path, *a, **k)

    def block(*_):
        raise BlockingIOError

    with (
        mock.patch("time.clock_gettime", world.clock),
        mock.patch("select.select", world.select),
        mock.patch("fcntl.ioctl", world.ioctl),
        mock.patch("subprocess.run", world.run),
        mock.patch("os.open", lambda *_a, **_k: 99),
        mock.patch("os.read", block),
        mock.patch.object(Path, "read_text", read_text),
        pytest.raises(Stop),
    ):
        lid.main()
    return world


def test_service_start_counts_as_a_resume():
    world = run_main(World(8))
    assert world.commands[0] == (5.0, ("/usr/bin/loginctl", "lock-sessions"))
    assert world.commands[1] == (5.0, ("/usr/bin/systemctl", "suspend", "-i"))


def test_open_lid_never_sleeps():
    assert run_main(World(120, closed=False)).commands == []


def test_attempt_in_flight_is_not_doubled_but_is_retried():
    world = run_main(World(200))  # systemctl returns, suspend_stats never moves
    assert world.suspends() == [5.0, 65.0, 125.0, 185.0]
    assert world.locks() == [5.0]


def test_aborted_attempts_follow_the_backoff():
    world = run_main(World(90, on_suspend=lambda w: w.abort()))
    assert world.suspends() == [5.0, 7.0, 12.0, 22.0, 52.0, 82.0]
    assert world.locks() == [5.0]


def test_goes_back_to_sleep_after_each_spontaneous_wake():
    world = run_main(World(3 * 3610, on_suspend=lambda w: w.sleep(3600)))
    times = world.suspends()
    assert len(times) >= 3
    # The sleep moves the clock, the next tick notices the resume, then GRACE.
    assert [b - (a + 3600) for a, b in itertools.pairwise(times)] == [6.0] * (len(times) - 1)


def test_failed_suspend_arms_no_wait_and_never_exits():
    """Re-plan 3: logind refused, so nothing is in flight: straight to the backoff schedule."""
    assert run_main(World(90, on_suspend=lambda w: 1)).suspends() == [5.0, 7.0, 12.0, 22.0, 52.0, 82.0]


def test_failed_lock_still_suspends():
    world = run_main(World(8, lock_code=1))
    assert world.suspends() == [5.0]


def test_opening_the_lid_ends_the_wait():
    """Re-plan 3: open at 10, shut again at 20, nothing moved suspend_stats: it locks at once."""
    world = run_main(World(90, at={10.0: False, 20.0: True}))
    assert world.locks() == [5.0, 20.0]
    assert world.suspends() == [5.0, 20.0, 80.0]


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
