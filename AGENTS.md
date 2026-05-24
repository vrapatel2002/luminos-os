# STRICT POST-EXECUTION RULE
Before concluding ANY task, you MUST update `luminos-notes.sh` to reflect all file changes, deleted directories, and architectural shifts. You must also verify that `LUMINOS_STATUS.md` matches the current reality. Do not output a final report until these state files are synchronized.

# AGENTS.md — Luminos OS Agent Constitution
# Last Updated: 2026-05-23 (Full rewrite + code-review-graph + mempalace re-enabled)

---

## 1. What Is Luminos OS?

Luminos OS is a custom **Arch Linux** distribution for the **ASUS ROG G14 GA403UU**.

- **Goal:** Privacy-first, AI-native Windows replacement. All Windows apps run automatically. Zero manual tuning ever.
- **UI:** KDE Plasma 6.6.4 (Wayland) + KWin + Qt/QML custom widgets
- **Backend daemons:** 5 Go binaries (luminos-ai, luminos-power, luminos-sentinel, luminos-router, luminos-ram)
- **AI Stack:** llama.cpp TurboQuant (NOT Ollama, NOT Docker) + HATS NPU for Sentinel
- **Hardware:** AMD Ryzen 9 8845HS (CPU) + Radeon 780M (iGPU) + RTX 4050 6GB (dGPU) + XDNA NPU
- **Triple boot:** Windows / Default Arch / Luminos OS

**PERMANENTLY BANNED:** Hyprland, GTK4, HyprPanel, Python UI, Docker, Ollama, Snapd, greetd, swww, hyprlock

---

## 2. Hardware Profile (Quick Reference)

| Component | Spec | Notes |
|-----------|------|-------|
| CPU | Ryzen 9 8845HS | 8c/16t Zen 4, TJmax 105°C, max boost 5.137 GHz |
| iGPU | Radeon 780M | `/dev/dri/card2`, renderD128 — always drives KWin |
| dGPU | RTX 4050 6GB | `/dev/dri/card1`, renderD129 — power-gated when idle |
| NPU | AMD XDNA (accel0) | 16 TOPS — ONNX/HATS only, NOT ROCm |
| Display | Samsung eDP-2 | 2880×1800, 120Hz, 2× integer HiDPI, VRR=Never (intentional) |
| RAM | 16GB LPDDR5x | Shared CPU/iGPU/OS |
| GPU mode | PRIME offload | iGPU always on. NVIDIA renders offscreen, DMA-BUFs back to iGPU. NO MUX switch. |

**VRAM Budget:** 6GB total → 4.6GB safe. Only ONE GPU model loads at a time.
**PRIME env vars:** `DRI_PRIME=1 __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia`
**Why card2 = AMD:** PCIe bus enumeration puts NVIDIA first. card1=NVIDIA, card2=AMD. Never assume otherwise.

---

## 3. System Architecture

### 3.1 Daemon Stack

```
User / KDE Plasma / Qt Apps
         │ Unix socket (JSON)
         ▼
 luminos-ai (Go)  /run/luminos/ai.sock
 Central routing, session mgmt, supervises sub-daemons
    │          │          │          │
    ▼          ▼          ▼          ▼
luminos-   luminos-   luminos-   luminos-
power      sentinel   router     ram
(Go)       (Go)       (Go)       (Go)
sysfs/EPP  /proc scan PE rules   LIRS HotSet
asusctl    kill/notify 80% rules KWin D-Bus
fan curves notify     AI edge    CDP port
    │                    │
    └──── Python NPU ────┘
    /run/luminos/npu.sock     /run/luminos/classifier.sock
    ONNX/VitisAI on accel0    ONNX edge-case routing (CPU)

hive-daemon.py  127.0.0.1:8078  (popup-managed, NOT systemd)
llama-server    127.0.0.1:8080  (lazy load, HIVE inference)
```

### 3.2 Socket Paths

| Service | Path | Protocol |
|---------|------|----------|
| luminos-ai | `/run/luminos/ai.sock` | JSON |
| luminos-power | `/run/luminos/power.sock` | JSON |
| luminos-sentinel | `/run/luminos/sentinel.sock` | JSON |
| luminos-router | `$XDG_RUNTIME_DIR/luminos-router.sock` | newline JSON |
| luminos-npu (Python) | `/run/luminos/npu.sock` | JSON |
| luminos-classifier (Python) | `/run/luminos/classifier.sock` | JSON |
| llama-server | `127.0.0.1:8080` | OpenAI-compatible REST |
| hive-daemon | `127.0.0.1:8078` | HTTP JSON |

### 3.3 Go vs Python Rule (Decision 13 — FINAL)

- **Go** — anything that is NOT ML inference: socket servers, routing rules, thermal control, process scanning, RAM management, power management
- **Python** — ONLY when touching: ONNX Runtime, VitisAI, llama.cpp, numpy

### 3.4 Service Startup Order

**Phase 1 (Go — AI not required):**
1. luminos-power → initial AC/battery mode
2. luminos-sentinel → /proc scanner (rules-only until NPU ready)
3. luminos-router → PE rule engine + cache
4. luminos-ai → opens main socket, routes to sub-services

**Phase 2+ (Python inference):**
5. luminos-npu (Python) → ONNX on /dev/accel0
6. luminos-classifier (Python) → edge-case model (CPU)
7. llama-server (Python) → lazy, loads first HIVE model on first request
8. hive-daemon.py → starts on SUPER+SPACE, killed on popup close

---

## 4. HIVE AI Models

| Alias | Model | Runs On | Role | Status | TPS |
|-------|-------|---------|------|--------|-----|
| **Nexus** | Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf | GPU (RTX 4050) | Uncensored coordinator | ✅ Active | 36.3 |
| **Bolt** | Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf | GPU (RTX 4050) | Expert coder | ✅ Active | 38.6 |
| **Nova** | DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf | CPU (AI Mode) | Deep reasoning | ✅ Active | 10.3 |
| **Sentinel** | MobileLLM-R1-140M-INT8.onnx | NPU (XDNA) | OS security (HATS) | ✅ Active | — |
| **Eye** | Qwen2.5-VL-7B-Q4_K_M.gguf | GPU (RTX 4050) | Vision | 📋 Pending download | — |

**llama.cpp flags:** `--cache-type-k turbo4 --flash-attn` (TurboQuant TheTom fork, SM89 CUDA)
**Popup:** SUPER+SPACE → `src/hive/HiveChat.qml` + `src/hive/HistorySidebar.qml`
**Backend:** `scripts/hive-daemon.py` port 8078 — owns routing, model swapping, inference
**RETIRED:** `hive-swap-server.py` (port 8079) — merged into hive-daemon. `orchestrator.py` — disabled.
**AI Mode:** Nova runs on CPU (n_gpu_layers=0) alongside a GPU model. Bypasses 1-model VRAM limit.

---

## 5. Mandatory Rules

1. **Minimal Changes** — Do not touch working OS components unless the task requires it.
2. **Identity Tags** — Add `[CHANGE: agent | date]` to EVERY modified code block.
3. **VRAM Watchdog** — Respect 4.6GB safe limit. Only one GPU model loads at a time.
4. **State Tracking** — Update `LUMINOS_STATUS.md` and `luminos-notes.sh` every turn.
5. **HIVE Brain** — Use `luminos-brain` CLI for environment safety and audit logging.
6. **Python Safety** — For ANY Python/venv/package action, run `luminos-brain safe "[action]"`. If response is NO, STOP.
7. **CodeGraph** — Use `code-review-graph` MCP BEFORE modifying any Python or Go file. AFTER adding new files or changing imports, run `code-review-graph update --repo ~/luminos-os` to keep the graph current.
8. **MemPalace** — Use `mempalace` MCP to recall project history and file decisions after tasks. Do NOT use the CLI `mempalace search` command (segfaults). Use only via MCP tools.
9. **No Docker / No Ollama** — Inference is bare-metal llama.cpp. Never suggest either.

---

## 6. HIVE Brain Safety Protocol

Before ANY action involving Python, virtual environments, or package installation:

| Agent | Method |
|-------|--------|
| Claude Code | `luminos-brain safe "description of action"` in terminal |
| Gemini CLI | `luminos-brain safe "description of action"` |
| Antigravity | `luminos-brain safe "description of action"` |

**If response starts with NO — do not proceed. Stop and ask user.**

Other HIVE Brain commands:
```bash
luminos-brain log "what you did"         # audit log entry
luminos-brain query "topic"              # grep-based knowledge search
luminos-brain think "question"           # RAG semantic search
luminos-brain status                     # system health
```

---

## 7. MCP Tools — Code Review Graph + MemPalace

### 7.1 code-review-graph

Persistent knowledge graph of the entire codebase. 3203 nodes, 21355 edges, 257 files. Builds an AST-level map of every function, class, and import across Go, Python, QML, C++, Bash.

**MCP server:** `/home/shawn/.local/bin/code-review-graph serve --repo /home/shawn/luminos-os`
**Configured in:** `~/luminos-os/.mcp.json`

**When to use:**
- BEFORE modifying any Python or Go file — check what calls/imports the target
- BEFORE refactoring — understand the blast radius
- To find where a function is defined vs called
- To understand data flow between daemons

**Maintenance commands (run outside MCP):**
```bash
# After adding new files or changing imports:
/home/shawn/.local/bin/code-review-graph update --repo ~/luminos-os

# Full rebuild (after major refactor or branch change):
/home/shawn/.local/bin/code-review-graph build --repo ~/luminos-os

# Check graph is current:
/home/shawn/.local/bin/code-review-graph status --repo ~/luminos-os
```

**Current state:** 3203 nodes, 21355 edges, built on `main` @ `90b40671` (2026-05-23).

---

### 7.2 MemPalace

Semantic knowledge palace with 253,822 drawers. Stores project history, Claude conversation exports, Luminos OS decisions, code, scripts, documentation. Enables cross-session recall.

**MCP server:** `/home/shawn/.mempalace-venv/bin/python3 -m mempalace.mcp_server`
**Configured in:** `~/luminos-os/.mcp.json`
**Palace data:** `~/.mempalace/`
**Python venv:** `~/.mempalace-venv/` (Python 3.12, chromadb 0.6.x, chroma_hnswlib 0.7.6)

**Existing wings (project data):**
| Wing | Rooms | Drawers |
|------|-------|---------|
| `luminos_os` | general, documentation, testing, configuration, src, scripts, systemd | ~253k |
| `claude_exports` | architecture, general | ~837 |
| `luminos-os` | decisions | 1 |

**Key MCP tools:**
| Tool | Use for |
|------|---------|
| `mempalace_search` | Semantic search across all drawers |
| `mempalace_add_drawer` | File new content (use after decisions/changes) |
| `mempalace_status` | Palace overview — counts by wing/room |
| `mempalace_kg_query` | Query knowledge graph for entity relationships |
| `mempalace_kg_add` | Add a fact to the knowledge graph |
| `mempalace_list_rooms` | List rooms in a wing |
| `mempalace_get_drawer` | Fetch full content of a specific drawer |
| `mempalace_diary_write` | Write agent diary entry (AAAK format) |
| `mempalace_reconnect` | Force reconnect after external CLI use |

**CRITICAL:** Do NOT use the CLI `mempalace search` command — it segfaults (Python 3.12 + chroma_hnswlib CLI path issue). Use ONLY via MCP tools in Claude Code. The MCP server path does NOT segfault.

**After major changes,** file a summary into the palace:
```
Use MCP tool: mempalace_add_drawer
  wing: "luminos-os"
  room: "decisions"  (or "general", "scripts", etc.)
  content: "[full summary of what changed and why]"
  added_by: "claude-code"
```

---

## 8. Agent Roles

| Agent | Best For | Start Command |
|-------|----------|---------------|
| **Claude Code** | Multi-file Go/Python, complex bugs, deep reasoning, planning | `cd ~/luminos-os && claude` |
| **Gemini CLI** | Daily tasks, config changes, bash scripts, quick fixes (80% of work) | `cd ~/luminos-os && gemini --yolo` |
| **Antigravity** | Full feature builds, complex Qt/QML UI (100+ lines) | `antigravity chat "prompt"` |
| **Cowork** | Autonomous background tasks, delegates to Gemini/Claude | Claude Desktop → Open ~/luminos-os |

**Claude Code Settings:** `~/luminos-os/.claude/settings.local.json` (OpenRouter → DeepSeek V4 Pro)
**Local DeepSeek Routing (advanced):** When Nova is loaded: `ANTHROPIC_BASE_URL=http://localhost:8080/v1 claude`
Only use when hive-daemon has loaded Nova. Default sessions use Claude API normally.

---

## 9. Session Start Checklist (Every Agent, Every Session)

```bash
# 1. Read mission context
cat ~/luminos-os/AGENTS.md
cat ~/luminos-os/LUMINOS_STATUS.md

# 2. Search existing knowledge
~/luminos-os/scripts/luminos-notes.sh search "<task topic>"

# 3. Check system health
luminos-brain status
luminos-brain query "<task topic>"

# 4. Before any Python/venv action:
luminos-brain safe "<action description>"
```

---

## 10. File Map (Current — May 2026)

### Go Daemons (`cmd/`)
| Path | Description |
|------|-------------|
| `cmd/luminos-ai/main.go` | Unix socket IPC server — central routing daemon |
| `cmd/luminos-power/main.go` | EPP thermal control, fan curve v2 (early ramp), beast mode, AC/battery switching |
| `cmd/luminos-sentinel/main.go` | Process security monitor — CAP_SYS_PTRACE, /proc scan |
| `cmd/luminos-router/main.go` | .exe classifier — 80% rule-based + 20% ONNX AI fallback |
| `cmd/luminos-ram/main.go` | v3.0 RAM manager — LIRS IRR, HotSet N=8, OnScreen guard, KWin D-Bus |

### Python HIVE (`src/hive/`)
| Path | Description |
|------|-------------|
| `src/hive/agent_base.py` | Base agent class |
| `src/hive/nexus.py` | Coordinator (Dolphin3-Llama3.1-8B) |
| `src/hive/bolt.py` | Coder (Qwen2.5-Coder-7B) |
| `src/hive/nova.py` | Reasoning (DeepSeek-R1-0528-8B) |
| `src/hive/eye.py` | Vision (Qwen2.5-VL-7B, pending) |
| `src/hive/orchestrator.py` | RETIRED — superseded by hive-daemon.py |

### HIVE UI (`src/hive/` — QML)
| Path | Description |
|------|-------------|
| `src/hive/HiveChat.qml` | Main chat window (Claude.ai-style, max-width 720px) |
| `src/hive/HistorySidebar.qml` | Conversation history sidebar |

### HIVE Backend (`scripts/`)
| Path | Description |
|------|-------------|
| `scripts/hive-daemon.py` | Consolidated orchestration, port 8078. Owns routing, model lifecycle, inference. |
| `scripts/hive-start-model.sh` | Start llama-server with a specific model |
| `scripts/hive-idle-watchdog.sh` | Auto-kills llama-server after 5 min idle |

### KDE KCMs (`src/kcms/`)
| Path | Description |
|------|-------------|
| `src/kcms/kcm_luminos_keyboard/` | Keyboard backlight (C++/QML, 7 modes) |
| `src/kcms/kcm_luminos_hive/` | HIVE AI settings (mode toggle, model roster, VRAM, shortcut) |

### Python NPU / Classifier (`src/`)
| Path | Description |
|------|-------------|
| `src/npu/hats_kernel.py` | HATS NPU inference (HATSSentinel class) |
| `src/npu/quantize_int8.py` | INT8 quantization entry point |
| `src/classifier/onnx_classifier.py` | Zone classifier |
| `src/classifier/router_daemon.py` | Zone routing daemon |

### Plasma Widgets (`src/widgets/`)
| Path | Description |
|------|-------------|
| `src/widgets/org.luminos.powerwidget/` | Power monitor widget (profile, CPU temp, fan, NVIDIA state) |
| `src/widgets/org.luminos.ramwidget/` | RAM monitor widget |

### Scripts (`scripts/`)
| Path | Deployed To | Description |
|------|-------------|-------------|
| `scripts/luminos-notes.sh` | — | SQLite notes tracker (project knowledge base) |
| `scripts/luminos-display-hz` | `/usr/local/bin/luminos-display-hz` | kdialog Hz settings window |
| `scripts/luminos-60hz` | `/usr/local/bin/luminos-60hz` | Switch display to 60Hz |
| `scripts/luminos-120hz` | `/usr/local/bin/luminos-120hz` | Switch display to 120Hz |
| `scripts/luminos-gpu-launch` | `/usr/local/bin/luminos-gpu-launch` | kdialog GPU picker (AMD or NVIDIA) |
| `scripts/luminos-nvidia-run` | `/usr/local/bin/luminos-nvidia-run` | Wake NVIDIA PCI power gate + PRIME env + exec |

### System Config (active, on-disk)
| Path | Purpose |
|------|---------|
| `/etc/environment` | `KWIN_DRM_DEVICES=/dev/dri/card2` + `__EGL_VENDOR_LIBRARY_FILENAMES=...50_mesa.json` + touchpad log suppression |
| `~/.config/kwinoutputconfig.json` | `sharpness: 0.35`, `vrrPolicy: "Never"` |
| `~/.var/app/com.google.Chrome/config/chrome-flags.conf` | `--ozone-platform=wayland` globally |
| `/usr/local/bin/chrome-luminos` | GPU-specific GL: AMD=`--use-gl=egl`, NVIDIA=`--use-gl=desktop` |
| `~/.local/share/kio/servicemenus/luminos-gpu-select.desktop` | Dolphin right-click GPU picker for executables |
| `~/.local/share/kio/servicemenus/luminos-app-gpu.desktop` | Dolphin right-click GPU picker for .desktop files |

### Archive (DO NOT RESTORE)
| Path | What It Was |
|------|-------------|
| `archive/windows-hive-2026/` | Old Windows HIVE (Ollama/Docker) |
| `archive/gtk4-ui/` | Retired GTK4 Python UI |
| `archive/hyprland/` | Retired Hyprland configs |
| `archive/stale-docs/` | Old Ubuntu-era docs + gemini agent rules |

---

## 11. Absolute Do-Nots

| Target | Reason |
|--------|--------|
| `.env` | Credentials — never touch |
| `data/hive.db` | Database — never touch |
| `TAG SCHEMA` in STATUS.md | Locked format — never modify `[SAVE]`/`[RECALL]`/`[CALC]` |
| Native Go daemons (`cmd/`) | Only touch when explicitly instructed |
| `hive-swap-server.py` (port 8079) | RETIRED — do not restart or reference |
| `orchestrator.py` service | RETIRED — do not enable or reference |
| Tahoe macOS theme | Caused white panel bugs. Archived. Do not restore. |
| ~~code-review-graph removed~~ | Re-enabled 2026-05-23. Use via MCP tools (see Section 7). |

---

## 12. Power & Thermal Quick Reference

**Current fan curve (v5 — ACTIVE, 2026-05-24):**
- CPU/GPU: `30c:0%,40c:5%,45c:22%,50c:55%,60c:88%,70c:100%,80c:100%,90c:100%`
- Mid fan:  `30c:0%,40c:0%,45c:15%,50c:37%,60c:59%,70c:70%,80c:88%,90c:100%`
- Hardware PWM CPU/GPU: `(0, 13, 56, 140, 224, 255, 255, 255)`
- Hardware PWM Mid: `(0, 0, 38, 94, 150, 179, 224, 255)`

**Key operating points (CPU/GPU fan):**
- 40°C: 5% — silent idle
- 47°C: 35% — hold target (interpolated between 45c:22% and 50c:55%)
- 50°C: 55% — recovery threshold
- 52°C: 62% — strong overshoot pullback
- 60°C: 88% — near-max under load

**WRONG curves (do not use):**
- v4 (cfb64db0) — 50°C breakpoint too low (25%), caused 52°C drift with only 29% fan
- v3.2 (febd312a) — silent below 44°C, caused 55–65°C drift
- v2 early-ramp — 40% at 40°C idle, too loud

**EPP policy:** `power` in all non-gaming states. `performance` only in beast mode (dGPU >80% for 30s or CPU >75% for 20s, AC only).

**Load-based profile switching (AC):**
- `Balanced` → `Quiet`: CPU<25% + iGPU<15% + dGPU<5% sustained 60s
- `Quiet` → `Balanced`: any load above thresholds, immediate
- `Balanced/Quiet` → `Performance`: beast mode trigger (CPU>75% 20s or dGPU>80% 30s)
- `Performance` → `Balanced`: beast mode exit (both drop below threshold)

**Thermal zones (AC):** Cool <60°C | Mild 60°C (no cap) | Warm 72°C (no cap — fans 100% at 70°C) | Hot 87°C (3.0GHz cap) | Emergency 92°C (2.0GHz) (2.0GHz + Quiet)
**5°C hysteresis** on all zone exits.

**EPP timing:** Always use `setEPPAfterAsusctl()` (350ms sleep after asusctl) to win the asusd race. Never write EPP immediately after `asusctl profile set`.

---

## 13. Luminos Notes Usage (Mandatory)

**BEFORE every task:**
```bash
~/luminos-os/scripts/luminos-notes.sh search "<task topic>"
```

**AFTER every task:**
```bash
~/luminos-os/scripts/luminos-notes.sh add [TAG] "[Detailed summary of changes]"
```

Tags used: `[HIVE]`, `[POWER]`, `[GPU]`, `[DISPLAY]`, `[RAM]`, `[SENTINEL]`, `[ROUTER]`, `[UI]`, `[DOCS]`, `[BUG]`, `[AUDIT]`

Never start a task without checking Luminos Notes first.
Never complete a task without adding to Luminos Notes.

---

## 14. Mandatory Update Protocol (Every Task)

After EVERY task, ALL agents must:

### 14.1 Luminos Notes
```bash
~/luminos-os/scripts/luminos-notes.sh add [TAG] "[Detailed summary of changes]"
```

### 14.2 HIVE Brain Log
```bash
luminos-brain log "[Summary of what was done]"
```

### 14.3 Relevant .md files (check all, update if changed)
- `LUMINOS_STATUS.md` → component status changed
- `LUMINOS_DECISIONS.md` → architectural decision made
- `docs/BUGS.md` → bug found or fixed
- `docs/CODE_REFERENCE.md` → new files added or removed

### 14.4 Git Commit Format (mandatory)
```bash
git add -A
git commit -m "type(scope): description

Agent: [claude-code|gemini-cli|antigravity|cowork]
Task: [what was asked]"
git push origin main
```

NEVER complete a task without updating Luminos Notes.
NEVER complete a task without updating relevant docs.
NEVER commit without the Agent and Task fields.

---

## 15. Emergency Recovery Reference

| Symptom | Fix |
|---------|-----|
| Fans silent at 70°C+ | `sudo systemctl restart luminos-power` |
| Thermal oscillation in logs | `sudo journalctl -u luminos-power -n 50` — check for rapid zone changes |
| HIVE not responding (SUPER+SPACE) | `pkill -f hive-daemon.py; pkill -f llama-server; SUPER+SPACE again` |
| NVIDIA GPU won't sleep (8W idle) | Check `/etc/environment` for `__EGL_VENDOR_LIBRARY_FILENAMES=...50_mesa.json` |
| Chrome 90–95% CPU | Check `/usr/local/bin/chrome-luminos` — remove any `--use-gl=angle` flag |
| Panel broken/white | `systemctl --user restart plasma-plasmashell` |
| Launcher blank/empty | Fix: `applicationsDisplay=1` in plasma-org.kde.plasma.desktop-appletsrc |
| KDE Settings can't find HIVE KCM | `kbuildsycoca6 --noincremental` |
| Display stuck at wrong Hz | `luminos-120hz` or `luminos-60hz` |
| KWin crash (blank screen) | `kwin_wayland --replace &` |

---

## 16. TAG SCHEMA (LOCKED — DO NOT MODIFY)

```
[SAVE: TOPIC-NN | description]    — bookmark result
[RECALL: ID or search phrase]     — retrieve bookmark
[CALC: python expression]         — compute arithmetic
[RESULT: value]                   — injected after [CALC]
[BOOKMARK FOUND: ID | content]    — injected after [RECALL]
[BOOKMARK NOT FOUND: message]     — injected after [RECALL]
```

---

## 17. Open Tasks (Priority Order)

1. Eye model download + wire vision route in hive-daemon.py
2. KDE right-click service menus for HIVE (kcm_luminos_hive.so already installed)
3. ydotool type-into-apps integration
4. Firefox WhiteSur theme
5. HIVE chat web panel (Flask localhost:7437)
6. Go orchestrator (replace Python hive-daemon.py)
7. Zone indicator Plasma widget
8. SDDM custom Luminos theme

---

## 18. Reply Format (always end output with)

```
REPLY TO MANAGEMENT:
  - Task completed: [yes/no/partial]
  - What changed: [list files modified/created]
  - LUMINOS_STATUS.md updated: [yes/no]
  - Luminos Notes updated: [yes/no]
  - Ready for: [what comes next]
```
