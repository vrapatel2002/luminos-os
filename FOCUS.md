# LUMINOS OS — Current Focus
# Last updated: 2026-05-06
# [CHANGE: claude-code | 2026-05-06]

## Current Priority: HIVE Polish + Expand

### What HIVE Is (Current State)
4 local AI models via llama.cpp TurboQuant (TheTom fork, SM89 CUDA):
- **Nexus**: Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf — uncensored coordinator (GPU, ~36 t/s)
- **Bolt**: Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf — coding specialist (GPU, ~38 t/s)
- **Nova**: DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf — deep reasoning (CPU, ~10 t/s)
- **Eye**: Qwen2.5-VL-7B-Q4_K_M.gguf — vision (GPU, not yet downloaded)

Popup: SUPER+SPACE → qml6 HiveChat.qml + HistorySidebar.qml
Backend: hive-daemon.py on port 8078 (popup-managed, not systemd)
NO Ollama. NO Docker. Direct llama.cpp inference with turbo4 KV cache.

### ✅ Done (this session)
- HIVE popup chat window (SUPER+SPACE) — full QML6 native UI
- Model upgrades: Dolphin3 Nexus + R1-0528 Nova
- hive-daemon.py — consolidated orchestration on port 8078
- Conversation history sidebar (HistorySidebar.qml)
- Centred message column layout (max-width 720px)
- Relative timestamps, delete chat, minimal sidebar style
- Competing orchestrator.py service disabled

### Active Tasks (In Order)
1. Eye model download + wire vision route in daemon
2. KDE right-click service menus for HIVE (kcm_luminos_hive.so already installed)
3. Type into any app (ydotool integration)
4. Panel layout final polish
5. Firefox WhiteSur theme
6. HIVE chat web panel (Flask localhost:7437)
7. Go orchestrator (replace Python hive-daemon.py)

### Stack (Locked)
- llama.cpp TurboQuant (TheTom fork, `--cache-type-k turbo4 --flash-attn`)
- hive-daemon.py (scripts/) — Python stdlib only, port 8078
- HiveChat.qml + HistorySidebar.qml (src/hive/)
- Go daemons (luminos-ai, power, sentinel, router)
- KDE Plasma 6.6.4 Wayland
- RTX 4050 for GPU models, AMD XDNA NPU for Sentinel (HATS)
