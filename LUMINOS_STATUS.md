# Luminos OS — System Status
Last updated: 2026-04-25
Agent: gemini-cli

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
| Keyboard backlight | ✅ Working | kdialog UI fixed, System Settings only, no app launcher dupe |
| NPU (RyzenAI-npu1) | ✅ Working | /dev/accel0 active |

## AI Stack
| Component | Status | Notes |
|---|---|---|
| HATS + triton-xdna | ✅ Working | NPU inference |
| MobileLLM-R1-140M INT8 | ✅ Working | 64MB, 800MB budget |
| SmolLM2-360M ONNX | ✅ Working | CPU fallback |
| llama.cpp TurboQuant | ✅ Working | SM89 CUDA turbo4 |
| Nexus/Llama3.1-8B | ✅ Working | 38 t/s GPU |
| Bolt/Qwen2.5-Coder-7B | ✅ Working | 38 t/s GPU |
| Nova/DeepSeek-R1-7B | ✅ Working | 1 t/s CPU |
| nomic-embed | ✅ Working | CPU embeddings |
| Eye/Qwen2.5-VL-7B | 📋 Not downloaded | Phase 4 next |
| HIVE Orchestrator | ✅ Working | Terminal UI |

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
1. Eye model download + wire to orchestrator
2. Model upgrades (Dolphin3 Nexus, R1-0528 Nova)
3. Panel layout final polish
4. Firefox WhiteSur theme
5. HIVE right-click KDE service menus
6. ydotool type-into-apps integration
7. HIVE chat web panel (Flask localhost:7437)
8. Go orchestrator (replace Python)
9. Zone indicator Plasma widget
10. SDDM custom Luminos theme
