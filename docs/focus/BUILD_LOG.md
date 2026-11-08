# BUILD_LOG — luminos-focus
# [CHANGE: claude-code | 2026-11-07]
Instruments (PM-owned): tests/focus/measure.sh (RAPL pkg power, iGPU busy, VCN load, PSR, CPU % of one core per
app cgroup + top pids), tests/focus/kwin-eval.sh (one-shot KWin script, prints its output), tests/focus/phaseA.sh.
Raw logs: /var/tmp/focus-phaseA-1345.log, /var/tmp/focus-a5.log … focus-a8.log, /var/tmp/focus-b.log.

## 13:44–13:58 STEP 1 — does a hidden window stop costing compute? (AC, YouTube music video in a 2nd Chrome window,
audio stream muted at the PipeWire level so Chrome can't tell; Claude window on top; 20 s samples)
| state of the video window                | Chrome total | Chrome GPU proc | Chrome renderer | VCN  | pkg W |
|------------------------------------------|-------------:|----------------:|----------------:|-----:|------:|
| A1 focused + visible                     | 34.7 %       | 12.1 %          | 19.8 %          | 31 % | 17.4  |
| A2 COVERED by Claude (not minimized)     | 33.9 %       | 12.0 %          | 18.8 %          | 20 % | 17.2  |
| A3 MINIMIZED (KWin sends `suspended`)    | 15.6 %       |  2.7 %          | 10.1 %          | 21 % | 15.8  |
| A3b minimized, 2nd run                   |  8.8 %       |  —              |  —              |  5 % | 15.7  |
| A4 restored                              | 31.5 %       | 12.2 %          | 18.1 %          | 20 % | 17.1  |
Claude app (B): renderer+GPU unit 25.4 % visible → 5.1 % minimized.
Findings:
1. COVERED costs exactly as much as visible (A2 ≈ A1). Confirms DESIGN: KWin 6.7.5 keeps frame callbacks for
   occluded windows. This is the case the Phase-B KWin patch would fix.
2. MINIMIZED works for both Chromium and Electron: painting stops (Chrome GPU process −78 %, renderer −49 %,
   Claude renderer/GPU −80 %), audio keeps running (stream stayed `running`), restore is instant.
3. Video DECODE mostly does NOT stop when minimized: VCN duty stayed the same in 2 of 3 runs (one run it stopped
   after ~25 s — Chrome's background-video-track optimisation is not reliable for YouTube/MSE). So the remaining
   renderer cost of a hidden playing video is decode + JS; the CPU lever caps the rest, an audio-playing app is
   exempt by design. VCN duty is small (1080p/360p decode ≈ 5–10 % duty) — the big costs are painting + compositing.
4. NEW, important for the CPU lever: the Cowork VM (qemu + virtiofsd) and every process the desktop app's
   host-shell starts (incl. these /build workers: 87 % in B2) live in app-com.anthropic.Claude-<pid>.scope, while
   Claude's renderer/GPU live in app-com.anthropic.Claude@….service. → the scope is allow-listed, the @service is
   throttled. Chrome likewise: window pid 2869 in app-com.google.Chrome-2869.scope, renderer/GPU children in
   app-google\x2dchrome@….service → the daemon must map the whole process tree, not just the window pid.
5. The wallpaper (plasmashell 16 % + QtWebEngine 13 %) kept animating in EVERY sample — windows are not "maximized"
   by flag (1396×900 tiles), so ObscurePolicy 2 never fires. Biggest single waste on screen right now.
6. VCN load from amdgpu_pm_info is an instantaneous 0/100 sample; fdinfo drm-engine-enc is updated lazily and
   double-counts across fds → use many pm_info samples (duty) for VCN, not fdinfo.

## 13:58 Spec + contracts written (SPEC.md, CONTRACTS.md). Plan: 3 Opus-high workers in parallel —
wg (Go daemon), wk (KWin script + wallpaper), wt (tests from spec only) — then static checks, Fable review against the
real source, install the no-reboot parts (KWin script, wallpaper, user unit), live A/B. Phase B (KWin patch) only
after Shawn says yes.
- 14:02 wk done (KWin script 121 lines, wallpaper +65 lines; rAF 30 fps cap verified in a simulated 120 Hz loop;
  qmllint no new warnings). 14:05 wg done (591/600 Go lines, build/vet/gofmt clean, godbus made direct by hand,
  go.sum already had it). Their open questions folded into CONTRACTS Re-plan 1 (f denominator = whole frame, etc.).
  Checked myself: pw-dump gives application.process.id as a JSON number (wg's assumption holds).
- 14:12 wt done: 6 Go test files (examples + testing/quick properties, fake /proc incl. Chrome scope/@service split,
  cycles, vanished pids), node tests with a pixel-count reference, static.sh. Only failure: f denominator (the
  ambiguity) → round 2 made tests strict to Re-plan 1, added own-unit test and a self-test proving the func-length
  check catches a 41-line func. 14:14 tests/focus/static.sh: 9/9 PASS (go vet, go test, node --test, gofmt, budgets).
- 14:19 review1 (Fable high, verified live against the process tree + godbus source): VERDICT safe to install;
  HIGH H1 focus raise waited for the 250 ms debounce; MEDIUM M1 stale heartbeat defeats fail-open, M2 pw-dump error
  dropped the audio exemption, M3 focused dialog = app unfocused, M4 plain user services in app.slice
  (luminos-hive, claude-cowork…) reachable + not reset, M5 installer didn't restart a running daemon. → Re-plan 2:
  only app-* units are ever touched; H1/M1/M3 → wk, M2/M4 → wg, tests → wt, M5 + uninstall `|| true` → PM (done).
- 14:20 round 2 done (wk H1/M1/M3, wg M2/M4 app-* only, wt tests) → static.sh 9/9 PASS.
- 14:20 WALLPAPER INSTALLED (rsync to ~/.local/share/plasma/wallpapers, ObscurePolicy 2→3 via evaluateScript,
  plasmashell restarted). Live A/B, policy 2 vs 3 alternated ×2 (Claude active, wallpaper behind tiled windows):
  NO DIFFERENCE (plasmashell 18–21 % both). Debug lines in the installed copy showed policy 3 works
  (windowActive true → shouldPlay false) but journal: "setLifecycleState: failed to transition from Active to
  Frozen state: page is visible" — QtWebEngine only freezes INVISIBLE pages, so the web wallpaper's freeze has
  NEVER worked (pre-existing bug since the 07-24 occlusion policy; explains DESIGN's "wallpaper always animates").
  Side note: with the 30 fps cap the running wallpaper is 18–21 % (plasmashell+renderer) vs 29–33 % before
  (A1–B1 samples) — first evidence the cap works; clean A/B after the freeze fix. → wk round 3: grab last frame,
  hide the view, then Frozen.
- 14:22 wk round 3: WebMode grabs the current frame into an Image, hides the view, then sets Frozen (1 s fallback
  freezes without the picture; async grab guarded against flips; grab released on resume). +39 lines.
- 14:24 KWin script + daemon INSTALLED (go build → ~/.local/bin/luminos-focus, user unit enabled,
  kpackagetool6 -i, kwinrc luminos-focusEnabled=true). Two live-only bugs, PM-fixed in main.js (Re-plan 3):
  script died at load — KWin 6.7 has no workspace.showingDesktop/showingDesktopChanged/stackingOrderChanged (→
  per-window stackingOrderChanged + hiddenChanged, w.hidden for Show Desktop); quickshell overlays (44 px bar,
  1396×900 transparent layer) are normalWindow=true, skipTaskbar=true and counted as covering → every app looked
  hidden (→ filter normalWindow && !skipTaskbar). After the fix the hidden Chrome got f=0.03 (its 44 px strip).

## LIVE A/B — CPU lever (14:26, /var/tmp/focus-cpu-ab.log)
| case                                                        | CPU of the app's unit | cgroup cpu.max      |
|-------------------------------------------------------------|----------------------:|---------------------|
| C1 busy page in Chrome, Chrome FOCUSED                      | 92 %                  | max                 |
| C2 same, Chrome COVERED by Claude (other Chrome window shows a 44 px strip → f 0.03) | 73 % | 74000/100000 (dial = 25+1575·0.03 = 74 %) |
| C3 refocus Chrome → quota lifted                            | ≤ 442 ms incl. ~400 ms of the test's own kwin-eval overhead | max |
| C4 allow-listed konsole running `yes`, COVERED              | 99 %                  | max, weight 100     |
Fully hidden app (f 0) seen live before the strip fix: Chrome weight 20, CPUQuotaPerSecUSec=250ms (25 % of a core).
Claude: scope (VM + host-shell + these workers) stays exempt/1000; only Claude@….service is dialled.

## LIVE A/B — wallpaper (jellyfish web wallpaper, AC, Claude active; 10–20 s samples)
| state                                              | pkg W | iGPU busy | plasmashell + renderer |
|----------------------------------------------------|------:|----------:|-----------------------:|
| before (W1–W3: running; old freeze refused by Qt)  | 12.9–14.8 | 14–19 % | 18–24 %              |
| S1 Show Desktop ON → plays (30 fps cap)            | 13.5  | 20 %      | 25 %                   |
| W4/X1/X2 policy 3 + grab-freeze, window active     | 12.2–12.3 | 4 %   | < 0.3 % (not listed)   |
| S2 Show Desktop OFF → frozen again                 | 12.0  | 4 %       | < 0.3 %                |
Freeze → −1.3…−1.5 W package, iGPU 20 → 4 %, ~¼ of a core freed; no "failed to transition" lines any more; resume
via Show Desktop works. 30 fps cap: running cost 29–33 % (morning samples, pre-cap) → 25 % (S1) — small; the
jellyfish page's own JS dominates. PSR stayed 0 in every sample: something else still repaints (Claude streaming
this build's output, bar clock) — must be re-measured with Shawn idle. Live policy changes through
evaluateScript writeConfig do NOT reach a running wallpaper (needs plasmashell restart) → A/B arms were taken
across restarts / via Show Desktop instead.
- 14:37 daemon self-cost measured 1.5 % of a core (300 ms CPU / 20 s) — /proc thread walks, not pw-dump (9 ms). Re-plan 4 → wg round 3 (cache process trees per Update).
- 14:40 wg round 3 (trees cached per Update; re-check never walks /proc): daemon 1.5 % → 0.42 % of a core.
  14:43 PM Re-plan 5 (re-check 15 s): 0.13 % of a core (measured over 45 s, incl. start-up). static.sh 9/9.
- 14:44 review2 (Fable high): review1 findings all closed; H2 Show Desktop not detected (KWin 6.7 exposes it only on
  D-Bus, checked live), H3 wallpaper froze before its first paint after plasmashell start (grabbed a blank page;
  live evidence 14:27–14:30), M6 URL change while frozen, M7 first pw-dump. → Re-plan 6, worker wfix (12th and last
  spawn of this round) gets both Go + WebMode fixes.
- 14:48 wfix (Re-plan 6) done; static.sh 9/9; daemon 600/600 lines. Installed: daemon rebuilt + restarted, wallpaper
  re-synced, plasmashell restarted. Live: page loads and PAINTS first (H3 fixed — plasmashell restart gives the
  desktop focus, so it correctly plays); activating Claude → "applyState play=false … freeze grab=yes" → iGPU 4 %,
  wallpaper gone from the CPU list (F2). Show Desktop → daemon sets every app f=0 (Claude renderer 20/25 %), Show
  Desktop off → focused 1000 at once.
- Step 9 strip pass: no unused non-test functions (Plan/UnitsForApp are contract API used by tests); budgets at the
  limit (Go 600/600, main.js 135/150, wallpaper ~+104/−18 incl. Re-plan 6 fixes — over the 90-line wallpaper budget
  set in CONTRACTS because the freeze bug (BUG-229) was not known when it was set; accepted, logged here).
- Spawns used: 12/12 (wg, wk, wt, wt2, review1, wg-r2, wk-r2, wt-r3, wk-r3, review2, wg-r3, wfix).

## Where it stands (14:52)
DONE + LIVE: steps 1–3. NOT DONE: step 4 (KWin occlusion patch) — waiting for Shawn's yes. Open measurements:
idle-desktop PSR + package power with Shawn away (target from DESIGN: 8.8 → ≤ 6.8 W).
- 2026-11-07 16:04-16:15 IDLE MEASURE (Shawn away, AC, 100 % battery, brightness 399000 = 100 %, only Claude + Chrome open; /var/tmp/idle-measure/report-20261107-1602.txt):
  wallpaper FROZEN (16:05-16:10): pkg 11.2-11.4 W, iGPU 0-1 %, wallpaper CPU 0.03 %; wallpaper PLAYING (16:11-16:15, desktop
  took focus): pkg 12.0-12.6 W, iGPU 12 %, wallpaper ~19 % of a core (30 fps cap works: was ~34 %). Freeze saves ~1.3 W (matches the
  focus build's 1.3-1.5 W). PSR stayed 0 in every sample. BUT the whole idle baseline is ~3 W HIGHER than 11-05 (8.1-8.8 W) with
  less CPU in use (~30 % of a core total), Tctl 57-63 °C (was ~43-47), VDDNB 835 mV (was 714 mV), dGPU suspended, Cowork VM running
  (qemu 1.7 %). Cause NOT found yet — suspects: data-fabric/memory kept up (VDDNB), heat soak after the build, the Cowork VM's
  timers keeping cores out of deep idle. Next: repeat with the Claude app closed, then with the Cowork VM stopped.
- 2026-11-08 Shawn: wallpaper must stay LIVE whenever any part of it is visible; freeze only when one app fully covers
  the desktop; and the paused frame looked low-res. Changes: ObscurePolicy default 3 → 2 (config/main.xml) + live desktop
  config set to 2 via plasmashell evaluateScript; WebMode.qml grabs the freeze frame at device pixels (Screen.devicePixelRatio,
  2x panel) instead of logical size. Deployed (backups *.bak-pre-20261108), plasmashell restarted. Proven
  (/var/tmp/wp-policy-test.log): Claude window restored (desktop partly visible) → wallpaper 30 % of a core, iGPU 37 %
  (live); Claude maximized → 0-5 %, iGPU 10-14 % (frozen). The CPU-dial daemon is unchanged.
