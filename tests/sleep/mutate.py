"""tests/sleep/mutate.py — test_lid.py must pass on scripts/luminos-lid and fail on every broken copy of it.

Works in temp dirs, never touches the source. A mutation whose text is no longer in the source is an error:
update it here, or it would quietly stop testing anything.
[CHANGE: claude-code | 2026-11-06]
"""
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE.parents[1] / "scripts" / "luminos-lid").read_text()
HOLD = "elif now < give_up and suspend_stats() == stats_before:"
RESET = "if resumed_at is not None and resumed_at > st.last_try:"
ARM = "give_up = boottime() + SLEEP_WAIT if act(action, st.attempts, fd) else 0.0\n"
CONSTANTS = "LOCK_TIMEOUT, LOCK_SETTLE, LOCK_POLL = 5.0, 1.0, 0.1"
LID_CHECK = "if not lid_is_closed(fd) or asleep_seconds() - asleep > RESUME_JUMP:"
TYPES = '{"Type=wayland", "Type=x11"}'
LOCK = '            run(LOGINCTL, "lock-session", sid, timeout=LOCK_CMD_TIMEOUT)\n'
GUARD_LOCK = 'if run(LOGINCTL, "lock-session", sid, timeout=LOCK_CMD_TIMEOUT) else'
WAIT = "        if sids and not wait_for_lock(fd, sids):\n            return False\n"
ASK_FAILED = 'except (OSError, subprocess.SubprocessError) as e:\n        log(f"failed: {e}")\n        return None'
RUN_FAILED = 'except (OSError, subprocess.SubprocessError) as e:\n        log(f"failed: {e}")\n        return False'
PLAN = "resumed_at, guard_plan = now, [now + n * LOCK_GUARD for n in range(4)]"
PLAN_LEFT = "return [] if worked and len(rest) <= 2 else rest"
WORKED = "worked = listing is not None and None not in answers.values()"
GUARD_WARNING = """log(f"WARNING: {what} {sid} {'was NOT locked' if hint == 'no' else 'could not be checked'} after wake — {done}{tail}")"""

MUTANTS = {
    "unchanged": ("", ""),
    # decide()
    "no grace": ("now - resumed_at < GRACE", "now - resumed_at < 0"),
    "grace off by one": ("now - resumed_at < GRACE", "now - resumed_at <= GRACE"),
    "retry locks again": ("return Action.SLEEP, replace", "return Action.LOCK_AND_SLEEP, replace"),
    "backoff index shifted": ("min(st.attempts - 1, 3)", "min(st.attempts, 3)"),
    "backoff strict": ("now - st.last_try >=", "now - st.last_try >"),
    "gives up": ("    if st.attempts == 0:", "    if st.attempts > 10:\n        return Action.NONE, st\n    if st.attempts == 0:"),
    "attempts +2": ("attempts=st.attempts + 1", "attempts=st.attempts + 2"),
    "open keeps state": ("return Action.NONE, State()", "return Action.NONE, st"),
    "closed_since moves": ("replace(st, attempts=st.attempts + 1", "replace(st, closed_since=now, attempts=st.attempts + 1"),
    "last_try not updated": (", last_try=now)\n    return", ")\n    return"),
    "wrong constant": ("GRACE = 5.0", "GRACE = 4.0"),
    "not frozen": ("@dataclass(frozen=True)", "@dataclass"),
    "no restart after sleep": (RESET, "if False:"),
    "restart on any resume": (RESET, "if resumed_at is not None:"),
    "restart on an equal resume": ("resumed_at > st.last_try", "resumed_at >= st.last_try"),
    "restart at the wrong attempt": ("st = replace(st, attempts=1)", "st = replace(st, attempts=2)"),
    # import and purity
    "prints at import": ("GRACE = 5.0", "GRACE = 5.0\nprint('hello')"),
    "v2 style import": ("GRACE = 5.0", "GRACE = 5.0\nwith open('/dev/null') as f:\n    pass"),
    "decide runs a command": ("    if not lid_closed:", "    subprocess.run(['true'])\n    if not lid_closed:"),
    "decide keeps hidden state": ("    if not lid_closed:", "    global N\n    N = globals().get('N', 0) + 1\n    if N % 97 == 0:\n        return Action.NONE, st\n    if not lid_closed:"),
    # main()
    "start is no resume": ("st, resumed_at, asleep = State(), boottime(), asleep_seconds()", "st, resumed_at, asleep = State(), None, asleep_seconds()"),
    "resume not noticed": (PLAN, "guard_plan = [now + n * LOCK_GUARD for n in range(4)]"),
    "no wait for suspend_stats": (HOLD, "elif False:"),
    "waits forever": ("give_up = boottime() + SLEEP_WAIT", "give_up = boottime() + 1e9"),
    "suspend_stats ignored": (HOLD, "elif now < give_up:"),
    "stats read after issuing": ("stats_before = suspend_stats()\n            " + ARM, ARM + "            stats_before = suspend_stats()\n"),
    "wait armed on a refused suspend": (ARM, "act(action, st.attempts, fd)\n            give_up = boottime() + SLEEP_WAIT\n"),
    "refusal reported as success": ('log(f"failed: {e}")\n        return False', 'log(f"failed: {e}")\n        return True'),
    # who gets locked, and the wait for it (section G, Re-plan 9)
    "locks KDE too": (" if not is_kde]", "]"),
    "locks KDE and not the others": (" if not is_kde]", " if is_kde]"),
    "locks nothing": (LOCK, "            pass\n"),
    "back to lock-sessions": ("        for sid in sids:\n" + LOCK, '        run(LOGINCTL, "lock-sessions")\n'),
    "locks only the first": ("for sid in sids:", "for sid in sids[:1]:"),
    "failed lock blocks the suspend": (LOCK, '            if not run(LOGINCTL, "lock-session", sid, timeout=LOCK_CMD_TIMEOUT):\n                return False\n'),
    "no wait for the lock": (WAIT, ""),
    "abort still suspends": (WAIT, "        if sids:\n            wait_for_lock(fd, sids)\n"),
    "waits with nothing to lock": ("if sids and not wait_for_lock", "if not wait_for_lock"),
    "settle runs past the cap": ("min(deadline, boottime() + LOCK_SETTLE)", "boottime() + LOCK_SETTLE"),
    "no settle": (CONSTANTS, "LOCK_TIMEOUT, LOCK_SETTLE, LOCK_POLL = 5.0, 0.0, 0.1"),
    "settle too short": (CONSTANTS, "LOCK_TIMEOUT, LOCK_SETTLE, LOCK_POLL = 5.0, 0.5, 0.1"),
    "timeout too long": (CONSTANTS, "LOCK_TIMEOUT, LOCK_SETTLE, LOCK_POLL = 8.0, 1.0, 0.1"),
    "timeout too short": (CONSTANTS, "LOCK_TIMEOUT, LOCK_SETTLE, LOCK_POLL = 2.0, 1.0, 0.1"),
    "polls too slowly": (CONSTANTS, "LOCK_TIMEOUT, LOCK_SETTLE, LOCK_POLL = 5.0, 1.0, 0.5"),
    "hint ignored": ('all(locked_hint(s) == "yes" for s in sids)', "True"),
    "tty sessions count": (f' and {TYPES} & set(p)', ""),
    "x11 not locked": (TYPES, '{"Type=wayland"}'),
    "wayland not locked": (TYPES, '{"Type=x11"}'),
    "any class counts": ('"Class=user" in p and ', ""),
    "waits only for the first": ("for s in sids)", "for s in sids[:1])"),
    "lid not re-read": (LID_CHECK, "if asleep_seconds() - asleep > RESUME_JUMP:"),
    "lid only read before the hint": (LID_CHECK, "if (not locked and not lid_is_closed(fd)) or asleep_seconds() - asleep > RESUME_JUMP:"),
    "lid only read during the settle": (LID_CHECK, "if (locked and not lid_is_closed(fd)) or asleep_seconds() - asleep > RESUME_JUMP:"),
    "a sleep during the wait unnoticed": (LID_CHECK, "if not lid_is_closed(fd):"),
    "broken loginctl crashes it": (ASK_FAILED, ASK_FAILED.replace("(OSError, subprocess.SubprocessError)", "KeyError")),
    "broken loginctl reads as yes": (ASK_FAILED, ASK_FAILED.replace("return None", 'return "yes"')),
    "timeout not reported": ('log("lock not confirmed — suspending anyway")', "pass"),
    "timeout gives up the sleep": ('log("lock not confirmed — suspending anyway")\n', 'return False\n'),
    "retries lock and wait too": ("    if action is Action.LOCK_AND_SLEEP:\n        sids", "    if True:\n        sids"),
    "a blank line kills it": ("if line.split()]", "]"),
    # the guard after a wake (Re-plan 9 addendum, review5 H1, H2, M1)
    "no guard": ("guard_plan = guard_pass(guard_plan)", "guard_plan = []"),
    "guard never stops": (PLAN_LEFT, "return plan"),
    "guard armed at service start": ("stats_before, give_up, guard_plan = None, 0.0, []", "stats_before, give_up, guard_plan = None, 0.0, [boottime()]"),
    "guard not at once": ("for n in range(4)]", "for n in range(1, 4)]"),
    "guard gap too long": ("[now + n * LOCK_GUARD", "[now + n * 3 * LOCK_GUARD"),
    "guard only checks once": (PLAN_LEFT, "return [] if worked and len(rest) <= 3 else rest"),
    "guard never retries": (PLAN_LEFT, "return [] if len(rest) <= 2 else rest"),
    "guard retries too often": ("for n in range(4)]", "for n in range(6)]"),
    "guard retries too little": ("for n in range(4)]", "for n in range(3)]"),
    "guard fails open": ('if hint != "yes":', 'if hint == "no":'),
    "guard only locks KDE": ('if hint != "yes":', 'if hint != "yes" and is_kde:'),
    "unreadable hint counts as a working query": ('        worked = worked and hint != ""\n', ""),
    "failed listing counts as working": (WORKED, "worked = None not in answers.values()"),
    "failed properties count as working": (WORKED, "worked = listing is not None"),
    "guard only with the lid open": ("if guard_plan and now >= guard_plan[0]:", "if guard_plan and now >= guard_plan[0] and not lid_is_closed(fd):"),
    "guard says nothing": (GUARD_WARNING, "pass"),
    "guard claims it locked": ('"COULD NOT lock it"', '"locked it now"'),
    "guard blames the wrong setting": ('("session", "")', '("session", "; check kscreenlockerrc LockOnResume")'),
    "guard hides that it gave up": ('log("WARNING: gave up checking the sessions are locked after wake: loginctl keeps failing")', "pass"),
    # timeouts (review5 M3)
    "lock timeout as long as a suspend": ("LOCK_GUARD, LOCK_CMD_TIMEOUT = 2.0, 10", "LOCK_GUARD, LOCK_CMD_TIMEOUT = 2.0, 180"),
    "guard lock not capped": (GUARD_LOCK, 'if run(LOGINCTL, "lock-session", sid) else'),
    "pre-sleep lock not capped": (LOCK, '            run(LOGINCTL, "lock-session", sid)\n'),
    "suspend capped too": ('return run(SYSTEMCTL, "suspend-then-hibernate", "-i")', 'return run(SYSTEMCTL, "suspend-then-hibernate", "-i", timeout=LOCK_CMD_TIMEOUT)'),
    "opening keeps the wait": ("give_up = 0.0  # opening the lid ends any wait", "pass"),
    "does not lock in the guard": (GUARD_LOCK, "if True else"),
    "inhibitors can veto": ('"suspend-then-hibernate", "-i"', '"suspend-then-hibernate"'),
    "dies on a failed suspend": (RUN_FAILED, RUN_FAILED.replace("(OSError, subprocess.SubprocessError)", "KeyError")),
}


def tests_pass(old, new):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "scripts").mkdir()
        (root / "tests" / "sleep").mkdir(parents=True)
        (root / "scripts" / "luminos-lid").write_text(SOURCE.replace(old, new) if old else SOURCE)
        shutil.copy(HERE / "test_lid.py", root / "tests" / "sleep")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", HYPOTHESIS_STORAGE_DIRECTORY=str(root / "hypothesis"))
        cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests/sleep/test_lid.py"]
        result = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, timeout=300)
        return result.returncode == 0, result.stdout


def main():
    stale = [name for name, (old, _) in MUTANTS.items() if old not in SOURCE]
    if stale:
        sys.exit(f"mutations no longer match scripts/luminos-lid: {stale}")
    with ThreadPoolExecutor(4) as pool:
        results = dict(zip(MUTANTS, pool.map(lambda m: tests_pass(*m), MUTANTS.values())))
    wrong = 0
    for name, (passed, output) in results.items():
        good = passed == (name == "unchanged")
        wrong += not good
        print(f"{'ok' if good else 'WRONG'} {name}: tests {'pass' if passed else 'fail'}")
        if name == "unchanged" and not passed:
            print(output)
    sys.exit(wrong)


if __name__ == "__main__":
    main()
