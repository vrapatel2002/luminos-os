# Luminos OS — System Status
Last updated: 2026-04-28
Agent: antigravity

## System
| Component | Status | Notes |
|---|---|---|
| Arch Linux base | ✅ Working | Triple boot G14 |
| KDE Plasma 6.6.4 | ✅ Working | Wayland session |
| SDDM | ✅ Working | Defaults to Plasma Wayland |
| NVIDIA 595.58.03 | ✅ Working | nvidia-dkms |
| AMD iGPU (Radeon 780M) | ✅ Working | Desktop rendering |
| RTX 4050 6GB | ✅ Working | AI + gaming |
| asusctl + supergfxctl | ✅ Working | Hybrid mode locked |
| Keyboard backlight | ✅ Working | Enhanced KDE KCM (7 modes) + Smart power daemon |
| NPU (RyzenAI-npu1) | ✅ Working | /dev/accel0 active |

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
| HIVE Orchestrator | ✅ Working | Native Python reasoning layer (systemd active) |
| llama.cpp Python | ✅ Installed | v0.3.20 (system package) |
| HIVE popup (SUPER+SPACE) | ✅ Working | QML6 native UI, optimized scroll (ListView), LocalStorage persistence |
| luminos-notes.sh | ✅ Working | SQLite replacement for MemPalace |
| HIVE Settings in KDE | ✅ Working | Native KCM plugin (kcm_luminos_hive.so) |
| AI Mode toggle | ✅ Available | Nova on CPU + GPU model simultaneously |
| AI Mode | ✅ Active | Nova on CPU alongside GPU model |
| Codebase Cleanup | ✅ Phase 2 Done | MemPalace retired, SQLite notes active |

## ARCHITECTURE SHIFT
- **Deprecated:** Docker Desktop, n8n (Docker), Ollama (Process), SearXNG (Docker), MemPalace (hnswlib crash)
- **Current:** Bare-metal Linux
    - **Data Plane:** Native `llama.cpp` (GPU/CPU) + HATS (NPU)
    - **Control Plane:** Go `luminos-ai` daemons
    - **Reasoning Plane:** Python `HIVE` orchestrator, Standalone SQLite Notes

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
| luminos-ai | ✅ Running | Unix socket IPC |
| luminos-power | ✅ Running | Auto profile switch |
| luminos-sentinel | ✅ Running | Process monitor |
| luminos-router | ✅ Running | .exe classifier |

## Compatibility
| Component | Status | Notes |
|---|---|---|
| Wine 11.6 | ✅ Working | .exe launches |
| .exe file association | ✅ Working | Silent auto-routing |
| Notepad++ tested | ✅ Working | Zone 2 Wine |
| Windows apps in launcher | ✅ Working | Auto-created |
| VM integration | ✅ Working | Right-click + auto-fallback |

## Visual
| Component | Status | Notes |
|---|---|---|
| Inter + JetBrains Mono | ✅ Installed | |
| KWin blur + animations | ✅ Working | Magic Lamp on |
| ZSH + Starship | ✅ Working | macOS style prompt |
| Albert launcher | ✅ Working | Alt+Space (Meta+Space → HIVE) |
| Floating panel | 🔧 In Progress | Layout needs polish |
| Firefox WhiteSur | 📋 Pending | Profile issue |

## Open Tasks (Priority Order)
1. Eye model download + wire to orchestrator
2. Panel layout final polish
3. Firefox WhiteSur theme
4. HIVE right-click KDE service menus
5. ydotool type-into-apps integration
6. HIVE chat web panel (Flask localhost:7437)
7. Go orchestrator (replace Python)
8. Zone indicator Plasma widget
9. SDDM custom Luminos theme
