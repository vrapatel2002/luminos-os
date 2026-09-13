#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-09-12]
# End-to-end latency harness for the media-server LLM.
#
# Measures what a person actually waits for when asking a coding question about a
# real file: time to first token, and time to the finished answer. Talks to a
# running llama-server. Reports server-side timings, which exclude network.
#
# Usage: llm-e2e-bench.py --url http://127.0.0.1:8080 --file X.py --label cfgname
#
# Turn 1 is cold (no KV cache). Turn 2 asks a DIFFERENT question about the SAME
# file, which is the case prefix caching is supposed to make nearly free.

import argparse, json, time, urllib.request

Q1 = "What does this file do? Answer in three sentences."
Q2 = "Which function here is most likely to fail on a machine with no GPU, and why?"


def ask(url, prompt, n_predict, timeout):
    body = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0,
        "cache_prompt": True,
    }).encode()
    req = urllib.request.Request(url + "/completion", body,
                                 {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    return out, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--file", required=True)
    ap.add_argument("--label", default="run")
    ap.add_argument("--n-predict", type=int, default=200)
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()

    src = open(a.file, encoding="utf-8", errors="replace").read()
    base = "You are a senior engineer. Here is a source file:\n\n```python\n" + src + "\n```\n\n"

    for turn, q in ((1, Q1), (2, Q2)):
        out, wall = ask(a.url, base + q + "\nAnswer: ", a.n_predict, a.timeout)
        t = out["timings"]
        rec = {
            "label": a.label, "turn": turn,
            "prompt_n": t["prompt_n"],
            "ttft_s": round(t["prompt_ms"] / 1000, 2),
            "gen_n": t["predicted_n"],
            "gen_s": round(t["predicted_ms"] / 1000, 2),
            "total_s": round((t["prompt_ms"] + t["predicted_ms"]) / 1000, 2),
            "wall_s": round(wall, 2),
            "pp_tps": round(t["prompt_per_second"] or 0, 2),
            "tg_tps": round(t["predicted_per_second"] or 0, 2),
        }
        print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    main()
