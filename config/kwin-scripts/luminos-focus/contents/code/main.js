// Luminos Focus — KWin is the one component that knows what is really on screen.
// On every relevant change (coalesced 250 ms) it sends one JSON snapshot of all
// normal windows to org.luminos.Focus: pid, active, visible fraction f.
// docs/focus/SPEC.md Part K, CONTRACTS §1-§2.
// [CHANGE: claude-code | 2026-11-07]

// ---- pure maths (no KWin globals, so node can require() this file) ----------

function rectArea(r) {
    return Math.max(0, r.width) * Math.max(0, r.height);
}

function intersect(a, b) {
    var x = Math.max(a.x, b.x), y = Math.max(a.y, b.y);
    var r = Math.min(a.x + a.width, b.x + b.width), btm = Math.min(a.y + a.height, b.y + b.height);
    return { x: x, y: y, width: Math.max(0, r - x), height: Math.max(0, btm - y) };
}

// r minus cutter → up to 4 disjoint rects: full-width bands above and below the
// overlap, then the left and right pieces beside it.
function subtract(r, cutter) {
    var c = intersect(r, cutter);
    if (rectArea(c) === 0) return rectArea(r) > 0 ? [r] : [];
    var out = [
        { x: r.x, y: r.y, width: r.width, height: c.y - r.y },
        { x: r.x, y: c.y + c.height, width: r.width, height: r.y + r.height - c.y - c.height },
        { x: r.x, y: c.y, width: c.x - r.x, height: c.height },
        { x: c.x + c.width, y: c.y, width: r.x + r.width - c.x - c.width, height: c.height }
    ];
    return out.filter(function (p) { return rectArea(p) > 0; });
}

// Share of the whole frame that is on its output and not under any coverer.
function visibleFraction(frame, output, coverers) {
    var total = rectArea(frame);
    if (total === 0) return 0;
    var pieces = [intersect(frame, output)];
    coverers.forEach(function (c) {
        pieces = [].concat.apply([], pieces.map(function (p) { return subtract(p, c); }));
    });
    var seen = pieces.reduce(function (s, p) { return s + rectArea(p); }, 0);
    return Math.min(1, Math.max(0, seen / total));
}

// wins: [{pid, active, minimized, onCurrent, frame, output}] bottom→top.
// Windows with pid ≤ 0 still cover others; they are just not reported.
function buildSnapshot(seq, wins) {
    var out = [];
    wins.forEach(function (w, i) {
        if (!(w.pid > 0)) return;
        var f = 0;
        if (!w.minimized && w.onCurrent) {
            var above = wins.slice(i + 1).filter(function (o) { return !o.minimized && o.onCurrent; });
            f = visibleFraction(w.frame, w.output, above.map(function (o) { return o.frame; }));
        }
        out.push({ pid: w.pid, active: !!w.active, f: Math.round(f * 1000) / 1000 });
    });
    return JSON.stringify({ v: 1, seq: seq, windows: out });
}

if (typeof module !== "undefined")
    module.exports = { rectArea: rectArea, subtract: subtract, visibleFraction: visibleFraction, buildSnapshot: buildSnapshot };

// ---- KWin wiring ------------------------------------------------------------

if (typeof workspace !== "undefined") {
    var seq = 0;
    var last = "";

    var plain = function (r) { return { x: r.x, y: r.y, width: r.width, height: r.height }; };

    var onCurrent = function (w) {
        var desk = w.onAllDesktops || w.desktops.some(function (d) { return d.id === workspace.currentDesktop.id; });
        var act = w.activities.length === 0 || w.activities.indexOf(workspace.currentActivity) >= 0;
        return desk && act && !w.hidden; // [CHANGE: claude-code | 2026-11-07] KWin 6.7: Show Desktop sets w.hidden; no workspace.showingDesktop
    };

    // [CHANGE: claude-code | 2026-11-07] Re-plan 2: active = same pid as the active
    // window (a focused dialog counts for its app). On any error send nothing and
    // clear the cache, so the daemon's 60 s fail-open rule can fire. Logged once
    // per failure streak.
    var failing = false;
    var send = function () {
        try {
            var aw = workspace.activeWindow;
            var activePid = aw ? aw.pid : -1;
            // [CHANGE: claude-code | 2026-11-07] live: quickshell overlays are normalWindow but skipTaskbar
            var wins = workspace.stackingOrder.filter(function (w) { return w.normalWindow && !w.skipTaskbar; }).map(function (w) {
                return {
                    pid: w.pid, active: w.pid === activePid, minimized: w.minimized,
                    onCurrent: onCurrent(w), frame: plain(w.frameGeometry), output: plain(w.output.geometry)
                };
            });
            seq += 1;
            last = buildSnapshot(seq, wins);
            callDBus("org.luminos.Focus", "/org/luminos/Focus", "org.luminos.Focus", "Update", last);
            failing = false;
        } catch (e) {
            last = "";
            if (!failing) print("luminos-focus: snapshot failed, sending nothing: " + e);
            failing = true;
        }
    };

    var debounce = new QTimer();
    debounce.singleShot = true;
    debounce.interval = 250;
    debounce.timeout.connect(send);
    var schedule = function () { debounce.start(); };

    // Heartbeat: a restarted daemon catches up, and its 60 s fail-open rule has a pulse.
    // Recomputes rather than resending a possibly stale string. [CHANGE: claude-code | 2026-11-07]
    var heartbeat = new QTimer();
    heartbeat.interval = 30000;
    heartbeat.timeout.connect(send);
    heartbeat.start();

    var watch = function (w) {
        w.minimizedChanged.connect(schedule);
        w.frameGeometryChanged.connect(schedule);
        w.desktopsChanged.connect(schedule);
        // [CHANGE: claude-code | 2026-11-07] KWin 6.7 has these per window, not on workspace (live error line 130).
        w.stackingOrderChanged.connect(schedule);
        w.hiddenChanged.connect(schedule);
    };

    workspace.windowList().forEach(watch);
    workspace.windowAdded.connect(function (w) { watch(w); schedule(); });
    workspace.windowRemoved.connect(schedule);
    // A focus switch must reach the daemon at once (raise within 250 ms). [CHANGE: claude-code | 2026-11-07]
    workspace.windowActivated.connect(function () { debounce.stop(); send(); });
    workspace.currentDesktopChanged.connect(schedule);
    workspace.currentActivityChanged.connect(schedule);
    schedule();
}
