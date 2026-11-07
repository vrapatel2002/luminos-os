# luminos-focus — only what you are looking at gets compute (steps 1–3 BUILT 2026-11-07 — see SPEC.md, BUILD_LOG.md, DECISION 174; step 4 not built)
# [CHANGE: claude-code | 2026-11-07]

## Shawn's rule (his words, 2026-11-07)
"For putting pixels on screen there will mostly be one app at a time — the one that's on screen. The rest need no
compute unless they are working in the background or playing audio/video. Keeping things in RAM compressed is one
thing, but the part where it's actually USING is what costs us the most. It should be at system level."
Standing rules that also apply: power is a continuous dial, not modes (feedback_continuous_not_phases); the dGPU stays
cold unless used; prove with measurements, not assertions; nothing not in use stays live.

## Measured today (2026-11-07 11:20-11:45, AC, Chrome + Claude open, windows NOT maximized)
- 20 s whole-system sample (% of one core): Chrome 34 (YouTube music video, visible), wallpaper 34 (plasmashell 17 +
  QtWebEngine renderer 17), Claude app 16 (active), KWin 8, ALL background services together ~3.
- Wallpaper frozen (SIGSTOP 20 s, 11-05): CPU package 8.1 W → 6.0 W, iGPU 27 % → 2 %. It animates at the panel's 120 Hz
  whenever ANY strip of desktop is visible, forcing KWin to recomposite the whole screen every frame and keeping the
  eDP panel out of PSR (panel self-refresh; psr_state 0 although sink + driver support it).
- YouTube with Ambient mode + auto quality: renderer 90 %, video decoder (VCN) 99 %, SoC 18 W avg; after Shawn set
  1080p + Ambient off + reload: renderer 20 %, VCN ~0, 13 W, Tctl 64 → 53 °C.
- Every GUI app already lives in its own systemd user scope: app.slice/app-com.google.Chrome-<pid>.scope,
  app-com.anthropic.Claude-<pid>.scope … → per-app CPU limits can be changed live (systemctl --user set-property).
- KWin 6.7.5 sends xdg_toplevel `suspended` + stops frame callbacks ONLY for minimized windows, other virtual desktops
  and the lock screen. A window merely COVERED by another keeps getting frame callbacks and keeps rendering
  (KDE bug 492924 "Buffers not released when window occluded", bug 467032 "Consider not sending frame callbacks to
  occluded windows" — open wishlist). UNVERIFIED: that Chromium/Electron honour `suspended` (expected: treat it as occluded,
  stop painting, background-video-track optimisation drops video decode, audio continues) — step 1 measures it.

## The design: one compositor-side truth, three levers
### 0. Truth source — KWin (it is the only component that knows what is really on screen)
A KWin script (QML/JS, no rebuild) publishing, per normal window: pid, app scope, focused, minimized, fully covered
(computed from stacking + geometry of opaque windows above it on the same output), visible fraction, on current
desktop; plus "desktop is what the user is looking at" (no focused normal window, or Show Desktop). Published on the
session bus (org.luminos.Focus) on every change, debounced 250 ms.
### 1. CPU lever — per-app cgroup limits (no compositor change needed)
A small user daemon (luminos-focus, Go or Python stdlib) maps state → systemd scope properties, as a CONTINUOUS
weight, not modes:
- focused app: CPUWeight 1000, no quota;
- visible but unfocused: CPUWeight 100, no quota;
- fully hidden / minimized / other desktop: CPUWeight 20 + CPUQuota ~25 % of one core;
- EXCEPTIONS that keep full rights while hidden: app has an active PipeWire playback/capture stream (audio/video
  call, music), app is in a user allow-list (e.g. terminals running a build, torrent/download apps, games launched
  via game mode), app is doing a foreground-requested job (luminos-gpu-yield/train-mode hooks);
- transitions glide over ~2 s (no flapping); never touches session/system services or kwin/plasmashell.
### 2. GPU / frame lever — stop hidden windows drawing
Phase A (no patch): minimized/other-desktop already suspended by KWin → nothing to do; measure Chrome/Electron really
stop (renderer + GPU process + VCN) when minimized.
Phase B (KWin patch, DKMS-style local package like the existing forked KDE libs, DECISION 140 pattern): mark FULLY
occluded windows `suspended` and stop their frame callbacks (exactly what KWin upstream plans); optional: throttle frame
callbacks for visible-but-unfocused windows to 30 Hz. Upstream-quality patch, kept tiny, rebuilt on every kwin bump
with a pacman hook that warns (like luminos-kirigami.hook).
### 3. Wallpaper — follows the same truth
org.luminos.livewallpaper gets its "play" signal from org.luminos.Focus: animate only while the desktop is what the
user is looking at; otherwise freeze on the current frame (Lifecycle Frozen — already implemented for the occlusion
policy), and cap its frame rate at 30 fps when it does run. The lock screen keeps animating (it IS what you look at).

## Done means
- With Chrome (YouTube playing music) covered by a focused Claude window: Chrome's renderer + GPU process ≤ 5 % and
  VCN 0 % (video not decoded), audio still plays; uncover → video resumes within 0.5 s.
- Idle desktop with windows open: wallpaper ≤ 1 % CPU, package power ≥ 2 W lower than today (8.8 W → ≤ 6.8 W), panel
  PSR active when nothing changes.
- A hidden terminal compile in the allow-list still runs at full speed; a hidden non-allow-listed app is capped.
- No visible regression: focus switch → the app is back to full speed within 250 ms; games/HIVE/training unaffected.
- Every number measured A/B (RAPL energy_uj, /proc/*/stat, amdgpu_pm_info VCN/GPU load, psr_state).

## Order (cheapest proof first)
1. Measure Phase A (minimize test with a playing video) → proves the `suspended` path works for Chrome/Electron.
2. Wallpaper on the focus signal + 30 fps cap (biggest single win, no compositor patch).
3. CPU lever daemon + exceptions.
4. KWin occlusion patch (Phase B) — only after 1-3 are measured, with an upstream-style patch and review.
