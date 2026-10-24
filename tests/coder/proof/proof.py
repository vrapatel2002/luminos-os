#!/usr/bin/env python3
# luminos-coder proof harness — does the Qwen3.8 REVIEW make Qwen3.6's code pass where Qwen3.6 alone cannot?
# [CHANGE: claude-code | 2026-10-23] DECISION 157.
#
#   proof.py <run_id>
# One run = ONE initial solution from the writer (Qwen3.6), then the SAME code goes down two arms:
#   self  : Qwen3.6 reviews its own code  -> Qwen3.6 fixes it
#   cross : Qwen3.8 reviews the code      -> Qwen3.6 fixes it
# plus "solo2": Qwen3.6 is simply asked to re-check and improve its code with no reviewer (second attempt).
# Every version is scored against hidden tests the models never see (test_hidden.py, validated 107/107 on
# reference.py). Results append to ~/.local/state/luminos/coder/proof-results.jsonl.
# Everything goes through luminos-coder-gateway (sonnet -> writer, opus -> reviewer), the same path Claude Desktop uses.
import json, os, re, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.environ.get("CODER_GATEWAY", "http://127.0.0.1:4142")
OUT = os.path.expanduser("~/.local/state/luminos/coder/proof-results.jsonl")
RUNDIR = os.path.expanduser("~/.local/state/luminos/coder/proof")
os.makedirs(RUNDIR, exist_ok=True)
TASK = open(os.path.join(HERE, "TASK.md")).read()
HIDDEN = open(os.path.join(HERE, "test_hidden.py")).read()

sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "scripts"))
import importlib.machinery, importlib.util
_l = importlib.machinery.SourceFileLoader("rmcp", os.path.join(HERE, "..", "..", "..", "scripts", "luminos-coder-review-mcp"))
_s = importlib.util.spec_from_loader("rmcp", _l); rmcp = importlib.util.module_from_spec(_s); _l.exec_module(rmcp)
REVIEW_SYSTEM = rmcp.REVIEW_SYSTEM          # exactly the prompt the Desktop tool uses

def token():
    for l in open(os.path.expanduser("~/.config/luminos/coder.env")):
        if l.startswith("CODER_LOCAL_TOKEN="):
            return l.strip().split("=", 1)[1]
    return ""

def ask(model, system, user, max_tokens):
    body = {"model": model, "max_tokens": max_tokens, "temperature": 0.6, "top_p": 0.95,
            "messages": [{"role": "user", "content": user}]}
    if system:
        body["system"] = system
    t0 = time.time()
    req = urllib.request.Request(GW + "/v1/messages", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "x-api-key": token(), "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=7200) as r:
        d = json.load(r)
    text = "\n".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    return text, round(time.time() - t0, 1), d.get("usage", {})

def code_of(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return max(blocks, key=len) if blocks else text

def score(code, tag):
    d = tempfile.mkdtemp(prefix=f"{tag}-", dir=RUNDIR)
    open(os.path.join(d, "solution.py"), "w").write(code)
    open(os.path.join(d, "test_hidden.py"), "w").write(HIDDEN)
    p = subprocess.run([rmcp.PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no", "-rN"],
                       cwd=d, capture_output=True, text=True, timeout=300)
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    passed = int((re.search(r"(\d+) passed", tail) or [0, 0])[1])
    failed = int((re.search(r"(\d+) failed", tail) or [0, 0])[1])
    errors = int((re.search(r"(\d+) error", tail) or [0, 0])[1])
    total = passed + failed + errors
    fails = [l.split(" ")[1] for l in p.stdout.splitlines() if l.startswith("FAILED ")][:40]
    if total == 0:   # import error etc.
        total, fails = 107, [tail or p.stderr[-300:]]
    return {"passed": passed, "total": max(total, 107), "dir": d, "failing": fails}

WRITE = TASK + "\n\nReturn the COMPLETE solution.py in a single ```python code block. No other code blocks."
def fix_prompt(code, review):
    return (TASK + "\n\nHere is your current solution.py:\n```python\n" + code + "\n```\n\nA reviewer reported:\n" + review +
            "\n\nFix every REAL defect the reviewer found (check each claim against the specification first; ignore claims that"
            " contradict the specification). Return the COMPLETE corrected solution.py in a single ```python code block.")
SOLO2 = ("\n\nHere is your current solution.py:\n```python\n{code}\n```\n\nRe-read the specification requirement by requirement,"
         " find anything your code gets wrong, and fix it. Return the COMPLETE corrected solution.py in a single ```python code block.")

def rec(o):
    with open(OUT, "a") as f:
        f.write(json.dumps(o) + "\n")
    print(json.dumps({k: v for k, v in o.items() if k not in ("review", "code")}), flush=True)

def main():
    # proof.py <run_id> [--init-from <dir with solution.py>] [--arms self,cross]
    # --init-from reuses an earlier initial solution (same code down both arms, saves ~11 min of writer time).
    a = sys.argv[1:]
    run = a[0] if a and not a[0].startswith("--") else time.strftime("%H%M%S")
    init = a[a.index("--init-from") + 1] if "--init-from" in a else None
    arms = (a[a.index("--arms") + 1] if "--arms" in a else "solo2,self,cross").split(",")
    if init:
        c0 = open(os.path.join(os.path.expanduser(init), "solution.py")).read()
        rec({"run": run, "arm": "initial", "reused_from": init, **score(c0, f"{run}-v0"), "code": c0})
    else:
        # [CHANGE: claude-code | 2026-10-24] PROOF_WRITER picks the model that writes the initial solution
        # (default the Qwen3.6 writer; e.g. PROOF_WRITER=bonsai to test Ternary Bonsai 2 27B as the writer).
        w_text, w_s, w_u = ask(os.environ.get("PROOF_WRITER", "claude-sonnet-4-5"), None, WRITE, 24000)
        c0 = code_of(w_text); s0 = score(c0, f"{run}-v0")
        rec({"run": run, "arm": "initial", "seconds": w_s, "usage": w_u, **s0, "code": c0})

    if "solo2" in arms:
        t, s_, u = ask("claude-sonnet-4-5", None, TASK + SOLO2.format(code=c0), 24000)
        c = code_of(t); rec({"run": run, "arm": "solo2", "seconds": s_, "usage": u, **score(c, f"{run}-solo2"), "code": c})

    # [CHANGE: claude-code | 2026-10-24] PROOF_REVIEWER picks the cross reviewer (default the Qwen3.8 reviewer).
    for arm, model in (("self", "claude-sonnet-4-5"), ("cross", os.environ.get("PROOF_REVIEWER", "claude-opus-4-5"))):
        if arm not in arms:
            continue
        # Each reviewer at its own server's thinking budget: the writer server allows 8192 thinking tokens, so its
        # self-review gets room for that plus the list; the reviewer runs with 1024 thinking + the Desktop tool's cap.
        cap = 12000 if arm == "self" else rmcp.REVIEW_MAX_TOKENS
        raw, rs, ru = ask(model, REVIEW_SYSTEM, f"TASK:\n{TASK}\n\nCODE:\n```\n{c0}\n```\n", cap)
        rv, kept, dropped = rmcp.ground(raw, TASK)   # same quote filter the Desktop tool applies, both arms
        ft, fs, fu = ask("claude-sonnet-4-5", None, fix_prompt(c0, rv), 24000)
        c = code_of(ft)
        rec({"run": run, "arm": arm, "review_seconds": rs, "review_usage": ru, "fix_seconds": fs, "fix_usage": fu,
             "verified": kept, "dropped": dropped, **score(c, f"{run}-{arm}"), "review": rv, "review_raw": raw, "code": c})

if __name__ == "__main__":
    main()
