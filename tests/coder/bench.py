#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-10-23] luminos-coder: quick speed probe — prompt-eval and generation tok/s from llama-server's own timings.
import json, sys, time, urllib.request
port = sys.argv[1] if len(sys.argv) > 1 else "8093"
plen = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
gen = int(sys.argv[3]) if len(sys.argv) > 3 else 200
# varied real-looking text (repeating one paragraph made MoE output gibberish before — see project_moe_expert_offload)
import glob
src = "\n".join(open(f).read() for f in sorted(glob.glob("/home/shawn/luminos-os/cmd/*/*.go")))  # ~260 KB, enough for 60K-token probes
words = src.split()
prompt = " ".join(words[: int(plen * 0.75)])
body = {"messages": [{"role": "user", "content": "Here is Go source:\n" + prompt + "\n\nExplain in detail what this program does, section by section."}],
        "max_tokens": gen, "temperature": 0.6, "chat_template_kwargs": {"enable_thinking": False}}
t = time.time()
r = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
d = json.load(urllib.request.urlopen(r, timeout=3600))
tm = d.get("timings", {})
print(json.dumps({"prompt_n": tm.get("prompt_n"), "prompt_tps": round(tm.get("prompt_per_second", 0), 1),
                  "gen_n": tm.get("predicted_n"), "gen_tps": round(tm.get("predicted_per_second", 0), 2),
                  "draft_n": tm.get("draft_n"), "draft_accepted": tm.get("draft_n_accepted"), "wall_s": round(time.time() - t, 1)}))
