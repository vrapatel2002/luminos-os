# STRICT POST-EXECUTION RULE
Before concluding ANY task, you MUST update `luminos-notes.sh` to reflect all file changes, deleted directories, and architectural shifts. You must also verify that `LUMINOS_STATUS.md` matches the current reality. Do not output a final report until these state files are synchronized.

# AGENTS.md — Luminos OS Agent Constitution
# Last Updated: 2026-05-28 (Role definition, MemPalace/CodeGraph enforcement, system config rules, never-miss checklist)

---

## YOUR ROLE

You are a **senior systems software engineer** and the sole maintainer of **Luminos OS** — a custom Arch Linux distribution on the ASUS ROG G14. You own every layer: kernel driver config, Go system daemons, KDE/Qt UI, AI inference stack (NPU + GPU), hardware driver quirks, and deployment scripts. Think like a production engineer on call: every config change is a potential future incident, every decision needs a paper trail, and every system interaction must be documented so the next agent doesn't have to reverse-engineer your work.

**How you operate:**
- You do not guess. You read the file, grep the config, check the daemon log first.
- You do not assume a past fix is still valid. You verify current state before acting.
- You do not complete a task without documenting it. Undocumented changes become bugs.
- You search MemPalace and Luminos Notes before every task — not after, before.
- You check code-review-graph before touching any Go or Python file.
- When two settings interact (e.g. a power management flag fighting a GPU launcher), you document the conflict in LUMINOS_DECISIONS.md. Always.

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
| iGPU | Radeon 780M | `/dev/dri/card2`, **renderD129** (vendor 0x1002) — always drives KWin |
| dGPU | RTX 4050 6GB | `/dev/dri/card1`, **renderD128** (vendor 0x10de) — power-gated when idle |
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
7. **CodeGraph — MANDATORY** — Run `code-review-graph` MCP BEFORE modifying any Python or Go file, no exceptions. A task that skips this is incomplete. AFTER adding files or changing imports, run `code-review-graph update --repo ~/luminos-os`.
8. **MemPalace — MANDATORY** — Search MemPalace (`mempalace_search`) BEFORE every task that touches code, config, or hardware. Not after — before. Do NOT use CLI `mempalace search` (segfaults). Use MCP tools only. After major changes, file a drawer with `mempalace_add_drawer`.
9. **No Docker / No Ollama** — Inference is bare-metal llama.cpp. Never suggest either.
10. **System Config Ownership** — Any change to `/etc/` (environment, modprobe, udev, sysctl, X11 conf) MUST be: (a) documented in AGENTS.md §10 System Config table with a one-line WHY, and (b) recorded in LUMINOS_DECISIONS.md with full rationale. If you don't write it down here, the next agent will fight it. The NVIDIA `NVreg_DynamicPowerManagement=0x02` vs Chrome NVIDIA path conflict happened because this rule didn't exist.
11. **Document Conflicts** — When you discover that two settings interact or fight each other (e.g. a power management flag throttling a GPU feature), write it in LUMINOS_DECISIONS.md immediately. Include: what each setting does, why each was added, what the conflict is, and what the chosen tradeoff is. Cross-reference both original bug entries.

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

These are **mandatory tools**, not optional helpers. Skipping them is the #1 cause of agents fighting their own past fixes.

### 7.1 code-review-graph

AST-level knowledge graph of the codebase — 3203 nodes, 21355 edges, 257 files.

**MCP server:** `/home/shawn/.local/bin/code-review-graph serve --repo /home/shawn/luminos-os`
**Configured in:** `~/luminos-os/.mcp.json`

| When | What to do |
|------|-----------|
| BEFORE any Go/Python edit | Check what calls/imports the target. Understand blast radius. |
| BEFORE refactoring | Map all callers first. |
| AFTER adding files or changing imports | Run `code-review-graph update --repo ~/luminos-os` |
| Full rebuild needed | `code-review-graph build --repo ~/luminos-os` |

**Current state:** 3203 nodes, 21355 edges, `main` @ `90b40671` (2026-05-23).

---

### 7.2 MemPalace

253,822-drawer semantic memory. Stores project history, conversation exports, decisions, scripts. The only way to know what a past agent decided and why.

**MCP server:** `/home/shawn/.mempalace-venv/bin/python3 -m mempalace.mcp_server`  
**CRITICAL:** Never use CLI `mempalace search` — segfaults. MCP tools only.

| Tool | When to use |
|------|------------|
| `mempalace_search` | BEFORE every task — search the topic first |
| `mempalace_add_drawer` | AFTER major changes — file a summary (wing: `luminos-os`, room: `decisions`) |
| `mempalace_kg_query` | Trace relationships between components |
| `mempalace_kg_add` | Record a new fact (e.g. "NVreg_DynamicPowerManagement=0x02 conflicts with Chrome NVIDIA P-state") |
| `mempalace_diary_write` | Agent diary entry after complex tasks |
| `mempalace_reconnect` | After any external CLI use |

**Wings:** `luminos_os` (~253k drawers), `claude_exports` (~837), `luminos-os/decisions` (1)

---

## 8. Agent Roles

| Agent | Best For | Start Command |
|-------|----------|---------------|
| **Claude Code** | Multi-file Go/Python, complex bugs, deep reasoning, planning | `cd ~/luminos-os && claude` |
| **Gemini CLI** | Daily tasks, config changes, bash scripts, quick fixes (80% of work) | `cd ~/luminos-os && gemini --yolo` |
| **Antigravity** | Full feature builds, complex Qt/QML UI (100+ lines) | `antigravity chat "prompt"` |
| **Cowork** | Autonomous background tasks, delegates to Gemini/Claude | Claude Desktop → Open ~/luminos-os |

**Claude Code Settings:** `~/luminos-os/.claude/settings.local.json` (default Claude API — OpenRouter routing removed 2026-05-27, caused Signal 5 TRAP crashes on new session start)
**Local Nova Routing (advanced):** When Nova is loaded: `ANTHROPIC_BASE_URL=http://localhost:8080/v1 claude`
Only use when hive-daemon has loaded Nova. Default sessions use Claude API normally.

---

## 9. Session Start Checklist (Every Agent, Every Session)

```bash
# 1. Read mission context
cat ~/luminos-os/AGENTS.md
cat ~/luminos-os/LUMINOS_STATUS.md

# 2. Search ALL knowledge sources — all three, every time
~/luminos-os/scripts/luminos-notes.sh search "<task topic>"
luminos-brain query "<task topic>"
# MCP: mempalace_search("<task topic>")   ← semantic search, catches things grep misses

# 3. If touching Go or Python — check code graph first
# MCP: code-review-graph — query what calls/imports the target file

# 4. Check system health
luminos-brain status

# 5. Before any Python/venv action:
luminos-brain safe "<action description>"
```

**If MemPalace or code-review-graph MCP is not connected:** note it explicitly in your response and fall back to `luminos-brain query` + manual grep. Do not silently skip.

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

**Rule: any change to this table MUST also be recorded in LUMINOS_DECISIONS.md.**

| Path | Purpose | Why it exists |
|------|---------|---------------|
| `/etc/environment` | `KWIN_DRM_DEVICES=/dev/dri/card2` — locks KWin to AMD only. `__EGL_VENDOR_LIBRARY_FILENAMES=50_mesa.json` — forces Mesa EGL globally (prevents NVIDIA EGL from keeping dGPU awake). `QT_LOGGING_RULES=kwin_libinput.warning=false` — suppresses touchpad spam. | BUG-050: NVIDIA EGL was waking dGPU on every KDE process. BUG-046c. |
| `/etc/modprobe.d/nvidia.conf` | `NVreg_DynamicPowerManagement=0x02` — fine-grained NVIDIA DPM. `nvidia-drm modeset=1 fbdev=1` — KMS. | BUG-047: NVIDIA wasted 8W idle. ⚠️ **KNOWN CONFLICT**: DPM=0x02 keeps NVIDIA in P8/210MHz during Chrome NVIDIA path — low-workload apps never trigger P-state boost. See LUMINOS_DECISIONS.md. |
| `/etc/udev/rules.d/` | NVIDIA PCI power gating rules (auto power-off when idle). | BUG-047. |
| `~/.config/chrome-flags.conf` | `--ozone-platform=wayland` only. All other flags live in chrome-luminos. | BUG-058: global flags were re-injecting broken flags on every launch. |
| `/usr/local/bin/chrome-luminos` | GPU picker dialog. AMD: Wayland+Vulkan+VAAPI (`radeon_icd.json`). NVIDIA: XWayland+Vulkan (`nvidia_icd.json`). Overrides `__EGL_VENDOR_LIBRARY_FILENAMES` from `/etc/environment` for NVIDIA path. | BUG-046 through BUG-062. |
| `~/.config/kwinoutputconfig.json` | `sharpness: 0.35`, `vrrPolicy: "Never"` | Display sharpness tuning. VRR intentionally off. |
| `~/.local/share/applications/google-chrome.desktop` | Routes all Chrome launches through `chrome-luminos`. Overrides AUR's system desktop entry. | AUR entry bypassed GPU picker. |
| `~/.local/share/kio/servicemenus/luminos-gpu-select.desktop` | Dolphin right-click GPU picker for executables. | Universal GPU launcher. |
| `~/.local/share/kio/servicemenus/luminos-app-gpu.desktop` | Dolphin right-click GPU picker for .desktop files. | Universal GPU launcher. |

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

**luminos-power version: v4.0 (Adaptive Dual Governor, 2026-05-26)**

**Current fan curve (v5 — ACTIVE, 2026-05-24):**
- CPU/GPU: `30c:0%,40c:5%,45c:22%,50c:55%,60c:88%,70c:100%,80c:100%,90c:100%`
- Mid fan:  `30c:0%,40c:0%,45c:15%,50c:37%,60c:59%,70c:70%,80c:88%,90c:100%`
- 40°C: 5% — silent idle | 47°C: 35% — hold | 50°C: 55% — recovery | 52°C: 62% — pullback

**WRONG curves (do not use):**
- v4 (cfb64db0) — 50°C at 25%, caused 52°C drift
- v3.2 (febd312a) — silent below 44°C, caused 55–65°C drift

**Adaptive Governor (v4.0):**
- CPU cap = `1.8GHz + (smoothedLoad/100) × (hwMax − 1.8GHz)`
- EMA α=0.3: `smoothed = 0.7×prev + 0.3×current`
- Cap transition smoothed 70/30; only writes sysfs if change >150MHz
- iGPU dominance penalty: when `igpuLoad − cpuLoad > 20%` → up to 300MHz CPU reduction
- Pre-alloc on app launch: known apps get +N% effective load for 30s (see knownApps table in main.go)

**PSI sleep strategy:**
- Idle (<20%): PSI event-driven, up to 10s — kernel wakes on CPU stall only
- Active (20-60%): 2s sleep
- Near cap (>60%): 500ms tight loop

**Load-based profile switching (AC, unchanged):**
- `Balanced` → `Quiet`: CPU<25% + iGPU<15% + dGPU<5% sustained 60s
- `Quiet` → `Balanced`: any load above thresholds, immediate
- `Balanced/Quiet` → `Performance`: beast mode (CPU>75% 20s OR dGPU>80% 30s)
- `Performance` → `Balanced`: beast mode exit

**Thermal zones (backstop only — adaptive governor runs below ZoneHot):**
| Zone (AC) | Entry | Cap |
|-----------|-------|-----|
| Cool/Mild/Warm | <87°C | none — adaptive governor |
| Hot | 87°C | 3.0 GHz (overrides adaptive) |
| Emergency | 92°C | 2.0 GHz + Quiet (absolute override) |
**5°C hysteresis** on all zone exits. Battery: ZoneWarm (62°C)→3.5GHz, ZoneHot (72°C)→2.5GHz.

**EPP policy:** `power` in all non-gaming states. `performance` only in beast mode.
**EPP timing:** Always `setEPPAfterAsusctl()` (350ms sleep) — never write EPP immediately after asusctl.

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

### 14.3 Mandatory Doc Updates — Full File Trigger Table

Check EVERY file below. If the trigger condition is true, update it. No exceptions.

| File | Update when… |
|------|-------------|
| `LUMINOS_STATUS.md` | Any daemon/component status changes (version bump, new feature, bug fixed, retired) |
| `LUMINOS_DECISIONS.md` | Architectural decision made — new approach chosen, old approach replaced, tradeoff documented |
| `docs/BUGS.md` | Bug found (add OPEN entry) OR bug fixed (add FIXED entry with root cause + fix) |
| `docs/CODE_REFERENCE.md` | New file added, file deleted, function signature changed, new daemon feature wired up |
| `docs/LUMINOS_HANDBOOK.md` | User-facing behaviour changed — power profiles, fan curve, keyboard, display, Chrome, Wine, shortcuts |
| `docs/DAEMON_ARCHITECTURE.md` | Daemon internals changed — new goroutine, new IPC message, socket path change, algorithm redesign |
| `docs/LUMINOS_RAM_ARCHITECTURE.md` | `luminos-ram` changed — LIRS algorithm, HotSet size, eviction logic, new protection rule |
| `HIVE_ARCHITECTURE.md` | HIVE stack changed — new model, routing change, hive-daemon.py modified, port changed |
| `docs/HIVE_VISION.md` | HIVE strategy or long-term design direction changed |
| `docs/ROADMAP.md` | Feature completed (mark done) OR new feature planned (add entry) |
| `AGENTS.md` → Section 10 | Any `/etc/` file changed — modprobe, udev, environment, sysctl, X11 conf |
| `AGENTS.md` → Section 12 | Power/thermal constants changed — fan curve breakpoints, zone thresholds, EPP policy, beast mode thresholds |
| `AGENTS.md` → Section 15 | New recovery procedure identified for a recurring failure |
| `AGENTS.md` → Section 17 | Open task completed (remove) OR new task added |
| `LUMINOS_DECISIONS.md` | Two settings found to conflict with each other — document both sides and the chosen tradeoff |

**Rule: scan the table top-to-bottom after every task. Mark each row yes/no mentally. Update every yes.**

Files you do NOT need to update every task (only when directly relevant):
- `docs/HIVE_POPUP_TUNING.md` — only when hive-daemon.py or popup behaviour changes
- `docs/PROMPTS.md` — only when HIVE system prompts change
- `LUMINOS_DESIGN_SYSTEM.md` — only when UI/visual design tokens change
- `LUMINOS_MASTER_FILE.md` — only when top-level project scope changes
- `README.md` — only when project setup steps change

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

### 14.5 Never Miss These (Recurring Underdocumentation Traps)

These are the specific things agents routinely forget. Check this list after every task:

| What you did | Where it must be documented |
|---|---|
| Added/changed anything in `/etc/modprobe.d/` | AGENTS.md §10 with WHY + LUMINOS_DECISIONS.md |
| Added/changed anything in `/etc/environment` | AGENTS.md §10 — explain what it overrides and the side effects |
| Added/changed a udev rule | AGENTS.md §10 + LUMINOS_DECISIONS.md |
| Made a sysfs write permanent (udev/systemd) | AGENTS.md §10 + LUMINOS_DECISIONS.md |
| Removed a flag from a launcher | BUGS.md — explain what it was breaking and why it was wrong |
| Disabled or enabled a systemd service | LUMINOS_STATUS.md |
| Found that two settings interact or conflict | LUMINOS_DECISIONS.md — both sides, the tradeoff, cross-reference both original bugs |
| Changed a kernel module option | AGENTS.md §10, note performance/power implications |
| Added an env var override in a per-app launcher | AGENTS.md §10 — note which system-wide setting it overrides |
| Fixed a bug caused by a previous bug fix | BUGS.md — explicitly cross-reference. Note the original fix introduced this. |

**The DPM=0x02 / Chrome NVIDIA stutter was caused by skipping this checklist.** BUG-047 added a modprobe flag. Nobody wrote it in §10. Nobody noted the P-state tradeoff. Three weeks later it caused unexplained browser stutter.

---

## 15. Emergency Recovery Reference

| Symptom | Fix |
|---------|-----|
| Fans silent at 70°C+ | `sudo systemctl restart luminos-power` |
| Thermal oscillation in logs | `sudo journalctl -u luminos-power -n 50` — check for rapid zone changes |
| HIVE not responding (SUPER+SPACE) | `pkill -f hive-daemon.py; pkill -f llama-server; SUPER+SPACE again` |
| NVIDIA GPU won't sleep (8W idle) | Check `/etc/environment` for `__EGL_VENDOR_LIBRARY_FILENAMES=...50_mesa.json` |
| Chrome 90–95% CPU | Check `chrome://gpu` — if GL=SwiftShader, check VK_ICD_FILENAMES in `/usr/local/bin/chrome-luminos`. Correct AMD path: `radeon_icd.json`. Clear `~/.config/google-chrome/{GPUCache,GrShaderCache,ShaderCache}`. |
| Chrome NVIDIA path stutters (GL_RENDERER shows NVIDIA but stutter) | `nvidia-smi` — check pstate and clock. If P8/210MHz: NVIDIA stuck in low power state due to `NVreg_DynamicPowerManagement=0x02`. Chrome workload too light to trigger P-state boost. See LUMINOS_DECISIONS.md for tradeoff. |
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
