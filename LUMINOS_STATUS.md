# Luminos OS — System Status
Last updated: 2026-07-25
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
| llama.cpp TurboQuant | ✅ Working | turbo4 (type_k=12, type_v=12) |
| HIVE Idle Watchdog | ✅ Working | Auto-unloads models after 5 mins |
| HIVE Orchestrator (orchestrator.py) | 🛠 Retired | Superseded by hive-daemon.py. luminos-hive.service updated + disabled. |
| llama.cpp Python | ✅ Installed | v0.3.20 (system package) |
| HIVE Swap Server | 🛠 Retired | Port 8079 functionality merged into HIVE Daemon |
| HIVE Daemon | ✅ Working | Port 8078. Popup-managed lifecycle (pgrep guard). ThreadingHTTPServer, 60s timeout, lockfile. |
| HIVE Web Search | ✅ Working | DuckDuckGo HTML scraping, no API key. Works without llama-server loaded. Auto-routes via [ROUTE:WEB] or keyword detection. |
| HIVE popup (SUPER+SPACE) | ✅ Working | Persistent kdialog conversation loop. Starts hive-daemon.py on open, kills on close. |
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
| Component | Status | Notes |
|---|---|---|
| Server hardware | ✅ Settled | [CHANGE: claude-code \| 2026-07-29] Friend's laptop: **i5-10210U, 10th gen Comet Lake, 4c/8t, 16 GB RAM**, SSD + HDD. Nothing purchased. **The SSD is off limits** — the owner's Windows install stays byte-identical, so Arch lives entirely on the HDD including its own EFI partition. UHD 620 (Gen9.5) is spec'd for 4K HEVC 10-bit decode + H264/HEVC encode but has **no AV1 at all**; the Roku can't do AV1 either, so keep AV1 out of the library rather than transcoding it on both ends. Spec-derived — confirm with `vainfo` on first boot. |
| Stage 1 installer | ✅ Written, dry-run tested | [CHANGE: claude-code \| 2026-07-29] `scripts/luminos-server-install`. Runs from the booted Arch ISO over SSH. **Detects** the target disk (non-removable + rotational + not USB) instead of assuming `/dev/sda`, aborts if 0 or >1 candidates, and requires `--confirm-disk` to match. Defaults to `--dry-run`. Ends in 12 assertions and refuses to claim success if any fail. No `\|\| true` anywhere. Testing caught a real bug: the original positional `lsblk` parse broke because **`TRAN` is empty for a plain SATA disk**, shifting every field left — it would have found no HDD on the real machine. Now reads each attribute individually via sysfs. |
| Stage 2 services | ✅ Written, dry-run tested | [CHANGE: claude-code \| 2026-07-29] `scripts/luminos-server-services`. Jellyfin + **`qbittorrent-nox`** (the GUI package only runs inside a logged-in desktop session — fatal on a headless box) + `sonarr-bin` + `prowlarr-bin` (the `-bin` variants skip a ~1 h .NET build on a 15 W CPU writing to a spinning disk). Single shared group `media` gid 945 pinned to match the G14; `/srv/media/{downloads,tv,movies,.import-staging}` at `2775` setgid. `informant` blocks `pacman -Syu` until Arch news is read, since updates are manual by choice. **Refuses to run on any host not named `luminos-server`**, so it cannot be fired at the G14 by accident. Verification *proves* the permission design by writing as `sonarr` and reading as `jellyfin`, and checks all four ports are bound. Reports `vainfo` output rather than claiming hwaccel works. |
| Install USB | ✅ Written + verified | [CHANGE: claude-code \| 2026-07-29] `archlinux-2026.07.01` written to `/dev/sda` (SanDisk Ultra 57.3 G, `TRAN=usb`, `RM=1`); internal `nvme0n1` never touched. **Proven, not assumed:** read the first 1583022080 bytes back off the raw device and the sha256 matched the ISO exactly (`e86295dc…a6c0`). `EFI/BOOT/BOOTx64.EFI` confirmed present on `ARCHISO_EFI` — the fallback path Dell firmware looks for on removable media. The movie that was on the stick still exists twice under `/srv/media`. |
| Server OS install | ✅ Installed + running | [CHANGE: claude-code \| 2026-07-31] Built on the **Dell Inspiron 3590** (i5-10210U, battery removed so it is AC-only), Arch on the HDD, headless, administered over SSH as `ssh -i ~/.ssh/luminos-server shawn@192.168.2.61`. Original build notes below still apply. [CHANGE: claude-code \| 2026-07-29] Laptop is a **Dell** — `F2` setup, `F12` boot menu. **BitLocker cleared:** protection off on the SSD (`C:`), so the TPM-seal hazard is gone. **HDD cleared:** it *had* been encrypted; owner reformatted it, which freed it. Its 2 existing partitions need no merging — the installer `wipefs`/`sgdisk --zap-all`s the whole table. Remaining warnings in MEDIA_SERVER_PLAN §7a-7c: (1) **never** flip `SATA Operation` from `RAID On` to `AHCI` — stops Windows booting; (2) Secure Boot must go off and **stays** off, which costs nothing for Windows itself but **breaks kernel-anti-cheat games** (Valorant/Fortnite/Battlefield on Win11) — ask the owner first; (3) full shutdown, not Restart, or Fast Startup leaves filesystems half-mounted. |
| Dual-boot design | ✅ Decided | [CHANGE: claude-code \| 2026-07-29] **Two independent bootloaders, zero shared state** — the HDD gets its own ESP and systemd-boot; Windows' bootloader on the SSD is never opened for writing. No GRUB os-prober, nothing that can clobber Windows. OS choice is the `F12` menu. **The HDD must be first in BIOS boot order**, or a power blip brings the box up in Windows at a login screen where SSH is unreachable. Consequence to accept: while Windows is running the media server is offline. Watch for Windows updates reasserting themselves first in NVRAM boot order — that presents as "the server stopped answering", not as a Linux fault. |
| State migration | ✅ Done | [CHANGE: claude-code \| 2026-07-31] `/var/lib/{jellyfin,sonarr,prowlarr}` + `/etc/jellyfin` rsync'd off the G14; library, indexers and watch state carried over rather than rebuilt. Radarr added on the server (it was never on the G14). Direct play to the Roku proven end to end. |
| Networking — dual-homed trap | ⚠️ Half-fixed, needs a cable | [CHANGE: claude-code \| 2026-07-31] The box answers on **both** wlan0 `192.168.2.61` and enp2s0 `192.168.2.62`, same subnet, and the ethernet cable is bad so the wire only negotiates **100 Mb/s (≈12.5 MB/s)**. Two separate bugs stacked: qBittorrent's own UPnP had mapped the router's forward to **.62**, and Linux **ARP flux** (default `arp_ignore=0`) let the router learn .61 at the *ethernet* MAC — so traffic addressed to the wifi IP still arrived over the slow wire. `ip route get` said wlan0 the whole time; only `/sys/class/net/<if>/statistics/rx_bytes` and `tcpdump -i <if>` showed the truth (27 k peer packets on enp2s0). Fixed: `/etc/sysctl.d/30-luminos-arp-flux.conf` (`arp_ignore=1`, `arp_announce=2`) + forward re-pointed at .61. Peer split went 15/679 → 14/20, so it is better but **not** fully on wifi. **Real fix is a new ethernet cable** (owner-only), then set `RouteMetric` in `/etc/systemd/network/20-wired.network`. Do **not** pin qBittorrent's `current_network_interface` — tried it, every tracker announce died. |
| BitTorrent port 25989 | ✅ Open on purpose + durable | [CHANGE: claude-code \| 2026-07-31] DECISION 35. Client had uploaded **0 bytes ever** and could only dial out, so 4K swarms stalled at 1 connection. `/etc/nftables.conf` now accepts tcp+udp 25989 from anywhere; every admin surface (WebUI 8080, Jellyfin 8096, Sonarr 8989, Radarr 7878, Prowlarr 9696, ssh) stays LAN-only. Loaded behind a `systemd-run --on-active=180` auto-rollback, cancelled only after SSH survived. Router forward is kept alive by **`qbt-portmap.service` + `.timer`** (boot+90 s, hourly) because qBittorrent's own UPnP stopped mapping entirely. Proven **outside-in** with a throwaway port and a genuinely external fetcher — an online port checker said CLOSED and was simply **wrong**, and probing your own public IP from inside the LAN is meaningless (hairpin NAT). Rationale + how to close it again: `docs/MEDIA_SERVER_SECURITY.md` §2a/§2b. |
| 1337x via Byparr | ✅ Working end to end | [CHANGE: claude-code \| 2026-07-30] Byparr/Camoufox clears Cloudflare headless with no virtual display (do **not** load the `playwright_captcha` addon — it is itself fingerprinted). Search still returned interstitials until `/usr/lib/byparr/src/endpoints.py` was patched: the wait loop broke as soon as `page.title()` changed, but a challenge navigates several times and the title is momentarily empty or the next document's between hops. New `_still_challenged()` also requires `__cf_chl` to be gone from `page.url`. Backup at `endpoints.py.orig`. Wired as Prowlarr proxy id 2 + indexer id 10 (tag `flaresolverr`), synced to Sonarr id 6; 16 results on re-verify. |
| Torrent throughput | ✅ Diagnosed, swarm-limited | [CHANGE: claude-code \| 2026-07-31] 0 → **10.74 MB/s** after fixing tracker rot (16 of 23 trackers on the original magnets were dead; ngosang `trackers_best` auto-added, `max_connec` 2000/300, 6 active downloads). The network itself does **46.34 MB/s** (Ubuntu ISO), so 46 MB/s is real — just not from these swarms. **Public indexer seeder counts are fiction:** 1337x claimed 346/256/207, `GET /api/v2/torrents/trackers` after adding showed **3/7/1**. Disk 5–37% util, never the bound. |

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
