# HIVE Vision — Luminos OS Integrated AI Experience
# Version: 2.1 — April 2026 Model Upgrade
# Date: April 2026
# Status: APPROVED — Build Phase 4

---

## What HIVE Is

HIVE is not a chatbot. It is an AI layer woven into 
every part of Luminos OS. The user never thinks 
"let me open my AI app." They just right-click, 
select text, press a shortcut, and AI is there.

---

## Model Stack (Updated April 2026)

### Current Models (Upgraded)
| Agent | New Model | Role | Device |
|-------|-----------|------|--------|
| **Nexus** | Dolphin3-Llama3.1-8B Q4_K_M | Coordinator | GPU |
| **Bolt** | Qwen2.5-Coder-7B Q4_K_M | Coder | GPU |
| **Nova** | R1-0528-Qwen3-8B Q4_K_M | Deep Thinker | CPU/GPU |
| **Eye** | Qwen2.5-VL-7B Q4_K_M | Vision | GPU |

### VRAM & KV Cache Strategy (TurboQuant)
All GPU-bound models utilize **TurboQuant turbo4** (Google ICLR 2026) for KV cache compression.
- **type_k=12 / type_v=12**: Reduces KV cache memory footprint by 6x.
- **Benefit**: Enables longer context windows (32K+) without VRAM overflow on the 6GB RTX 4050.

### AI Mode vs. Normal Mode
To bypass the "one model in VRAM" bottleneck, HIVE supports two concurrency modes:

- **Normal Mode**: All models run on GPU. Models are hot-swapped (evicted/loaded) on demand. Best for maximum inference speed.
- **AI Mode**: Nova (Reasoning) is pinned to the Ryzen 7 CPU (`n_gpu_layers=0`). This allows Nova to process long-running reasoning tasks in the background while Nexus or Bolt remain active on the GPU for immediate user interaction.

---

## Integration Points (The Real Product)

### 1. Right-Click Context Menu (KDE Service Menu)
Right-click ANY file or folder → HIVE submenu:
- Summarize, Explain, Find Bugs, Write Tests, Rename, Translate.

### 2. Text Selection → Global Shortcut (SUPER+H)
Select text anywhere → Press SUPER+H → HIVE popup for quick actions.

### 3. Type Directly Into Apps
HIVE can type its output directly into the focused window via `xdotool` or `ydotool`.

### 4. Screen Understanding (SUPER+SHIFT+H)
Eye agent analyzes current screen for error messages, UI help, or OCR.

---

## Architecture

```
User Action (right-click/shortcut/terminal)
         ↓
luminos-hive-cli (Go binary — fast startup)
         ↓
HIVE Socket (/run/luminos/hive.sock)
         ↓
HIVEOrchestrator (Python — src/hive/orchestrator.py)
         ↓
Router → detects model needed
         ↓
VRAMManager → evict current, load needed model
         ↓
llama.cpp (TurboQuant turbo4 GPU inference)
```

---
Last updated: 2026-04-26
Status: APPROVED — Phase 4 Upgrade Complete
