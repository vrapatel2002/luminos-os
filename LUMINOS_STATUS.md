# Luminos OS — System Status
Last updated: 2026-05-24
Agent: claude-code (session 2 — fan curve v3.2, universal GPU launcher, Chrome Wayland, touchpad log fix, display sharpness, Hz toggle)

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

## HIVE Roster (2026) — April Upgrade
| Alias | Model Base | Target | Role | Status |
|---|---|---|---|---|
| **Nexus** | Dolphin3-Llama3.1-8B | GPU | Coordinator (Uncensored) | ✅ Active (36.3 TPS) |
| **Bolt** | Qwen2.5-Coder-7B | GPU | Expert Coder | ✅ Active (38.6 TPS) |
| **Nova** | DeepSeek-R1-0528-8B | CPU/GPU | Deep Thinker | ✅ Active (10.3 TPS CPU) |
| **Sentinel**| MobileLLM-140M | NPU | OS Security | ✅ Active |
| **Eye** | Qwen2.5-VL-7B | GPU | Vision | 📋 Pending |

## Max Speed Geometry (G14/4050)
- **Full-GPU Threshold:** < 8.5B parameters (Q4_K_M)
- **Safe VRAM Buffer:** 4.6 GB
- **VRAM/RAM Split Penalty:** -1.8 TPS per offloaded layer
- **Peak Performance:** 38.6 TPS (Qwen2.5-Coder-7B Q4 100% GPU)

## AI Stack
| Component | Status | Notes |
|---|---|---|
| HATS + triton-xdna | ✅ Working | NPU inference |
| MobileLLM-R1-140M INT8 | ✅ Working | 64MB, 800MB budget |
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
| luminos-notes.sh | ✅ Working | SQLite replacement for MemPalace |
| HIVE Settings in KDE | ✅ Working | kcm_luminos_hive.so installed at /usr/lib/qt6/plugins/plasma/kcms/systemsettings/ |
| AI Mode toggle | ✅ Available | Nova on CPU + GPU model simultaneously |
| AI Mode | ✅ Active | Nova on CPU alongside GPU model |
| Codebase Cleanup | ✅ Phase 2 Done | MemPalace retired, SQLite notes active |
| RAM Management | ✅ Phase 3 | luminos-ram v3.0 precise algorithm. N=8 HotSet, LIRS IRR ranking, OnScreen protection, and safety checks. |

## ARCHITECTURE SHIFT
- **Deprecated:** Docker Desktop, n8n (Docker), Ollama (Process), SearXNG (Docker), MemPalace (hnswlib crash), hive-swap-server.py
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
| luminos-ai | ✅ Running | Unix socket IPC — central routing daemon |
| luminos-power | ✅ Running | v4.0 Adaptive Dual Governor. Continuous CPU cap: 1.8GHz+(load/100)×(max-1.8), EMA α=0.3, 70/30 smooth. PSI event-driven idle sleep. Exec watcher pre-alloc. iGPU dominance penalty ≤300MHz. ZoneHot 87°C→3GHz override. Emergency 92°C. Beast mode + fan curve v5 unchanged. |
| luminos-sentinel | ✅ Running | Process monitor — CAP_SYS_PTRACE, /proc scan |
| luminos-router | ✅ Running | .exe classifier — 80% rules + 20% ONNX AI fallback |
| luminos-ram | ✅ Running | v3.0 — LIRS IRR ranking, N=8 HotSet, OnScreen protection, memory pressure monitor |

## Compatibility
| Component | Status | Notes |
|---|---|---|
| Wine 11.8 | ✅ Working | .exe launches |
| .exe file association | ✅ Working | Silent auto-routing |
| Notepad++ tested | ✅ Working | Zone 2 Wine |
| Windows apps in launcher | ✅ Working | Auto-created |
| VM integration | ✅ Working | Right-click + auto-fallback |
| Lutris | ✅ Installed | v0.5.22. Games partition mounted at /home/shawn/Games (315GB, nvme0n1p6). lib32 GPU libs installed. |

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
| Universal GPU launcher | ✅ Working | luminos-gpu-launch (kdialog picker); luminos-nvidia-run (wakes PCI power gate); Dolphin service menus for executables + .desktop files |
| Touchpad log flood | ✅ Fixed | QT_LOGGING_RULES=kwin_libinput.warning=false in /etc/environment; suppresses ASUP1208 Touch Jump spam |
| Wine/MT5 GPU | ✅ Fixed | [CHANGE: claude-code | 2026-05-30] luminos-mt5 launcher: AMD forced (DRI_PRIME=0, mesa EGL/GLX/VK), warns if markets closed. Desktop file fixed. mt5-terminal.service updated. |
| Forex Bot GPU | ✅ Fixed | [CHANGE: gemini-cli | 2026-05-11] Forced CPU inference only. |
| NVIDIA power gating | ✅ Active | Sleeps when idle (BUG-047) |
| Power Monitor widget | ✅ Working | [CHANGE: gemini-cli | 2026-05-11] Plasma widget (org.luminos.powerwidget) installed. |
| Thermal oscillation | ✅ Fixed | BUG-048: Removed auto-Performance switching, 45°C target, EPP-based control, hysteresis |
| Display smoothness | ⚪ VRR reverted | BUG-051 fix was VRR=Automatic+KWin LatencyPolicy=Low; user reverted VRR to Never (intentional) |
| Memory leak detection | ✅ Active | Alerts for background growth (BUG-049) |
| Firefox WhiteSur | 📋 Pending | Profile issue |

## Open Tasks (Priority Order)
1. Eye model download + wire vision route in hive-daemon.py
2. KDE right-click service menus for HIVE (kcm_luminos_hive.so already installed)
3. ydotool type-into-apps integration
4. Firefox WhiteSur theme
5. HIVE chat web panel (Flask localhost:7437)
6. Go orchestrator (replace Python hive-daemon.py)
7. Zone indicator Plasma widget
8. SDDM custom Luminos theme

## Input & Hardware
| Component | Status | Notes |
|---|---|---|
| Touchpad input lag | ✅ Fixed | libinput quirks (BUG-045) |
| CPU governor | ✅ schedutil | Permanent udev rule (was powersave) |
