# CONTRACTS — luminos-focus (frozen; change only by an explicit re-plan logged in BUILD_LOG.md)
# [CHANGE: claude-code | 2026-11-07]

## Budgets (red build if exceeded)
- Go daemon cmd/luminos-focus: ≤ 600 non-test lines total, each file ≤ 150, each func ≤ 40 lines, nesting ≤ 3.
- KWin script config/kwin-scripts/luminos-focus/contents/code/main.js: ≤ 150 lines.
- Wallpaper change: ≤ 90 added lines across the plugin.
- Deps: Go stdlib + github.com/godbus/dbus/v5 v5.2.2 (already in go.mod/module cache; hand-rolled D-Bus would be
  clearly worse). JS: none. Tests: Go testing + testing/quick (property tests), node:test (stdlib) for the JS.

## 1. Snapshot (KWin script → daemon), JSON string
{"v":1,"seq":<int, +1 per send>,"windows":[{"pid":<int>,"active":<bool>,"f":<float 0..1, 3 decimals>}]}
- One entry per NORMAL window (w.normalWindow true, not w.skipTaskbar-only shells; quickshell/layer-shell,
  desktop, dock, notification, OSD windows are never normal → excluded). pid ≤ 0 → excluded.
- f = visible fraction of the window's frameGeometry ∩ its output geometry, after subtracting every other normal,
  non-minimized window on the current desktop+activity stacked ABOVE it (later in workspace.stackingOrder).
  Minimized, not on current desktop/activity, or workspace.showingDesktop → f = 0. Zero-area window → f = 0.
- active = (w === workspace.activeWindow).

## 2. KWin script → bus
callDBus("org.luminos.Focus", "/org/luminos/Focus", "org.luminos.Focus", "Update", json)
- Trigger: windowAdded/windowRemoved/windowActivated, per-window minimizedChanged/frameGeometryChanged/
  desktopsChanged, workspace.currentDesktopChanged/currentActivityChanged/showingDesktopChanged,
  stackingOrderChanged — all coalesced by a 250 ms single-shot timer. Heartbeat: resend last JSON every 30 s.
- Pure functions exported for node tests (guarded `if (typeof module !== "undefined") module.exports = {...}`):
    rectArea(r) → number
    subtract(r, cutter) → [rect]            // r minus cutter, ≤ 4 disjoint rects
    visibleFraction(frame, output, coverers[]) → number in [0,1]
    buildSnapshot(seq, wins[]) → string     // wins: [{pid, active, minimized, onCurrent, frame, output}] in
                                            // stacking order bottom→top; uses visibleFraction
  rect = {x, y, width, height} (KWin QRectF-like plain object).

## 3. Daemon bus API (session bus, name org.luminos.Focus, path /org/luminos/Focus, iface org.luminos.Focus)
- Update(s json) → ()     — never errors to the caller on bad input; logs and ignores.
- State() → (s json)      — {"units":{"<unit>":{"weight":<int>,"quotaPct":<int, 0 = none>,"why":"<string>"}}}
                            current APPLIED values only for units the daemon has touched.

## 4. Go packages/functions (all in package main, cmd/luminos-focus/)
dial.go
  type Want struct { Weight uint64; QuotaPct int /* 0 = no quota */ ; Why string }
  func Dial(f float64, focused bool, exempt bool) Want
     focused → {1000, 0}; exempt → {100, 0}; else weight = round(20+80f), q = round(25+1575f), q ≥ 1600 → 0.
     f clamped to [0,1]; NaN treated as 0.
  func Higher(a, b Want) bool            // a grants strictly more than b (weight up OR quota up/removed)
procmap.go
  func Descendants(proc string, pid int) []int        // pid + all descendants via <proc>/<pid>/task/*/children
  func AppUnit(proc string, pid int) (string, bool)   // unit name if the pid's cgroup v2 path is
                                                      // …/app.slice/<unit>(/…)?; false otherwise
  func UnitsForApp(proc string, pid int) []string     // sorted unique AppUnit over Descendants
audio.go
  func StreamPIDs(pwDumpJSON []byte) map[int]bool     // pids (application.process.id) of nodes whose
       media.class starts with "Stream/" and info.state == "running"; bad JSON → empty map
allow.go
  func LoadAllow(path string) []string                // globs, blank/# lines skipped; missing file → defaults
  func Allowed(unit string, globs []string) bool      // path.Match on the unit name
plan.go
  type Win struct { PID int; Active bool; F float64 }
  func Plan(wins []Win, proc string, audio map[int]bool, globs []string) map[string]Want
       per app pid → UnitsForApp; per unit keep the max-granting Want (focused beats all); a unit is exempt if
       Allowed or any pid of the app's tree is in audio. Never returns the daemon's own unit.
glide.go
  type Setter interface { Set(unit string, w Want) error }
  type Glider struct { ... }               // holds applied state
  func NewGlider(s Setter, now func() time.Time) *Glider
  func (g *Glider) Apply(target map[string]Want)   // raise → Set immediately; lower → 4 steps over 2 s
                                                    // (linear in weight and quota); units absent from target
                                                    // → glide back to {100,0} then forgotten
  func (g *Glider) Tick()                           // advances glides; called every 500 ms only while any glide
                                                    // is pending
  func (g *Glider) ResetAll()                       // Set {100,0} on every touched unit now
systemd.go
  systemd user manager SetUnitProperties(unit, runtime=true, [("CPUWeight", t), ("CPUQuotaPerSecUSec", t)])
  quota none = ^uint64(0); quotaPct q → q*10000 µs per second.
main.go  wiring: bus name (exit 1 if taken), Update handler → channel → one goroutine; pw-dump only when a plan
  has any non-exempt unit with weight < 100, then every 5 s while that holds; 60 s without Update while anything
  is throttled → ResetAll; SIGTERM/SIGINT → ResetAll and exit 0; on start ResetAll for every app.slice unit with a
  non-default CPUWeight/CPUQuota (leftovers).

## 5. Files and ownership
- Implementer (Go): cmd/luminos-focus/*.go (non-test), systemd/user/luminos-focus.service,
  config/luminos/focus-allow.conf
- Implementer (KWin+wallpaper): config/kwin-scripts/luminos-focus/**, src/wallpapers/org.luminos.livewallpaper/**
- Test writer: cmd/luminos-focus/*_test.go, tests/focus/** (except measure.sh, kwin-eval.sh, phaseA.sh = PM tools)
- PM: docs/focus/**, installs, live A/B, repo state files.

## 6. Default allow-list (config/luminos/focus-allow.conf)
app-*konsole*  app-*kitty*  app-*Alacritty*  app-*alacritty*  app-*foot*  app-*wezterm*  app-*ghostty*
app-*qbittorrent*  app-*transmission*  app-*steam*  app-*lutris*  app-*wine*  app-*gamescope*  app-*heroic*
app-*luminos*  app-com.anthropic.Claude-*.scope   ← holds the Cowork VM (qemu+virtiofsd are children of the
Claude main process, measured 2026-11-07); Claude's renderers live in app-com.anthropic.Claude@*.service and ARE
throttled when hidden.

## Re-plan 1 (14:06, PM) — clarifications, no code thrown away
- f denominator = the WHOLE frame area; numerator = the part of the frame that is on its output and not covered.
  (A window half off-screen with nothing on top → f = 0.5.)
- Windows excluded from the snapshot for pid ≤ 0 still COVER the windows below them.
- Show Desktop: the KWin wiring passes every window as onCurrent=false → f 0 (buildSnapshot has no extra flag).
- Glide steps land at +0.5/+1.0/+1.5/+2.0 s (first step not immediate); returning a forgotten unit to {100,0} is a
  raise when it was throttled → immediate.
- Allow-list is read once at start (restart to reload).
- plan.go exposes `var selfUnit string` (set in main from AppUnit(os.Getpid())); Plan never returns it.

## Re-plan 2 (14:21, PM, from review1 — docs/focus/briefs/review1.out.txt)
- AppUnit returns (unit, true) ONLY if the unit sits directly under app.slice AND its name starts with "app-"
  (desktop-launched apps per the XDG systemd naming). Plain user services that live in app.slice (luminos-hive,
  claude-cowork, luminos-focus itself, glm proxy, portals…) are never touched. Leftover reset uses the same rule.
- pwDump (exec wrapper) returns nil on exec error/timeout; replan keeps the previous audio map when it gets nil
  (a wedged PipeWire must not drop the exemption). StreamPIDs(garbage) still returns an empty map.
- KWin: windowActivated sends immediately (stop the debounce, send now); everything else stays debounced 250 ms.
  Heartbeat recomputes (calls send()) instead of resending the cached string; send() is wrapped in try/catch and
  on error sends nothing and clears the cache. active = (w.pid === activeWindow.pid) — a focused dialog/transient of
  the same process counts for its app.

## Re-plan 3 (14:25, PM, found live on KWin 6.7.5)
- KWin 6.7 has NO workspace.showingDesktop / showingDesktopChanged / stackingOrderChanged (script died at load:
  "Cannot call method 'connect' of undefined"). Use per-window w.stackingOrderChanged + w.hiddenChanged; Show Desktop
  shows up as w.hidden = true → onCurrent false.
- Quickshell (Caelestia/Luminos desktop overlay, 44 px bar, a 1396×900 transparent layer) reports normalWindow=true,
  layer 3, skipTaskbar=true. An app window = normalWindow && !skipTaskbar; nothing else is reported or covers.

## Re-plan 4 (14:37, PM, measured live) — the daemon itself must be near-zero
Measured: luminos-focus's own process used 1.5 % of a core in steady state (Chrome hidden → 5 s re-check). pw-dump
is only ~9 ms CPU; the cost is Plan walking every thread's /proc/<pid>/task/*/children of Chrome (~250 threads),
Claude + the Cowork VM, twice per re-check, and once per window even when several windows share a pid.
Change (signatures of Plan/Descendants/AppUnit/UnitsForApp unchanged, tests keep passing):
- new `type appTree struct { PIDs []int; Units []string }` and `func trees(wins []Win, proc string) map[int]appTree`
  (one walk per distinct pid); `func planFrom(wins []Win, t map[int]appTree, audio map[int]bool, globs []string)
  map[string]Want`; Plan = planFrom(wins, trees(wins, proc), …).
- the daemon builds trees once per Update (and on the 30 s heartbeat, which is an Update) and reuses them in the
  5 s re-check and for both plans in replan. Re-check does NO /proc walking.
Target: steady-state daemon CPU < 0.2 % of a core.

## Re-plan 5 (14:43, PM) — PipeWire re-check every 15 s, not 5 s
After Re-plan 4 the daemon still used 0.42 % of a core: pw-dump output is ~180 KB of JSON, exec + parse every 5 s.
At 15 s: 0.13 % (6 ticks / 45 s, measured). Trade-off: a hidden app that STARTS playing is released within 15 s
instead of 5 s; its audio is not harmed meanwhile (25 % of a core is far above audio decode cost).

## Re-plan 6 (14:47, PM, from review2 — docs/focus/briefs/review2.out.txt)
- Show Desktop: KWin 6.7 does not expose it to scripts at all (w.hidden stays false, w.hiddenByShowDesktop is
  undefined — checked live). It IS on the bus: org.kde.KWin /KWin, property `showingDesktop` (b) and signal
  `org.kde.KWin.showingDesktopChanged(bool)`. → The DAEMON subscribes to that signal (and reads the property once at
  start); while showing, it plans as if every window had F=0 and Active=false (allow-list/audio exemptions still
  apply); on change it replans at once from the cached trees. The KWin script's `!w.hidden` stays (harmless).
- Wallpaper H3: never grab/freeze while the page is still loading; after a load finishes, wait 1 s (one Timer) so the
  first frame is painted before grabbing. M6: a URL change while frozen resets frozenShown/frozenGrab and sets Active
  so the new page loads, then the normal path re-freezes. LOW: revive (renderer crash) sets Active before reload.
- M7: the daemon reads pw-dump once at start so the first hidden app has a real audio map.
