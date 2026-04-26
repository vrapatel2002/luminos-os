# LUMINOS OS — Current Focus
# Last updated: 2026-04-26
# [CHANGE: claude-code | 2026-04-26]

## Current Priority: HIVE Integration

### What HIVE Is (Linux Version)
4 local AI models running via llama.cpp TurboQuant (TheTom fork, SM89 CUDA):
- **Nexus**: Llama-3.1-8B-Instruct — coordinator (GPU, ~38 t/s)
- **Bolt**: Qwen2.5-Coder-7B-Instruct — coding specialist (GPU, ~38 t/s)
- **Nova**: DeepSeek-R1-Distill-Qwen-7B — reasoning (CPU, ~1 t/s)
- **Eye**: Qwen2.5-VL-7B — vision (GPU, not yet downloaded)

NO Ollama. NO Docker. Direct llama.cpp inference with turbo4 KV cache.
VRAM limit: 4.6GB safe (6GB total). Only ONE GPU model at a time.

### Active Tasks (In Order)
1. HIVE popup chat window (SUPER+SPACE shortcut)
2. Eye model download + vision integration
3. Model upgrades (Dolphin3 Nexus, R1-0528 Nova)
4. KDE right-click service menus for HIVE
5. Type into any app (ydotool integration)
6. HIVE chat web panel (Flask localhost:7437)

### Stack (Locked)
- llama.cpp TurboQuant (TheTom fork, `--cache-type-k turbo4 --flash-attn`)
- Python HIVE layer (src/hive/)
- Go daemons (luminos-ai, power, sentinel, router)
- KDE Plasma 6.6.4 Wayland
- RTX 4050 for GPU models
- AMD XDNA NPU for Sentinel/MobileLLM (HATS)
