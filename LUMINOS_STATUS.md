# Luminos OS — System Status
Last updated: 2026-08-04
Agent: claude-code (DECISION 41 — **the stock Caelestia Hyprland config is now adopted verbatim, with Luminos hardware settings moved into override files.** `~/.config/hypr/` is a byte-for-byte copy of upstream `caelestia-dots/caelestia`'s `hypr/` tree so `caelestia update` can never conflict; everything machine-specific lives in `~/.config/caelestia/hypr-vars.lua` (values: kitty/dolphin/chrome/Yaru/`systemctl suspend`) and `~/.config/caelestia/hypr-user.lua` (behaviour: the `AQ_DRM_DEVICES` iGPU pin, `QT_QPA_PLATFORMTHEME=kde`, eDP-2 @ scale 2, polkit-kde + session-recorder autostarts), which `hyprland.lua` requires LAST so it always wins. This was the real answer to "many things are missing": the hand-written 180-line `hyprland.conf` had **20 binds against upstream's ~140**, and critically **none of Caelestia's 22 Wayland global shortcuts were wired** — `caelestia-shell` registers `caelestia:launcher`, `:sidebar`, `:lock`, `:screenshot`, media and brightness, then waits for the compositor to fire them, so the launcher, sidebar, lock screen and screenshot tools existed but were unreachable. Proven in a **nested session at zero risk to the live one**: `configProvider: lua`, 140 binds, 0 errors. Titlebars deliberately left as-is (no hyprbars) — Caelestia has none by design and the user confirmed the current look is exactly what he wants. **NOT adopted:** Caelestia's GTK/Qt/Firefox/VSCode/Discord theming, which would destroy the Yaru/KDE look from BUG-088/090. 🟥 Upstream `execs.lua` runs `trash-empty 30` at every login, which would have permanently deleted **8.9 GB / 31 of 43 trash items including `LUMINOS_MASTER_FILE.md`, `AGENT_HANDOFF.md` and `conversations.json`** — neutralised by removing `trash-cli` rather than editing upstream; do NOT reinstall it before rescuing the trash. BUG-094 FIXED **AND VERIFIED ON A REAL LOGIN (2026-08-04 16:32)** — Hyprland is live on the AMD iGPU with Claude Desktop running as a native Wayland window and the dGPU still asleep. The failure it fixed: the session bounced back to SDDM in ~2 s, three times, SIGABRT with `CBackend::create() failed!`, because `AQ_DRM_DEVICES` is a **colon-separated list** and the iGPU pin had been written as a PCI by-path (`/dev/dri/by-path/pci-0000:65:00.0-card`) — full of colons — so aquamarine split one device into three nonexistent ones, discarded the AMD card it had *already* enumerated as KMS-capable, and aborted. Neither stock name works alone: by-path is stable but has colons, `cardN` is colon-free but is enumeration order and NVIDIA is card1 here. Fixed with a colon-free udev alias `/dev/dri/luminos-igpu` matched on PCI address (`/etc/udev/rules.d/99-luminos-gpu-alias.rules`), plus a negative-tested `readlink -f` fallback in `uwsm/env-hyprland`. Two diagnosis traps recorded: aquamarine enumerates *every* DRM device before applying the pin, so `NVRM: nvAssertFailedNoLog` appears in the journal regardless and is NOT evidence the compositor took the dGPU; and **an agent shell started under the old Plasma session keeps `XDG_CURRENT_DESKTOP=KDE` forever** — I read my own environment and wrongly told the user the login had never succeeded while he was reading the reply inside Hyprland. Ask the system (`pgrep -a Hyprland`, `loginctl list-sessions`, `hyprctl instances`, `/proc/<pid>/environ`), never your own env. DECISION 39 + 40 — **Hyprland and Caelestia Shell are installed.** `hyprland 0.56.1-3`, `quickshell-git`, `caelestia-shell 2.2.0-1`, `caelestia-cli 1.1.2-1`. Hyprland is an **opt-in second SDDM session; KDE Plasma remains the default and is untouched.** The whole stack was proven in a **nested session inside live Plasma — no logout, no risk**: bar, live system tray, clock, wifi/bluetooth/battery icons, power button, and **Claude Desktop running as a native Wayland window on the AMD iGPU with no escape hatches needed**, which was the user's hard acceptance criterion. The three things the nested test could not exercise — `AQ_DRM_DEVICES` GPU pinning, dGPU sleep, and panel scaling — were all **proven on the real login of 2026-08-04 16:32**. **`power-profiles-daemon` came in as a hard dep of caelestia-shell and is now permanently MASKED** — it and `asusd` both write `/sys/firmware/acpi/platform_profile`, and the entire thermal stack assumes asusd is the sole writer; masked rather than disabled because that also blocks D-Bus activation, and it was negative-tested with a real activation request. Known cost: Caelestia's battery power-profile buttons do nothing — accepted, since profile switching belongs to asusctl/luminos-power. BUG-093 FIXED — a shadowing user-site `packaging 26.0` made pacman and Python disagree about versions and broke every AUR python build; fixed with `PYTHONNOUSERSITE=1`, deliberately removing nothing from the 301-package user-site the MCP tooling depends on. BUG-092 FIXED — the SDDM greeter wallpaper pointed at a missing file under `$HOME` that the `sddm` user could never have read anyway; the black login screen it produced was misreported as a Hyprland crash, when Hyprland had never been launched.)
Prev: 2026-08-02
Agent: claude-code (BUG-091 FIXED / DECISION 38 — the G14 never slept on lid close or on idle. Not a suspend bug: a controlled `rtcwake -m freeze -s 30` reached s0i3 and resumed clean BEFORE anything was changed, and the 2026-08-01 "suspend loop" in the journal was upowerd's critical-battery suspend plus the user repeatedly opening the lid. The real cause was three deliberate layers from commit f8e00ab0 (2026-06-03, "keep all processes running on lid close, screen off only"): logind HandleLidSwitch*=ignore, PowerDevil lidAction=0, and a udev rule that blanked the panel via kscreen-doctor instead of sleeping — plus no idle-suspend setting at all on either profile. Reversed at the user's request: lid = Sleep on AC and battery, idle-suspend at KDE's own shipped defaults (900/600/300 s, read out of the binary rather than invented). **The expensive part was a silent no-op:** the first fix wrote LidAction=1 to `~/.config/powerdevilrc` under a bare `[AC]` group. PowerDevil opened the file — proven with inotifywait — and ignored the value, because ProfileSettings registers its items against the `[AC][SuspendAndShutdown]` subgroup. `powermanagementprofilesrc` is legacy and no longer read for this at all. Settled by driving the live daemon: HandleButtonEvents.lidAction returned 1 → 2 → 0 → 1 as the config changed. Its sibling triggersLidAction() would have reported success for every wrong config tried — caught only by negative-testing.)
Prev: 2026-07-25
Agent: claude-code (BUG-085 FIXED / DECISION 33 — agent MCP tooling was silently rotting. Neither tool was crashed: both answered a handshake, which is why nobody noticed. Six defects: (1) BOTH hooks had never run once — they called bare `code-review-graph`, but hooks get a non-interactive shell with PATH=/usr/local/bin:/usr/bin and `~/.local/bin` is only added by ~/.zshrc; (2) MemPalace was registered TWICE under one name across `.mcp.json` and `~/.claude.json`, pointing at two different installs, and local scope won — so the live server was an unintended v3.1.0 while docs described v3.3.1; (3) that one was an EDITABLE install, so a `git pull` in ~/mempalace silently changed the running server — the literal cause of "we add things and it breaks"; (4) a THIRD MemPalace lived in a shared 301-package user-site on Arch's ROLLING python; (5) code-review-graph's shebang was `#!/usr/bin/python3`, one pacman bump from vanishing; (6) 5,951 stale lock files. Fix: one tool → one pyenv-3.12.13 venv, pinned, never editable; single authoritative `.mcp.json`; absolute paths in hooks; locks reaped 5951→0. Durable part: `luminos-verify --mcp` does a REAL MCP handshake and hard-fails on all six modes — each negative-tested by reintroducing the fault. Also fixed `--quiet` printing NOTHING, which made a FAIL look identical to a PASS. **Found in passing: BUG-086 — a live OpenRouter API key is committed AND pushed to GitHub in `.claude/settings1.json`; needs rotation, user action.**)
Prev: 2026-07-01
Agent: claude-code (Monitor made light + BUG-078 FIXED: Meta+M/Ctrl+M now open `luminos-monitor watch` (bash loop) instead of konsole+btop (saves ~55M unique RAM + ~5% CPU per window). Root-caused dGPU-never-sleeps: nvidia-smi polls (powerwidget 5s, monitor 2s) each take a runtime-PM ref — replaced with side-effect-free runtime_status reads; monitor v1.2/1.3 sleep-guard shows SLEEP/0W without waking GPU. New org.luminos.monitorwidget (panel popup, feeds on `luminos-monitor stats`) installed + added to panel; powerwidget tokenized version deployed (installed copy was stale since May 21). NOTE: forex bot CUDA mmap + nvidia-powerd still hold GPU awake — 0W/D3cold reachable only when those exit.)
Prev: 2026-06-30
Agent: claude-code (Foreign-toolkit light/dark cohesion ROOT-CAUSED + fixed, no daemon. The desktop's 3-way light/dark disagreement traced to ONE bad value: GTK theme name was `Breeze-Dark` (a permanently-dark theme that ignores the prefer-dark flag) instead of `Breeze` (the adaptive theme). KDE's built-in kded `gtkconfig` already syncs the prefer-dark flag + xdg portal to the active Plasma color scheme — but a fixed-dark theme name overrode it, so the flag and the theme contradicted each other. Fix = `gtk-theme-name=Breeze` everywhere. Now KDE color scheme is the single source of truth; Qt/GTK/Electron/Chromium/Flatpak all follow it natively. Verified round-trip light<->dark with no extra process. Daemon experiment removed.)
Prev: 2026-06-14 (UI cohesion: single token source `design/luminos-tokens.json` + `scripts/luminos-theme-gen` generator + `src/theme/Theme.qml`; power/ram widgets + HIVE refactored off hardcoded hex; BUG-071 fixed. SCAFFOLDED repo-only. Decision 21)
Prev: 2026-06-13 (BUG-070 FIXED — training OOM root-caused to zram-only swap; reversible `luminos-train-ram` toggle. Decision 20)

## System
| Component | Status | Notes |
|---|---|---|
| Arch Linux base | ✅ Working | Triple boot G14 |
| KDE Plasma 6.6.4 | ✅ Working | Wayland session |
| SDDM | ✅ Working | Defaults to Plasma Wayland |
| Hyprland 0.56.1 + Caelestia Shell 2.2.0 | ✅ Working (opt-in 2nd session) | Real login proven 2026-08-04 16:32 with Claude Desktop native Wayland on the iGPU. Pinned to the iGPU via `AQ_DRM_DEVICES=/dev/dri/luminos-igpu` (colon-free udev alias — BUG-094). Config = upstream Caelestia verbatim in `~/.config/hypr/`; all Luminos settings in `~/.config/caelestia/hypr-{vars,user}.lua` (DECISION 41). Plasma remains the default session and is untouched. `power-profiles-daemon` MASKED, so Caelestia's power-profile buttons are inert by design (DECISION 40) |
| Window management (float + titlebars) | ✅ Working | [CHANGE: claude-code \| 2026-08-05] DECISION 45. Every app opens **floating** (catch-all `hl.window_rule` in `hypr-user.lua`) instead of dwindle-tiling left/right; `SUPER+ALT+Space` still tiles on demand. Titlebars with minimize/maximize/close come from the **hyprbars** plugin, set up in `~/.config/caelestia/hypr-bars.lua`; buttons shell out to `luminos-win`. `SUPER+ALT+M` restores minimized windows. **`min` needs two dispatches** — moving to a special workspace also opens it, and `silent = true` is accepted and ignored because dispatcher tables are not validated. Button colours are hardcoded: the scheme's `red`/`green`/`yellow` are wallpaper-harmonised (`red` was purple). **Upgrade hazard:** hyprbars is compiled and pinned `hyprland <0.57.0`; rebuild it in the same transaction as any Hyprland upgrade. The `require` is `pcall`-wrapped so a stale plugin costs titlebars, not the whole session |
| Look tuner (`luminos-look`) | ✅ Working | Live A/B testing of the Hyprland look. 6 presets (caelestia/soft/glass/sharp/chunky/performance) + a Quickshell slider dashboard, `SUPER+SHIFT+T`. Preview writes nothing; `hyprctl reload` is the undo. Persists to `~/.config/caelestia/hypr-look.lua`, merged by `hypr-vars.lua` so a save can never clobber hand-written settings. **Applies via `hyprctl eval` — `hyprctl keyword` is a silent no-op under the Lua parser and still exits 0** |
| NVIDIA 595.71.05 | ✅ Working | nvidia-dkms (Arch native — no Ubuntu dependency) |
| AMD iGPU (Radeon 780M) | ✅ Working | Desktop rendering + KWin compositor |
| RTX 4050 6GB | ✅ Working | HIVE AI models + gaming (power-gated when idle) |
| asusctl + supergfxctl | ✅ Working | Hybrid mode locked |
| Keyboard backlight | ✅ Working | Enhanced KDE KCM (7 modes) + Smart power daemon |
| NPU (RyzenAI-npu1) | ✅ Working | /dev/accel0 active |
| Display VRR | ⚪ Disabled | VRR=Never (user intentional — reverted from Automatic) |
| Display sharpness | ✅ Active | KWin sharpness=0.35 (AMD display pipeline, all content) |
| Display Hz toggle | ✅ Available | luminos-display-hz in KDE Settings; luminos-60hz / luminos-120hz scripts |
| UI design tokens | 🛠 Scaffolded (not applied) | Single source `design/luminos-tokens.json` → `scripts/luminos-theme-gen` → `Theme.qml` (QML), `Luminos.colors` (KDE), `gtk.css` (GTK/libadwaita). Widgets+HIVE tokenized. Apply post-training. Decision 21 |
| Light/dark cohesion | ✅ Fixed (no daemon) | Root cause: GTK name was `Breeze-Dark` (always-dark, ignores prefer-dark flag) → contradicted KDE's auto-synced flag. Fix: `gtk-theme-name=Breeze` (adaptive). KDE color scheme = single source of truth; GTK + portal + Electron/Chromium/Flatpak follow natively via kded gtkconfig. Flip in System Settings → Colors |
| Big-LLM weight-offload | ✅ Working (Phases 0-5) — 10.4B runs on 6GB, coherent text | Runs the 10.4B HOPE model on the 6GB 4050 by parking 4-bit weights in RAM + streaming layer-by-layer. Engine `hope-llm/src/offload_engine.py` (StreamedLinear/ChunkedStreamedLinear + shared StagingPool + mmap quantize + OffloadSession daemon coord); runner `scripts/offload_run.py`. **Full real run generates coherent text** ("The capital of France is Paris…"). Throughput tuned via `--resident-gb` (keep hot 4-bit layers GPU-resident, since the run is PCIe-transfer-bound): **~3.07 tok/s @ 2.0GB resident (4.31GB VRAM)** vs ~2.0 all-streamed (2.18GB VRAM). Bugs fixed this run: head OOM (chunked head), wrong tokenizer (GPT-2→Qwen3), single-token decode degenerates (use `--refeed`) — see BUGS.md 075-077. Remaining: daemon-coordinated run (root socket perms) + Phase 6 throughput tuning. See docs/LUMINOS_OFFLOAD_ARCHITECTURE.md, DECISION 23 |

## HIVE Roster (2026) — April Upgrade
| Alias | Model Base | Target | Role | Status |
|---|---|---|---|---|
| **Nexus** | Dolphin3-Llama3.1-8B | GPU | Coordinator (Uncensored) | ✅ Active (36.3 TPS) |
| **Bolt** | Qwen2.5-Coder-7B | GPU | Expert Coder | ✅ Active (38.6 TPS) |
| **Nova** | DeepSeek-R1-0528-8B | CPU/GPU | Deep Thinker | ✅ Active (10.3 TPS CPU) |
| **Sentinel**| MobileLLM-140M | NPU | OS Security | 📋 Pending fine-tune (deliberate — model held back until custom training; no NPU service running. NPU hw/driver verified ✅) |
| **Eye** | Qwen2.5-VL-7B | GPU | Vision | 📋 Pending |

## Max Speed Geometry (G14/4050)
- **Full-GPU Threshold:** < 8.5B parameters (Q4_K_M)
- **Safe VRAM Buffer:** 4.6 GB
- **VRAM/RAM Split Penalty:** -1.8 TPS per offloaded layer
- **Peak Performance:** 38.6 TPS (Qwen2.5-Coder-7B Q4 100% GPU)

## AI Stack
| Component | Status | Notes |
|---|---|---|
| HATS + triton-xdna | ⚪ Verified 2026-04, not in production | xclbin compile proof in ~/.triton/cache; no daemon consumes it yet (Phase 3). luminos-npu.service / luminos-classifier.service from AGENTS.md §3 were never created. |
| MobileLLM-R1-140M INT8 | 📋 Pending fine-tune | 64MB quantized weights on disk; deliberately not deployed until custom Sentinel training done |
| VRAM Watchdog | ✅ Working | Auto-evict if >90% usage |
| llama.cpp TurboQuant | ❌ Broken | [CHANGE: claude-code \| 2026-08-04] BUG-097. `/usr/local/bin/llama-server` has 7 unresolved `DT_NEEDED` libs; `libggml-cuda.so.0` exists nowhere on disk. The venv was refreshed 2026-05-09 to a CPU-only ggml 0.10.2, so the CUDA build the Apr-24 binary links against is gone. **No model can load.** Needs a CUDA rebuild, or a switch to `llama_cpp.server`. |
| HIVE Idle Watchdog | ✅ Working | Auto-unloads models after 5 mins |
| HIVE Orchestrator (orchestrator.py) | 🛠 Retired | Superseded by hive-daemon.py. luminos-hive.service updated + disabled. |
| llama.cpp Python | ✅ Installed | v0.3.20 (system package) |
| HIVE Swap Server | 🛠 Retired | Port 8079 functionality merged into HIVE Daemon |
| HIVE Daemon | ✅ Working | Port 8078. [CHANGE: claude-code \| 2026-08-04] Lifecycle is now **systemd's**, not the popup's — `luminos-hive.service` enabled + started under Hyprland. The popup no longer forks or kills it. `/health` verified. |
| HIVE Web Search | ✅ Working | DuckDuckGo HTML scraping, no API key. Works without llama-server loaded. Auto-routes via [ROUTE:WEB] or keyword detection. |
| HIVE popup (SUPER+SPACE) | ✅ Working (UI only) | [CHANGE: claude-code \| 2026-08-04] Rebound under Hyprland in `hypr-user.lua` (was kglobalaccel). Runs `qml6 src/hive/HiveChat.qml` — 1 process / 265 MB, vs 5 processes / 604 MB for the retired PyQt6+QWebEngine path. Toggle fixed (BUG-096) and proved over 4 presses. **Chat will not answer until BUG-097 is fixed** — the window opens, the backend has no model. |
| Claude Code Router | ✅ Working | DeepSeek V4 Pro via OpenRouter. Key in .env, config in .claude/settings.local.json |
| luminos-notes.sh | ✅ Working | SQLite knowledge base. Complements MemPalace (which is NOT retired — see below); AGENTS.md §8 says search both. |
| MemPalace (MCP) | ✅ Working — pinned v3.3.1 | **NOT retired** (the old "hnswlib crash" note was stale). Registered in **user scope** `~/.claude/settings.json` (Cowork ignores project scope) **plus** Claude Desktop and Antigravity, all pointing at one binary `~/.mempalace-venv` (pyenv 3.12.13). 29 tools, 2.0 GB store at `~/.mempalace/palace`. Was silently running an unintended editable v3.1.0 for months — BUG-085 / DECISION 33; reached only one of three clients until BUG-087 / DECISION 34. Check: `luminos-verify --mcp` |
| code-review-graph (MCP) | ✅ Working — pinned v2.3.1 | `~/.code-review-graph-venv` (pyenv 3.12.13), symlinked from `~/.local/bin`. 24 tools; 259 files / 3161 nodes / 21658 edges. Was on Arch's **rolling** `/usr/bin/python3` and its hooks never ran (`command not found`) — BUG-085 / DECISION 33. Hooks now in user scope via self-gating wrappers, and GUI clients must pass `--repo` (without it the server returns an EMPTY graph with `status: ok`) — BUG-087 / DECISION 34. |
| HIVE Settings in KDE | ✅ Working | kcm_luminos_hive.so installed at /usr/lib/qt6/plugins/plasma/kcms/systemsettings/ |
| AI Mode toggle | ✅ Available | Nova on CPU + GPU model simultaneously |
| AI Mode | ✅ Active | Nova on CPU alongside GPU model |
| Codebase Cleanup | ✅ Phase 2 Done | MemPalace retired, SQLite notes active |
| RAM Management | ✅ Phase 3 | luminos-ram v3.0 precise algorithm. N=8 HotSet, LIRS IRR ranking, OnScreen protection, and safety checks. |

## ARCHITECTURE SHIFT
- **Deprecated:** Docker Desktop, n8n (Docker), Ollama (Process), SearXNG (Docker), hive-swap-server.py
  - *(MemPalace removed from this list 2026-07-25 — it is active and MANDATORY per AGENTS.md §6. The "hnswlib crash" came from the CLI resolving to a different install on Arch's rolling python, not from MemPalace itself. Fixed in BUG-085.)*
- **Current:** Bare-metal Linux
    - **Data Plane:** Native `llama.cpp` (GPU/CPU) + HATS (NPU)
    - **Control Plane:** Go `luminos-ai` daemons + Python `hive-daemon.py`
    - **Reasoning Plane:** Python `hive-daemon.py` (port 8078), Standalone SQLite Notes

## TAG SCHEMA (LOCKED)
```
[SAVE: TOPIC-NN | description]    — bookmark result
[RECALL: ID or search phrase]     — retrieve bookmark
[CALC: python expression]         — compute arithmetic
[RESULT: value]                   — injected after [CALC]
[BOOKMARK FOUND: ID | content]    — injected after [RECALL]
[BOOKMARK NOT FOUND: message]     — injected after [RECALL]
```

## TRAINING DATASET STATUS
| File | Target | Status |
|---|---|---|
| nexus_routing.jsonl | 100 | ✅ LOCKED |
| nexus_web_decision.jsonl | 150 | ✅ LOCKED |
| nexus_web_grounding.jsonl | 250 | 🔥 IN PROGRESS |
| nova_reasoning.jsonl | 200 | ⬜ NOT STARTED |

## Go Daemons
| Daemon | Status | Notes |
|---|---|---|
| luminos-ai | ✅ Running | Unix socket IPC — central routing daemon. **+ aggregates `report_ram` + Conductor `intent` broadcasts in `status` (DECISION 24 Phase 4).** |
| luminos-power | ✅ Running | v4.1 Adaptive Dual Governor + Thermal Burst Cooling + Resource Coordinator. Burst: 52°C→100% fans until 40°C. RAM pressure → effective load modifier. SPI log. **+ Conductor (DECISION 24, Phases 0-4) landed & wired — closed-loop PID fan + workload PCIe P0 pin + intent broadcast (`/run/luminos/intent.json` + socket push to ram/ai) + per-tick `conductor-telemetry.jsonl` corpus. Fan PID retuned 2026-07-04 (BUG-079: deadband + EMA + back-calc anti-windup killed the idle hunting) — idle-validated, no surging. GATED OFF by default (load test pending before default-on); enable with `LUMINOS_CONDUCTOR=1`.** |
| luminos-sentinel | ✅ Running | Process monitor — CAP_SYS_PTRACE, /proc scan |
| luminos-router | ✅ Running | .exe classifier — 80% rules + 20% ONNX AI fallback |
| luminos-ram | ✅ Running v3.5 | Real process_madvise + caps CAP_KILL/CAP_SYS_NICE active (BUG-065/066 fixed 2026-06-12 restart). All /run/luminos sockets rebound (BUG-067). **+ reacts to Conductor `intent` broadcast — heavy workload lowers swappiness via single-writer `reconcileSwappinessLocked` (offload>intent precedence); pushes `report_ram` to ai (DECISION 24 Phase 4).** |

## Compatibility
| Component | Status | Notes |
|---|---|---|
| Wine 11.8 | ✅ Working | .exe launches |
| .exe file association | ✅ Working | Silent auto-routing |
| Notepad++ tested | ✅ Working | Zone 2 Wine |
| Windows apps in launcher | ✅ Working | Auto-created |
| Wine uninstaller | ✅ Working | [CHANGE: claude-code | 2026-07-05] luminos-wine-uninstall + .desktop: hybrid — runs the app's own uninstall.exe if present, then sweeps leftovers by location (folder + AppData + Start-Menu .lnk + Wine Linux launcher + registry key), with confirm. Falls back to pure location-sweep for ghosts (e.g. WinRAR, whose uninstall.exe is gone). MT5 hard-excluded. Verified: Notepad++→runs own uninstaller; Adobe→location-only; MT5 filtered. |
| Windows VM (qemu/libvirt) | ❌ Removed | [CHANGE: claude-code | 2026-07-05] User request. luminos-windows domain undefined, VMShare/luminos-windows.qcow2 deleted (~9.7G freed), libvirtd disabled, full VM stack uninstalled (148 pkgs: qemu-full/libvirt/virt-manager/virt-viewer). Dead VM launchers + helpers swept (2nd pass): windows-vm/luminos-windows-vm/adobe-reader-vm .desktop, /usr/share/applications/luminos-vm.desktop, /usr/local/bin/luminos-vm-app + luminos-vm-launch. ("Adobe Reader (Windows VM)" menu ghost = adobe-reader-vm.desktop → luminos-vm-app; removed.) MT5 (Wine) untouched. Leftover: ~/VMShare/AcroRdrDCx…exe (739M installer). |
| Lutris | ✅ Installed | v0.5.22. lib32 GPU libs installed. Games install to root partition (629GB total). |
| GE-Proton10-34 | ✅ Installed | [CHANGE: claude-code | 2026-05-31] ~/.local/share/Steam/compatibilitytools.d/. DXVK+VKD3D-Proton bundled. |
| luminos-proton-run | ✅ Installed | [CHANGE: claude-code | 2026-05-31] /usr/local/bin/. GE-Proton launcher wrapper for Lutris (no Steam). |
| Black Myth: Wukong | 🔧 Installing | Fitgirl repack. Prefix: ~/Games/prefixes/black-myth-wukong. Setup via Lutris+GE-Proton. |

## Visual
| Component | Status | Notes |
|---|---|---|
| Inter + JetBrains Mono | ✅ Installed | |
| KWin blur + animations | ✅ Working | Magic Lamp on |
| ZSH + Starship | ✅ Working | macOS style prompt |
| Albert launcher | ✅ Working | Alt+Space (Meta+Space → HIVE) |
| Tahoe macOS Theme | ❌ Removed | [CHANGE: gemini-cli | 2026-05-11] Reverted Tahoe theme and restored Breeze Dark default state. |
| Floating panel | ❌ Reverted | [CHANGE: gemini-cli | 2026-05-11] Panel reset to default bottom position. |
| RAM monitor widget | ✅ Working | Plasma widget (org.luminos.ramwidget) installed |
| System Telemetry | ✅ Active | Continuous logging to /var/log/luminos-telemetry.csv |
| Chrome GPU | ✅ Fixed | Native AUR google-chrome-stable. AMD: Wayland+Vulkan+VAAPI. NVIDIA: XWayland+Vulkan (BUG-062). GPU selector dialog (kdialog). renderD128=NVIDIA, renderD129=AMD. |
| Chrome CPU | ✅ Fixed | Removed ANGLE/Vulkan flags (wrong for AMD); --ozone-platform=wayland; GPU-specific --use-gl |
| Universal GPU launcher | ✅ Working | Single path: luminos-gpu-launch (styled QML picker, wakes PCI power gate inline, routes NVIDIA via dgpu-exec gate — DECISION 25). luminos-nvidia-run deleted 2026-07-04. Dolphin service menu = one "Run on GPU..." action. |
| Touchpad log flood | ✅ Fixed | QT_LOGGING_RULES=kwin_libinput.warning=false in /etc/environment; suppresses ASUP1208 Touch Jump spam |
| Wine/MT5 GPU | ✅ Fixed | [CHANGE: claude-code | 2026-05-30] luminos-mt5 launcher: AMD forced (DRI_PRIME=0, mesa EGL/GLX/VK), warns if markets closed. Desktop file fixed. mt5-terminal.service updated. |
| Forex Bot GPU | ✅ Fixed | [CHANGE: gemini-cli | 2026-05-11] Forced CPU inference only. |
| NVIDIA power gating | ✅ Active | Sleeps when idle (BUG-047) |
| Suspend / lid close | ✅ Working — **verified end to end 2026-08-03**: `Lid closed.` → PowerDevil suspend → 40 h asleep → `Lid opened.` → clean resume | [CHANGE: claude-code \| 2026-08-02] BUG-091 / DECISION 38. **Lid close now suspends on AC and battery; idle suspends at KDE's shipped defaults (AC 900s / Battery 600s / LowBattery 300s).** Reverses the 2026-06-03 "never sleep on lid close" policy. Live config is `~/.config/powerdevilrc` → `[<profile>][SuspendAndShutdown] LidAction=1` — **not** `powermanagementprofilesrc`, and **not** a bare `[AC]` group; both parse fine and do nothing. logind (`luminos-lidsleep.conf`, `HandleLidSwitch=suspend`) is only the SDDM/TTY fallback, because PowerDevil holds a `block` inhibitor on `handle-lid-switch` while Plasma runs. The suspend path itself was never broken — `rtcwake -m freeze -s 30` reaches s0i3 and resumes clean; the 2026-08-01 "suspend loop" was upowerd critical-battery + the user flapping the lid. `99-luminos-lid.rules` deleted (its `kscreen-doctor` blank is now redundant and SIGABRTs per BUG-084); `luminos-lid.service` left installed but unreachable. Check with `qdbus6 … HandleButtonEvents.lidAction` (→1); **never** `triggersLidAction`, which reads true for every config. |
| Power Monitor widget | ✅ Working | [CHANGE: gemini-cli | 2026-05-11] Plasma widget (org.luminos.powerwidget) installed. [CHANGE: claude-code | 2026-07-01] BUG-078: awake-dot now reads runtime_status (wake-free); tokenized repo version deployed (installed copy was stale). Not currently placed in any panel. |
| System Monitor widget | ✅ Working | [CHANGE: claude-code | 2026-07-01] org.luminos.monitorwidget installed + in panel. Popup = full luminos-monitor box (CPU/iGPU/dGPU/fans/NVMe/WiFi/battery), feeds on `luminos-monitor stats`, 2s poll only while open (15s trickle for panel chip), dGPU sleep-guard inherited. btop escape-hatch button. |
| Thermal oscillation | ✅ Fixed | BUG-048: Removed auto-Performance switching, 45°C target, EPP-based control, hysteresis |
| Display smoothness | ⚪ VRR reverted | BUG-051 fix was VRR=Automatic+KWin LatencyPolicy=Low; user reverted VRR to Never (intentional) |
| Memory leak detection | ✅ Active | Alerts for background growth (BUG-049) |
| Firefox WhiteSur | ❌ Dropped | macOS theming removed 2026-06-11 (BUG-068); Firefox not installed |
| Live Wallpaper — visibility cost | ✅ Fixed + measured | [CHANGE: claude-code \| 2026-07-24] BUG-083/DECISION 32. `PauseWhenObscured` bool → `ObscurePolicy` int (0 never / 1 fullscreen only / 2 desktop hidden — **default 2**), per-window cover graded + 400 ms debounce. Source video right-sized 3840×2160 → 2880×1620 (panel is 2880×1800), audio stripped. plasmashell 240 → **1 jiffies/10s** while hidden, 810 → ~600 MB RSS; 24% → 12% of a core while visible. Lock-screen copy deliberately `ObscurePolicy=0`. Gap: locked/DPMS-off session is not detected as covered. |
| Login/lock cohesion | ✅ Unified look | [CHANGE: claude-code \| 2026-07-18] Two auth screens by design: SDDM (boot, Sugar-Candy theme) launches session; KScreenLocker (breeze-dark, Autolock 5min + LockOnResume) guards live session — cannot merge (different layers). Unified visually: lock screen wallpaper set to Sugar-Candy's `Mountain.jpg` via `~/.config/kscreenlockerrc [Greeter][Wallpaper][org.kde.image][General] Image=`. Both now show same mountain bg. Backup: `~/.config/kscreenlockerrc.bak-20260718`. Latent: `/etc/sddm.conf.d/hidpi.conf` says `Current=breeze` but `luminos.conf` says `Sugar-Candy` (Sugar-Candy wins alphabetically; harmless, uncleaned). |
| Ubuntu (Yaru) look | ✅ Holds across lock/idle | [CHANGE: claude-code \| 2026-07-26] BUG-088 / DECISION 30 amendment. Root cause was **KDE's Global-Theme auto-switcher** (kded `lookandfeelautoswitcher`), which re-applied `breezedark` after **5 s of idle** — so it never survived a lock. Both `[KDE] AutomaticLookAndFeel` and `AutomaticLookAndFeelOnIdle` now `false`; module unloaded live. `luminos-ubuntu-persist` rewritten to verify the colour **payload** (`[Colors:Button] DecorationFocus == 233,84,32`), not the scheme *name* — `plasma-apply-colorscheme` silently no-ops when the name already matches, which is how "Yaru" sat on top of Breeze Dark colours for 4 days while the script printed success. Verified 60/60 Yaru keys; negative-tested. **Tradeoff: no automatic light/dark switching while the Ubuntu look is on.** |
| Yaru icons (Qt + GTK) | ✅ Both sides on Yaru | [CHANGE: claude-code \| 2026-07-26] BUG-090. Qt/Dolphin was **already** correct — verified by cropping a live Dolphin window and matching it pixel-for-pixel against `Yaru/256x256/{places/folder.png, places/folder-documents.png, mimetypes/text-markdown.png}`. What was broken: GTK (`gtk-3.0`/`gtk-4.0`/`gsettings`) still read `breeze-dark`, because a Look-and-Feel apply rewrites them and `luminos-ubuntu-persist` only re-affirmed the Qt keys. Also removed the uninstalled `Humanity` from Yaru's `Inherits` (58 `Icon theme "Humanity" not found` errors in one day) and un-mangled `index.theme` (`kwriteconfig6` had sorted `[Icon Theme]` down to line 651 of 789; the spec requires it first). A pacman hook now restores the chain after `yaru-icon-theme` upgrades. Negative-tested three ways. **Known and unfixable: dock/launcher icons come from Papirus** — Yaru ships no `org.kde.dolphin`/`konsole`/`firefox`/`google-chrome` icons, and neither does breeze. |
| Folder "double icon" in Dolphin | ✅ Not a bug | [CHANGE: claude-code \| 2026-07-26] BUG-090. The folders that look different are the **same** Yaru icon with content thumbnails composited by Dolphin's `directorythumbnail` preview plugin. Disable in Configure Dolphin → Interface → Previews → uncheck *Folders*. Left enabled — it is a preference, not drift. |
| Plasma version | ⚠️ Drifted to 6.7.3 | [CHANGE: claude-code \| 2026-07-26] `plasmashell --version` = 6.7.3; docs said 6.6.4. DECISION 26 flagged 6.7 as a risk to custom KCMs — `kcm_luminos_keyboard` / `kcm_luminos_hive` not re-verified since the bump. Run `luminos-verify` (section [2]). |

## Media Server (separate machine — NOT the G14)

Moved to [`server/STATUS.md`](server/STATUS.md) — the media server now has its own
directory so it can be read, and eventually split out, without wading through G14 material.
Decisions live in [`server/DECISIONS.md`](server/DECISIONS.md).

## Open Tasks (Priority Order)
1. Eye model download + wire vision route in hive-daemon.py
2. KDE right-click service menus for HIVE (kcm_luminos_hive.so already installed)
3. ydotool type-into-apps integration
4. ~~Firefox WhiteSur theme~~ — dropped (BUG-068, macOS theming removed)
5. HIVE chat web panel (Flask localhost:7437)
6. Go orchestrator (replace Python hive-daemon.py)
7. Zone indicator Plasma widget
8. SDDM custom Luminos theme

## Input & Hardware
| Component | Status | Notes |
|---|---|---|
| Touchpad input lag | ✅ Fixed | libinput quirks (BUG-045) |
| CPU governor | ✅ schedutil | Permanent udev rule (was powersave) |
