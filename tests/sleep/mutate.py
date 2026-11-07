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
ARM = "give_up = boottime() + SLEEP_WAIT if act(action, st.attempts) else 0.0\n"

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
    "resume not noticed": ("            resumed_at = now\n", ""),
    "no wait for suspend_stats": (HOLD, "elif False:"),
    "waits forever": ("give_up = boottime() + SLEEP_WAIT", "give_up = boottime() + 1e9"),
    "suspend_stats ignored": (HOLD, "elif now < give_up:"),
    "stats read after issuing": ("stats_before = suspend_stats()\n            " + ARM, ARM + "            stats_before = suspend_stats()\n"),
    "wait armed on a refused suspend": (ARM, "act(action, st.attempts)\n            give_up = boottime() + SLEEP_WAIT\n"),
    "refusal reported as success": ("        return False\n", "        return True\n"),
    "opening keeps the wait": ("give_up = 0.0  # opening the lid ends any wait", "pass"),
    "failed lock blocks the suspend": ('        run(LOGINCTL, "lock-sessions")', '        if not run(LOGINCTL, "lock-sessions"):\n            return False'),
    "does not lock": ('run(LOGINCTL, "lock-sessions")', "pass"),
    "inhibitors can veto": ('"suspend", "-i"', '"suspend"'),
    "dies on a failed suspend": ("except (OSError, subprocess.SubprocessError) as e:", "except KeyError as e:"),
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
