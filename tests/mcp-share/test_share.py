#!/usr/bin/env python3
# End-to-end test for scripts/luminos-mcp-share (DECISION 159). Uses its own broker names (test-*), never the
# production ones, and short idle timers. Run: python3 tests/mcp-share/test_share.py  → prints PASS/FAIL per check.
import json, os, signal, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SHARE = os.path.join(REPO, "scripts", "luminos-mcp-share")
RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}", "luminos-mcp-share")
MP = [os.path.expanduser("~/.mempalace-venv/bin/python3"), "-m", "mempalace.mcp_server"]
CRG = [os.path.expanduser("~/.code-review-graph-venv/bin/code-review-graph"), "serve"]
ENV = {**os.environ, "MCP_SHARE_CHILD_IDLE_S": "6", "MCP_SHARE_BROKER_IDLE_S": "6"}
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


class Session:
    def __init__(self, argv, cwd=REPO):
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=cwd, env=ENV, text=True,
                                  bufsize=1)
        self.n = 0

    def req(self, method, params=None, timeout=180):
        self.n += 1
        mid = self.n * 1000 + 7                  # every client uses the SAME ids → proves renumbering
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}) + "\n")
        self.p.stdin.flush()
        box = {}

        def rd():
            while True:
                line = self.p.stdout.readline()
                if not line:
                    return
                m = json.loads(line)
                if m.get("id") == mid:
                    box["m"] = m
                    return
        t = threading.Thread(target=rd, daemon=True)
        t.start()
        t.join(timeout)
        return box.get("m")

    def note(self, method):
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.p.stdin.flush()

    def open(self):
        r = self.req("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "test", "version": "0"}})
        self.note("notifications/initialized")
        return r

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(10)
        except Exception:
            self.p.kill()


def state(name):
    try:
        return json.load(open(os.path.join(RUN, name + ".state")))
    except Exception:
        return None


def unit_pids(name):
    cg = subprocess.run(["systemctl", "--user", "show", "-p", "ControlGroup", "--value",
                         f"luminos-mcp-share-{name}.service"], capture_output=True, text=True).stdout.strip()
    try:
        return [int(x) for x in open(f"/sys/fs/cgroup{cg}/cgroup.procs").read().split()] if cg else []
    except Exception:
        return []


def real_servers(name, marker):
    """pids of the real MCP server inside the broker unit (the broker's own cmdline also contains the command)."""
    out = []
    for p in unit_pids(name):
        try:
            c = open(f"/proc/{p}/cmdline").read().replace("\0", " ")
        except FileNotFoundError:
            continue
        if marker in c and "luminos-mcp-share" not in c:
            out.append(p)
    return out


def wait_for(fn, secs):
    t0 = time.time()
    while time.time() - t0 < secs:
        if fn():
            return True
        time.sleep(0.5)
    return False


def direct(cmd, calls, cwd=REPO):
    s = Session(cmd, cwd)
    s.open()
    out = [s.req(m, p) for m, p in calls]
    s.close()
    return out


def tool_names(m):
    return sorted(t["name"] for t in (m or {}).get("result", {}).get("tools", []))


def text_of(m):
    return json.dumps((m or {}).get("result"), sort_keys=True)


def test_mempalace():
    name = "test-mempalace"
    subprocess.run(["systemctl", "--user", "stop", f"luminos-mcp-share-{name}.service"], capture_output=True)
    try:
        os.unlink(os.path.expanduser(f"~/.cache/luminos/mcp-share/{name}.json"))
    except FileNotFoundError:
        pass
    want_tools, want_status = direct(MP, [("tools/list", {}), ("tools/call", {"name": "mempalace_status", "arguments": {}})])
    argv = [SHARE, "client", name, "--", *MP]

    # 1) six clients at once
    sess, outs = [Session(argv) for _ in range(6)], [None] * 6

    def one(i):
        s = sess[i]
        outs[i] = (s.open(), s.req("tools/list"), s.req("tools/call", {"name": "mempalace_status", "arguments": {}}))
    th = [threading.Thread(target=one, args=(i,)) for i in range(6)]
    [t.start() for t in th]
    [t.join(300) for t in th]
    check("6 concurrent clients all initialised", all(o and o[0] and "result" in o[0] for o in outs))
    check("tools/list identical to a direct server", all(tool_names(o[1]) == tool_names(want_tools) for o in outs),
          f"{len(tool_names(want_tools))} tools")
    check("mempalace_status identical to a direct server", all(text_of(o[2]) == text_of(want_status) for o in outs))
    st = state(name) or {}
    pyprocs = real_servers(name, "mempalace.mcp_server")
    check("exactly ONE real mempalace process for 6 clients", len(pyprocs) == 1 and st.get("child_starts") == 1,
          f"procs={len(pyprocs)} starts={st.get('child_starts')} clients={st.get('clients')}")
    stub = [int(l.split()[1]) for l in open(f"/proc/{sess[0].p.pid}/status") if l.startswith("VmRSS")]
    check("per-client stub is socat, small", "socat" in open(f"/proc/{sess[0].p.pid}/cmdline").read(), f"{stub[0]} kB RSS")

    # 2) a client that disconnects mid-call does not break the others
    s = Session(argv)
    s.open()
    s.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": "mempalace_status", "arguments": {}}}) + "\n")
    s.p.stdin.flush()
    s.p.kill()
    r = sess[1].req("tools/call", {"name": "mempalace_status", "arguments": {}})
    check("disconnect mid-call: other clients unaffected", text_of(r) == text_of(want_status))

    # 3) child crash → next request restarts it
    os.kill(pyprocs[0], signal.SIGKILL)
    time.sleep(1)
    r = sess[2].req("tools/call", {"name": "mempalace_status", "arguments": {}})
    new = real_servers(name, "mempalace.mcp_server")
    check("server crash: next call restarts and works",
          text_of(r) == text_of(want_status) and len(new) == 1 and new[0] != pyprocs[0],
          f"old pid {pyprocs[0]} → new pid {new}")

    # 4) idle → child stopped while clients stay connected; next call brings it back
    t0 = time.time()
    ok = wait_for(lambda: (state(name) or {}).get("child_pid") is None and not real_servers(name, "mempalace.mcp_server"), 30)
    left = real_servers(name, "mempalace.mcp_server")
    print(f"     (server gone {time.time() - t0:.1f}s after the last call + 6s idle timer)")
    check("idle: real server leaves RAM, clients stay connected", ok and not left, f"clients={(state(name) or {}).get('clients')}")
    r = sess[3].req("tools/list")
    check("idle: tools/list answered from cache without starting the server",
          tool_names(r) == tool_names(want_tools) and (state(name) or {}).get("child_pid") is None)
    r = sess[3].req("tools/call", {"name": "mempalace_status", "arguments": {}})
    check("idle: a real call starts it again", text_of(r) == text_of(want_status))

    # 5) all clients gone → child and broker exit, socket removed
    [x.close() for x in sess]
    gone = wait_for(lambda: not os.path.exists(os.path.join(RUN, name + ".sock")) and not unit_pids(name), 60)
    check("all apps closed: broker + server fully gone, nothing left", gone)

    # 6) cold open of a new app: initialize + tools/list from disk cache, server NOT started
    s = Session(argv)
    a, b = s.open(), s.req("tools/list")
    st = state(name) or {}
    check("app opening does not start the server (cache)", a and tool_names(b) == tool_names(want_tools)
          and st.get("child_starts") == 0, f"starts={st.get('child_starts')}")

    # 7) broker killed outright (SIGKILL leaves a stale socket file) → the next app still gets a working broker
    bpid = (state(name) or {}).get("pid")
    os.kill(bpid, signal.SIGKILL)
    time.sleep(1)
    stale = os.path.exists(os.path.join(RUN, name + ".sock"))
    s2 = Session(argv)
    a = s2.open()
    r = s2.req("tools/call", {"name": "mempalace_status", "arguments": {}})
    check("broker SIGKILLed: next app recovers despite stale socket", stale and a and text_of(r) == text_of(want_status),
          f"stale_socket={stale}")
    s.close()
    s2.close()
    wait_for(lambda: not unit_pids(name), 60)


def test_crg():
    name = "test-crg@auto"
    calls = [("tools/list", {}), ("tools/call", {"name": "list_graph_stats_tool", "arguments": {}})]
    want = direct(CRG, calls)
    argv = [SHARE, "client", name, "--", *CRG]
    sess, outs = [Session(argv) for _ in range(3)], [None] * 3

    def one(i):
        sess[i].open()
        outs[i] = [sess[i].req(m, p) for m, p in calls]
    th = [threading.Thread(target=one, args=(i,)) for i in range(3)]
    [t.start() for t in th]
    [t.join(300) for t in th]
    check("crg @auto: 3 clients, tools/list identical", all(tool_names(o[0]) == tool_names(want[0]) for o in outs),
          f"{len(tool_names(want[0]))} tools")
    check("crg @auto: graph stats identical", all(text_of(o[1]) == text_of(want[1]) for o in outs))
    names = [f[:-6] for f in os.listdir(RUN) if f.startswith("test-crg-") and f.endswith(".state")]
    check("crg @auto: one broker per repo", len(names) == 1, names[0] if names else "none")
    [x.close() for x in sess]
    if names:
        wait_for(lambda: not unit_pids(names[0]), 60)
    s = Session([SHARE, "client", name, "--", *CRG], cwd="/tmp")
    r = s.open()
    check("crg @auto outside a git repo: falls back to a direct server", r and "result" in r)
    s.close()


if __name__ == "__main__":
    test_mempalace()
    test_crg()
    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)
