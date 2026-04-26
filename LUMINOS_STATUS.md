# Luminos OS — System Status
Last updated: 2026-04-26
Agent: claude-code (cleanup pass)

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
| Keyboard backlight | ✅ Working | KDE KCM (7 modes: static/breathe/pulse/highlight/laser/rainbow/wave) |
| NPU (RyzenAI-npu1) | ✅ Working | /dev/accel0 active |

## HIVE Roster (2026) — llama.cpp TurboQuant, NO Ollama
| Alias | Model File (GGUF) | Target | Role | Status |
|---|---|---|---|---|
| **Nexus** | Llama-3.1-8B-Instruct-Q4_K_M.gguf | GPU | Front-end Coordinator | ✅ Active |
| **Bolt** | Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf | GPU | Expert Coder | ✅ Active |
| **Nova** | DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf | CPU | Deep Thinker | ✅ Active |
| **Sentinel** | MobileLLM-R1-140M-INT8.onnx | NPU | OS Security Driver | ✅ Active |
| **Eye** | Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf | GPU | Vision | 📋 Not downloaded |

## Max Speed Geometry (G14/4050)
- **Full-GPU Threshold:** < 8.5B parameters (Q4_K_M)
- **Safe VRAM Buffer:** 4.6 GB
- **VRAM/RAM Split Penalty:** -1.8 TPS per offloaded layer
- **Peak Performance:** 38.6 TPS (any 7-8B Q4 100% GPU)

## AI Stack
| Component | Status | Notes |
|---|---|---|
| HATS + triton-xdna | ✅ Working | NPU inference (MobileLLM) |
| MobileLLM-R1-140M INT8 | ✅ Working | 64MB, 800MB budget |
| VRAM Watchdog | ✅ Working | Auto-evict if >90% usage |
| llama.cpp TurboQuant | ✅ Working | TheTom fork, SM89 CUDA turbo4 |
| HIVE Orchestrator | ✅ Working | src/hive/ Python layer |
| Codebase Cleanup | ✅ Done | Windows HIVE (Ollama) archived |

## Architecture
- **Deprecated:** Docker, Ollama, n8n, SearXNG (all archived to archive/windows-hive-2026/)
- **Data Plane:** Native llama.cpp (GPU/CPU) + HATS (NPU)
- **Control Plane:** Go daemons (cmd/)
- **Reasoning Plane:** Python HIVE (src/hive/)

## HATS vs CPU Benchmark (MobileLLM-R1-140M)
| Backend | TPS | CPU Usage | Latency (avg) |
|---|---|---|---|
| **NPU (HATS)** | 141.71 | 8.0% | 7.05 ms |
| **CPU (Fallback)** | 169.51 | 2.9% | 5.89 ms |
- **Finding:** NPU overhead exceeds compute gains for sub-1B models.

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
| Albert launcher | ✅ Working | Meta+Space |
| Floating panel | 🔧 In Progress | Layout needs polish |
| Firefox WhiteSur | 📋 Pending | Profile issue |

## Open Tasks (Priority Order)
1. HIVE popup chat window (SUPER+SPACE)
2. Eye model download + wire to orchestrator
3. Model upgrades (Dolphin3 Nexus, R1-0528 Nova)
4. Panel layout final polish
5. Firefox WhiteSur theme
6. HIVE right-click KDE service menus
7. ydotool type-into-apps integration
8. HIVE chat web panel (Flask localhost:7437)
9. Zone indicator Plasma widget
10. SDDM custom Luminos theme
