# 🐝 HIVE — Heterogeneous Intelligent Virtual Engine

A 100% local multi-AI agent system running on bare-metal Linux.

---

## 1. What is HIVE

HIVE is a local AI orchestrator that coordinates a team of specialized language models. Unlike general-purpose chatbots, HIVE routes every prompt to the most capable "agent" for the task.

The system is built for the **ASUS ROG G14**, utilizing its NVIDIA dGPU, Ryzen CPU, and XDNA NPU simultaneously to maximize inference throughput.

---

## 2. The Team & Hardware Targets

| Agent | Role | Model | Hardware Target |
|-------|------|-------|-----------------|
| 🧠 **Nexus** | Coordinator | `Dolphin-8B` | **GPU** (RTX 4050) |
| ⚡ **Bolt** | Expert Coder | `Qwen-3.6-7B` | **GPU** (RTX 4050) |
| 💭 **Nova** | Deep Thinker | `DeepSeek-R1-8B` | **CPU** (Ryzen 7) |
| 🛡️ **Sentinel**| OS Security | `MobileLLM-140M`| **NPU** (XDNA 1) |

**VRAM Management:** 
Nexus and Bolt share the 6GB VRAM pool. HIVE performs aggressive hot-swapping to ensure the active agent has a 4.6GB "Safe VRAM" buffer, preventing system UI lag.

---

## 3. Native Linux Architecture

HIVE has been ported from legacy Docker/Windows infrastructure to a native Linux daemon stack:

- **Data Plane:** Native `llama.cpp` binaries running as managed subprocesses.
- **Control Plane:** Go-based `luminos-ai` daemons handling IPC and process lifecycle.
- **Reasoning Plane:** Python HIVE logic managing intent-based routing and agent profiles.
- **NPU Layer:** HATS (Host-Assisted Tile-Streaming) kernel for real-time security inference on XDNA.

---

## 4. Boot Sequence

The system is managed by `systemd` and the `luminos-power` daemon:

1. **Hardware Init:** `luminos-power` verifies dGPU state and NPU driver availability.
2. **Control Plane:** `luminos-ai` starts the Unix socket listener at `/run/luminos/ai.sock`.
3. **Reasoning Warmup:** The Python `orchestrator` loads agent profiles from `config.yaml`.
4. **Sentinel Launch:** The NPU Sentinel starts continuous system-call monitoring via HATS.
5. **Ready:** The system waits for user input. GPU models (Nexus/Bolt) are loaded on-demand.

---

## 5. File Locations (Linux)

- **Models:** `~/.local/share/luminos/models/`
- **Config:** `~/luminos-os/config.yaml`
- **Orchestrator:** `~/luminos-os/orchestrator/`
- **Agents:** `~/luminos-os/agents/`
- **Logs:** `/var/log/luminos/`

---

## 6. VRAM Watchdog

HIVE includes a native VRAM pressure watchdog. If VRAM usage exceeds **90%** (e.g., during gaming), the system will automatically:
1. Signal `SIGUSR1` to active `llama-server` processes.
2. Evict GPU models immediately.
3. Transition to NPU/CPU fallback mode for background tasks.

---

*Last updated: 2026-04-26 | Phase 2 Cleanup Complete*
