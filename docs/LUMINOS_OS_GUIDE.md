# Luminos OS — Complete System Guide
# Version: 1.0
# Date: 2026-05-09
# Role: Foundational Reference for All Agents

---

## 1. What Is Luminos OS
Luminos OS is a custom, AI-native Arch Linux distribution specifically engineered for the **ASUS ROG G14 GA403UU**.
- **Philosophy**: Privacy-first, local-only AI inference, and seamless Windows compatibility.
- **Boot Configuration**: Triple-boot setup (Windows 11 / Default Arch / Luminos OS).
- **Primary Goal**: A high-performance, intelligent desktop environment that replaces Windows for developer and gaming workloads.

## 2. Hardware (Never Change These)
- **CPU**: AMD Ryzen 7 8845HS (Phoenix/Hawk Point) with integrated Radeon 780M.
- **NPU**: Ryzen AI (XDNA 1) — accessed via `/dev/accel0`. Dedicated to system security (Sentinel).
- **GPU**: NVIDIA RTX 4050 6GB Laptop GPU.
- **RAM**: 16GB LPDDR5x (Managed by `luminos-ram` v3.0).
- **GPU Rules**: 
    - **iGPU**: Handles all desktop rendering and UI composition.
    - **dGPU**: Reserved exclusively for heavy AI inference (HIVE) and gaming.
    - **Mode**: **Hybrid GPU mode is locked**. Never use `supergfxctl` to switch to Integrated or Discrete-only modes.

## 3. The Stack (Locked Decisions)
- **Desktop**: KDE Plasma 6.6.4 (Wayland session).
- **Compositor**: KWin.
- **UI Framework**: Qt 6 / QML for custom widgets and popups.
- **System Logic**: Go-based daemon stack for speed and stability.
- **AI Inference**: `llama.cpp` with TurboQuant for HIVE; ONNX/Triton-XDNA for NPU.
- **BANNED**: Hyprland, GTK4, Python-based UIs, Docker, Ollama. (See `LUMINOS_DECISIONS.md` for rationale).

## 4. HIVE AI System
HIVE is a local multi-agent cluster running on bare-metal Linux. It is **not** a chatbot; it is system infrastructure.
- **Nexus** (Dolphin 3.0): Coordinator. Uncensored, follows OS-level instructions.
- **Bolt** (Qwen 2.5 Coder): Programming specialist.
- **Nova** (DeepSeek R1): Deep reasoning and complex debugging. (Runs on CPU in "AI Mode").
- **Sentinel** (MobileLLM): Real-time OS security monitoring on the NPU.
- **Eye** (Qwen-VL): Vision specialist (pending).
- **HIVE Brain**: A semantic intelligence layer (`hive-brain.md`) that acts as a security guard, observing system state and enforcing safety rules.

## 5. Go Daemons
The control plane consists of 4 primary Go daemons:
1. **`luminos-ai`**: The central IPC hub. Manages request routing and session state via Unix sockets.
2. **`luminos-power`**: Intelligent thermal management. Automatically switches profiles based on AC state and CPU temperature (Q→B at 50°C, B→P at 65°C).
3. **`luminos-sentinel`**: Process monitor and threat detection. Uses NPU for low-power always-on scanning.
4. **`luminos-router`**: Classifies `.exe` files to determine the best compatibility layer (Wine vs. Firecracker vs. KVM).

## 6. RAM Management
Managed by the `luminos-ram` daemon (v3.0) using a precise LIRS-based algorithm.
- **Hot Set**: 8 slots for most-used windows. Protected from compression.
- **Cold Set**: Inactive processes. Subject to `MADV_PAGEOUT` (compression to ZRAM) and eventual `SIGSTOP`.
- **OnScreen Protection**: **Sacred Rule**. Any window visible to the user or focused within the last 60 seconds is never compressed or frozen.
- **ZRAM**: 8GB compressed swap device (`/dev/zram0`) using `zstd`.

## 7. Python Environment Rules (CRITICAL)
Python versioning is the #1 cause of system instability. Follow these rules strictly:
- **System Python (3.14.x)**: For system utilities only. **NEVER** install `torch`, `tensorflow`, or ML packages here.
- **Pyenv Python (3.12.13)**: The **MANDATORY** version for all AI, HIVE, and ML projects.
- **Venv Isolation**: Every project (HIVE, Triton, Forex) **MUST** have its own dedicated virtual environment.
- **MemPalace**: **RETIRED**. Do not attempt to fix or use. Use `luminos-notes.sh` instead.
- **BANNED Packages**: `hnswlib` and `chromadb` (cause immediate SEGV). Use **FAISS** for vector search.
- **Override Protocol**: If a safety block is triggered by `hive-watch`, you can bypass it for legitimate reasons using `--hive-override` (Terminal) or `--reason` (CLI).

## 8. Projects on This System
- **Luminos OS**: `~/luminos-os`. The main repository. Contains all core logic and docs.
- **Forex Trading Bot**: `~/Forex-Trading-Bot-main`. Separate Python project. Requires pyenv 3.12.13. Needs MT5 via Wine.

## 9. Agent Workflow
- **Claude Code**: Best for complex planning and architectural changes. Uses HIVE Brain MCP.
- **Gemini CLI**: Best for automation, daemon logic, and state maintenance.
- **Antigravity**: Best for QML/Qt visual implementations.
- **HIVE Brain Protocol**:
    - **Before acting**: `luminos-brain safe "action"`
    - **After acting**: `luminos-brain log "summary"`
- **Git Format**: `type(scope): description \n\n Agent: [name] \n Task: [task]`

## 10. Current Status (May 2026)
- **Healthy**: All core Go daemons, HIVE popup, RAM management, NPU drivers, Touchpad fix (BUG-045).
- **Broken**: MemPalace (Permanent), Forex Bot venv (Needs 3.12 rebuild).
- **Pending**: Eye model integration, Firefox WhiteSur theme, HIVE Web Panel.

## 11. Critical Rules (Non-Negotiable)
1. **Never use Docker or Ollama.**
2. **Never modify the Wayland environment critical section** in the HIVE popup script.
3. **Never install ML packages on system Python.**
4. **Always document changes** in `LUMINOS_STATUS.md` and `luminos-notes.sh`.

## 12. Quick Reference
### Common Commands
- `luminos-brain {safe|log|query|think|status}`: Interface with system intelligence.
- `luminos-notes.sh {add|search|list}`: Project knowledge base.
- `systemctl --user {status|restart} {service}`: Manage UI components.
- `cat /sys/block/zram0/mm_stat`: Check real-time ZRAM compression.

### Important Paths
- `/usr/local/bin/`: System-wide Luminos tools.
- `~/luminos-os/scripts/`: Repository source for scripts.
- `~/.local/share/luminos/`: Runtime data, models, and brain logbook.
- `/run/luminos/`: Unix sockets for daemon IPC.
