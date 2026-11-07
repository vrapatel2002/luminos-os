# SPEC — luminos-focus (only what Shawn is looking at gets compute)
# [CHANGE: claude-code | 2026-11-07]
Design + measurements: docs/focus/DESIGN.md. Contracts: CONTRACTS.md. Log: BUILD_LOG.md.

## What he wants, in his words
"For putting pixels on screen there will mostly be one app at a time — the one that's on screen. The rest need no
compute unless they are working in the background or playing audio/video. … It should be at system level."
"One continuous dial, no modes. Prove every step with measured A/B numbers."
Order fixed by him: (1) measure minimize path, (2) wallpaper follows focus + 30 fps, (3) per-app CPU limits with
exceptions, (4) KWin occlusion patch — ASK before installing it or anything needing a reboot.

## This build round delivers (1)–(3). (4) is designed later and needs Shawn's yes.

### Part W — wallpaper (src/wallpapers/org.luminos.livewallpaper)
- New ObscurePolicy value 3 "only while you are looking at the desktop", made the default and set in Shawn's config.
  Plays when: Show Desktop is on, OR no task window on the current desktop+activity is active (he clicked the
  desktop, or everything is minimized/closed). Otherwise frozen on its current frame (existing freeze paths).
  Policies 0/1/2 keep their old meaning. PauseOnBattery unchanged.
- 30 fps cap whenever it does run: web mode throttles requestAnimationFrame to ≤ 30 calls/s (script injected at
  document creation, page code unchanged); Shader/ShaderToy scenes step iTime from a 33 ms Timer instead of a
  vsync NumberAnimation. Canvas scenes already tick at 33 ms. Video plays at its own rate (untouched).
- Lock screen: the greeter's wallpaper instance has no task windows → keeps playing (it is what he looks at).

### Part K — KWin script `luminos-focus` (config/kwin-scripts/luminos-focus, JS, no rebuild)
The one truth: KWin knows what is on screen. On any relevant change (window added/removed, activated, minimized,
geometry, stacking, desktop/activity switch, Show Desktop), debounced 250 ms, it computes per normal window:
visible fraction f ∈ [0,1] of its frame on its output after subtracting every normal, non-minimized, opaque window
stacked above it on the current desktop (minimized / other desktop / Show Desktop → 0), and whether it is the active
window. It sends one JSON snapshot via callDBus to org.luminos.Focus Update(string).

### Part D — daemon `luminos-focus` (Go, src/focus/, systemd --user unit)
Owns org.luminos.Focus on the session bus. For each snapshot: window pid → the app's process tree (pid + all
descendants) → the set of app.slice child units holding those processes (Chrome and Electron put their window pid
in a .scope and their renderer/GPU children in an @.service — both must be covered). Per unit, the best window of
that app wins. Target, one continuous dial (f = best visible fraction, focused = 1 forced up):
- focused: CPUWeight 1000, no quota.
- unfocused: CPUWeight = round(20 + 80·f); CPUQuota% = 25 + 1575·f, and no quota once that reaches 1600 (16 threads).
  So fully hidden = weight 20 + 25 % of one core; a sliver visible already gets more; half visible ≈ unlimited.
- EXCEPTIONS (treated as focused-unfocused-visible = weight 100, no quota): any process of the app owns a PipeWire
  stream in state running (audio/video playback or a call); unit name matches a glob in the allow-list file
  ~/.config/luminos/focus-allow.conf (one glob per line, # comments; default ships terminals, torrent/download
  clients, Steam/Lutris/Wine/gamescope, luminos-*).
- Raising rights applies at once (focus switch → full speed well inside 250 ms). Lowering glides over 2 s in 4 steps;
  a raise during a glide cancels it.
- Touches ONLY units directly under app.slice, never session.slice/system services, never its own unit.
  Properties are set runtime-only (vanish at logout). On start and on SIGTERM/SIGINT it resets every unit it set
  back to CPUWeight 100 + no quota.
- No polling while nothing is throttled. While ≥ 1 unit is held below weight 100 it re-checks PipeWire streams
  every 15 s (one pw-dump; Re-plan 5), so an app that starts playing while hidden is released within 15 s.
- If KWin's script is gone (no snapshot for 60 s while units are throttled) → release everything (fail open).

## Assumptions (gaps filled)
- "Focused" = KWin's active window; a different window of the SAME app counts for the app (per-app, not per-tab).
- Opaque = every normal window (KWin's opacity/blur is ignored; transparent terminals count as covering).
- quickshell/layer-shell bars, docks, OSDs, the desktop and notifications are not normal windows → never covering,
  never throttled.
- Multiple monitors: fraction is per window's own output geometry; works for one panel today.
- XWayland apps: same pid mapping (pid comes from KWin).
- Audio exception covers capture too (calls).
- Hidden cap of 25 % of one core is the starting value; tunable constant in one place.
- A crash of the daemon leaves runtime properties in place until restart/logout → the unit has Restart=on-failure and
  the start-up reset clears them.

## Blind spots → decisions
- Empty snapshot (no windows) → release all. Huge snapshot (100+ windows) → still one pass, O(n²) rects fine.
- Duplicate pids across windows → best window wins. pid 0 / unknown pid / process gone → skipped.
- Unit vanishes between read and set → error logged once, ignored.
- Bad JSON from the bus → logged, ignored, state unchanged.
- Non-ASCII captions → captions are never sent (not needed).
- Concurrent Update calls → serialised on one goroutine.
- Restart of daemon → reset on start; KWin script re-sends on next change and on a 30 s heartbeat only while the
  daemon's name is owned? → simpler: KWin sends on every change; daemon at start asks for nothing and waits.
  KWin heartbeat: resend the last snapshot every 30 s (cheap, one callDBus) so a restarted daemon catches up and the
  60 s fail-open rule has a pulse.
- Restart of KWin/plasma → script reloaded by KWin (enabled in kwinrc), sends a fresh snapshot.
- Game launched fullscreen and focused → focused → full rights. HIVE/training/system services are not in app.slice →
  never touched.

## Done means (plain words)
1. Step 1 measured and written down (BUILD_LOG + DESIGN): what minimizing really saves for Chrome and Claude.
2. Wallpaper: with any window focused, wallpaper CPU ≈ 0 and package power drops vs today; clicking the desktop
   brings the animation back; when it runs it draws ≤ 30 frames/s.
3. CPU: a hidden non-allow-listed busy app is held to ~25 % of a core; a hidden allow-listed one and a hidden one
   playing audio run at full speed; focusing any app gives it full speed within 250 ms.
4. Every claim above has an A/B number from tests/focus/measure.sh in BUILD_LOG.md.
5. Tests: unit/property tests for the dial, the rect maths and the process→unit mapping all pass; budgets met.
