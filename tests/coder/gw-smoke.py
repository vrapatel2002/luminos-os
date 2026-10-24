#!/usr/bin/env python3
# [CHANGE: claude-code | 2026-10-23] luminos-coder: gateway smoke test — non-stream + SSE stream through :4142, with power read-back.
import json, os, subprocess, time, urllib.request
tok = [l.split("=",1)[1].strip() for l in open(os.path.expanduser("~/.config/luminos/coder.env")) if l.startswith("CODER_LOCAL_TOKEN=")][0]
H = {"Content-Type": "application/json", "x-api-key": tok, "anthropic-version": "2023-06-01"}
def post(body, stream=False):
    r = urllib.request.Request("http://127.0.0.1:4142/v1/messages", json.dumps(body).encode(), H)
    return urllib.request.urlopen(r, timeout=1800)
out = {}
t = time.time()
d = json.load(post({"model": "claude-sonnet-4-5", "max_tokens": 400, "messages": [{"role": "user", "content": "Write a Python one-liner that reverses a string s. Answer with just the code."}]}))
out["nonstream_s"] = round(time.time() - t, 1)
out["nonstream_types"] = [b.get("type") for b in d.get("content", [])]
out["nonstream_text"] = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")[:200]
out["powerd"] = subprocess.run(["systemctl", "is-active", "nvidia-powerd"], capture_output=True, text=True).stdout.strip()
out["dgpu"] = open("/sys/bus/pci/devices/0000:01:00.0/power/runtime_status").read().strip()
t = time.time(); ev = []
with post({"model": "claude-haiku-4-5", "max_tokens": 200, "stream": True, "messages": [{"role": "user", "content": "Say hello in 3 words."}]}) as r:
    for line in r:
        line = line.decode().strip()
        if line.startswith("event:"):
            ev.append(line[6:].strip())
out["stream_s"] = round(time.time() - t, 1); out["stream_events"] = sorted(set(ev))
out["health"] = json.load(urllib.request.urlopen("http://127.0.0.1:4142/health"))
open(os.path.expanduser("~/.local/state/luminos/coder/gw-smoke.json"), "w").write(json.dumps(out, indent=1))
print(json.dumps(out))
