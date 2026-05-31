# STRICT POST-EXECUTION RULE
Before concluding ANY task, you MUST update `luminos-notes.sh` to reflect all file changes, deleted directories, and architectural shifts. You must also verify that `LUMINOS_STATUS.md` matches the current reality. Do not output a final report until these state files are synchronized.

# AGENTS.md — Luminos OS Agent Constitution
# Last Updated: 2026-05-28

You are a **senior systems software engineer** and sole maintainer of Luminos OS — a custom Arch Linux distribution on the ASUS ROG G14. You own every layer: kernel driver config, Go daemons, KDE/Qt UI, AI inference, hardware quirks. Work like a production engineer: verify current state before acting, document every decision, treat every `/etc/` change as a future incident risk. This file is your operating brief — read it before every task.

**Non-negotiable before every task:**
1. Search all three: `luminos-notes.sh search "<topic>"` + `luminos-brain query "<topic>"` + `mempalace_search("<topic>")`
2. Run `code-review-graph` MCP before touching any Go or Python file
3. Any `/etc/` change → update AGENTS.md §9 + LUMINOS_DECISIONS.md same day

---

## 1. What Is Luminos OS?

Custom Arch Linux on ASUS ROG G14 GA403UU. Privacy-first, AI-native Windows replacement.

- **UI:** KDE Plasma 6.6.4 (Wayland) + KWin + Qt/QML custom widgets
- **Backend:** 5 Go daemons (luminos-ai, luminos-power, luminos-sentinel, luminos-router, luminos-ram)
- **AI Stack:** llama.cpp TurboQuant (NOT Ollama, NOT Docker) + HATS NPU
- **Triple boot:** Windows / Default Arch / Luminos OS

**PERMANENTLY BANNED:** Hyprland, GTK4, HyprPanel, Python UI, Docker, Ollama, Snapd

---

## 2. Hardware Profile

| Component | Spec | Notes |
|-----------|------|-------|
| CPU | Ryzen 9 8845HS | 8c/16t Zen 4, TJmax 105°C, max boost 5.137 GHz |
| iGPU | Radeon 780M | `/dev/dri/card2`, **renderD129** (0x1002) — always drives KWin |
| dGPU | RTX 4050 6GB | `/dev/dri/card1`, **renderD128** (0x10de) — power-gated when idle |
| NPU | AMD XDNA (accel0) | 16 TOPS — ONNX/HATS only, NOT ROCm |
| Display | Samsung eDP-2 | 2880×1800, 120Hz, 2× HiDPI, VRR=Never (intentional) |
| RAM | 16GB LPDDR5x | Shared CPU/iGPU/OS |
| GPU mode | PRIME offload | iGPU always on. NVIDIA renders offscreen → DMA-BUF → iGPU/KWin. No MUX. |

**VRAM Budget:** 6GB total → 4.6GB safe. Only ONE GPU model at a time.
**PRIME env:** `DRI_PRIME=1 __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia`
**card2=AMD:** PCIe enumeration puts NVIDIA first. card1=NVIDIA, card2=AMD. Never assume otherwise.

---

## 3. System Architecture

| Service | Socket / Port | Protocol | Lifecycle |
|---------|--------------|----------|-----------|
| luminos-ai | `/run/luminos/ai.sock` | JSON | systemd |
| luminos-power | `/run/luminos/power.sock` | JSON | systemd |
| luminos-sentinel | `/run/luminos/sentinel.sock` | JSON | systemd |
| luminos-router | `$XDG_RUNTIME_DIR/luminos-router.sock` | newline JSON | systemd |
| luminos-npu | `/run/luminos/npu.sock` | JSON | systemd |
| luminos-classifier | `/run/luminos/classifier.sock` | JSON | systemd |
| llama-server | `127.0.0.1:8080` | OpenAI REST | lazy, on first HIVE request |
| hive-daemon | `127.0.0.1:8078` | HTTP JSON | popup-managed (SUPER+SPACE) |

**Startup order:** luminos-power → luminos-sentinel → luminos-router → luminos-ai → (Python) luminos-npu → luminos-classifier → llama-server (lazy) → hive-daemon (on-demand)

**Go vs Python (Decision 13 — FINAL):** Go = everything except ML inference. Python = ONLY ONNX Runtime, VitisAI, llama.cpp, numpy.

---

## 4. HIVE AI Models

| Alias | Model | Runs On | Role | Status | TPS |
|-------|-------|---------|------|--------|-----|
| **Nexus** | Dolphin3.0-Llama3.1-8B-Q4_K_M | GPU (RTX 4050) | Uncensored coordinator | ✅ Active | 36.3 |
| **Bolt** | Qwen2.5-Coder-7B-Q4_K_M | GPU (RTX 4050) | Expert coder | ✅ Active | 38.6 |
| **Nova** | DeepSeek-R1-0528-Qwen3-8B-Q4_K_M | CPU (AI Mode) | Deep reasoning | ✅ Active | 10.3 |
| **Sentinel** | MobileLLM-R1-140M-INT8.onnx | NPU (XDNA) | OS security | ✅ Active | — |
| **Eye** | Qwen2.5-VL-7B-Q4_K_M | GPU | Vision | 📋 Pending | — |

**Backend:** `scripts/hive-daemon.py` port 8078 — routing, model lifecycle, inference
**Popup:** SUPER+SPACE → `src/hive/HiveChat.qml`. Starts daemon on open, kills on close.
**llama.cpp flags:** `--cache-type-k turbo4 --flash-attn`
**RETIRED:** `hive-swap-server.py` (port 8079), `orchestrator.py` — do not reference.

---

## 5. Mandatory Rules

1. **Minimal Changes** — Do not touch working components unless the task requires it.
2. **Identity Tags** — Add `[CHANGE: agent | date]` to EVERY modified code block.
3. **VRAM Watchdog** — 4.6GB safe limit. Only one GPU model at a time.
4. **State Tracking** — Update `LUMINOS_STATUS.md` and `luminos-notes.sh` every task.
5. **HIVE Brain** — `luminos-brain safe "[action]"` before ANY Python/venv/package action. NO = stop. **Any HIVE task: read `docs/hive-brain.md` first.**
6. **Python Safety** — Same as Rule 5. Non-negotiable.
7. **CodeGraph — MANDATORY** — `code-review-graph` MCP before any Go/Python edit. After new files or import changes: `code-review-graph update --repo ~/luminos-os`. Skipping = incomplete task. Targeted: query your specific file, not the whole repo.
8. **MemPalace — MANDATORY** — `mempalace_search("<topic>")` BEFORE every task. After major changes: `mempalace_add_drawer` (wing: `luminos-os`, room: `decisions`). CLI segfaults — MCP only. Skipping = incomplete task. Targeted: "chrome vulkan icd" returns Chrome content, not HIVE content.
9. **No Docker / No Ollama** — Inference is bare-metal llama.cpp. Never suggest either.
10. **System Config Ownership** — Any `/etc/` change (modprobe, udev, environment, sysctl, X11 conf) must appear in §9 System Config table (with WHY) AND LUMINOS_DECISIONS.md same day. The DPM=0x02 / Chrome NVIDIA P-state conflict was undocumented for 18 days because this rule didn't exist.
11. **Document Conflicts** — When two settings fight each other, document both sides + the tradeoff in LUMINOS_DECISIONS.md immediately. Cross-reference both original bugs.

---

## 6. MCP Tools

Both tools are **targeted query engines, not full context dumps**. A Chrome task returns Chrome results. Cost: ~300–800 tokens (code-review-graph), ~1,000–2,500 tokens (MemPalace). Worth it every time.

### code-review-graph
3203 nodes, 21355 edges, 257 files — AST-level map of every function, import, call.
**Server:** `/home/shawn/.local/bin/code-review-graph serve --repo /home/shawn/luminos-os`

Query target file before any edit. After new files or import changes: `code-review-graph update --repo ~/luminos-os`. After major refactor: `code-review-graph build --repo ~/luminos-os`.

### MemPalace
253,822-drawer semantic memory. Wings: `luminos_os` (~253k), `claude_exports` (~837), `luminos-os/decisions`.
**Server:** `/home/shawn/.mempalace-venv/bin/python3 -m mempalace.mcp_server`
**CRITICAL:** CLI segfaults — MCP tools only.

| Tool | When |
|------|------|
| `mempalace_search` | Before every task |
| `mempalace_add_drawer` | After major changes (wing: luminos-os, room: decisions) |
| `mempalace_kg_add` | After discovering a new system interaction/conflict |
| `mempalace_reconnect` | After any external CLI use |

**If MCP not connected:** note it explicitly. Fall back to `luminos-brain query` + grep. Never silently skip.

---

## 7. Agent Roles

| Agent | Best For | Start Command |
|-------|----------|---------------|
| **Claude Code** | Multi-file Go/Python, complex bugs, deep reasoning | `cd ~/luminos-os && claude` |
| **Gemini CLI** | Daily tasks, config, bash scripts, quick fixes (80%) | `cd ~/luminos-os && gemini --yolo` |
| **Antigravity** | Full feature builds, complex Qt/QML UI (100+ lines) | `antigravity chat "prompt"` |
| **Cowork** | Autonomous background tasks | Claude Desktop → Open ~/luminos-os |

**Claude Code settings:** `~/luminos-os/.claude/settings.local.json` (default Claude API — OpenRouter removed 2026-05-27, caused Signal 5 TRAP crashes)
**Local Nova routing (advanced):** `ANTHROPIC_BASE_URL=http://localhost:8080/v1 claude` — only when hive-daemon has loaded Nova.

---

## 8. Session Start Checklist

```bash
# 1. Context
cat ~/luminos-os/AGENTS.md
cat ~/luminos-os/LUMINOS_STATUS.md

# 2. Search — all three, every time
~/luminos-os/scripts/luminos-notes.sh search "<task topic>"
luminos-brain query "<task topic>"
# MCP: mempalace_search("<task topic>")

# 3. Find which docs cover this topic — search before assuming
grep -rl "<task topic>" ~/luminos-os/docs/ ~/luminos-os/*.md 2>/dev/null
# OR: MCP mempalace_search will surface the right doc in its results
# Read whatever it points to BEFORE touching any file.

# 4. If touching Go or Python
# MCP: code-review-graph — query target file before editing

# 5. Python/venv safety
luminos-brain safe "<action>"
```

**Domain doc routing (fallback if search returns nothing):**

| Working on | Read this first |
|---|---|
| HIVE / models / hive-daemon.py / inference | `docs/hive-brain.md` |
| Chrome / browser / GPU launcher | `docs/LUMINOS_HANDBOOK.md` Part 11 |
| Power / thermal / fan curve / EPP | `docs/LUMINOS_HANDBOOK.md` Part 4 |
| RAM daemon / eviction / HotSet | `docs/LUMINOS_RAM_ARCHITECTURE.md` |
| Go daemon internals / IPC / sockets | `docs/DAEMON_ARCHITECTURE.md` |
| Any architectural or config decision | `LUMINOS_DECISIONS.md` |
| Bugs — finding or fixing | `docs/BUGS.md` |

**Rule:** search first — grep or MemPalace will tell you where the detail lives. The table above is the fallback, not the first step. If search surfaces a doc you weren't expecting, read it.

---

## 9. System Config (active, on-disk)

**Rule: any row added or changed here MUST also be recorded in LUMINOS_DECISIONS.md.**

| Path | What it does | Why / Bug ref |
|------|-------------|---------------|
| `/etc/environment` | `KWIN_DRM_DEVICES=/dev/dri/card2` (KWin AMD-only). `__EGL_VENDOR_LIBRARY_FILENAMES=50_mesa.json` (force Mesa EGL globally — prevents NVIDIA EGL waking dGPU). `QT_LOGGING_RULES=kwin_libinput.warning=false` (suppress touchpad spam). | BUG-050, BUG-046c |
| `/etc/modprobe.d/nvidia.conf` | `NVreg_DynamicPowerManagement=0x02` (fine-grained DPM — GPU sleeps aggressively). `nvidia-drm modeset=1 fbdev=1` (KMS). | BUG-047: NVIDIA wasted 8W idle. ⚠️ **KNOWN CONFLICT:** DPM=0x02 keeps NVIDIA at P8/210MHz during light workloads (e.g. Chrome). See LUMINOS_DECISIONS.md. |
| `/etc/udev/rules.d/` | NVIDIA PCI auto power-off when idle. | BUG-047 |
| `~/.config/chrome-flags.conf` | `--ozone-platform=wayland` only. All GPU flags live in chrome-luminos. | BUG-058: global flags injected broken options on every launch. |
| `/usr/local/bin/chrome-luminos` | GPU picker (kdialog). AMD: Wayland+Vulkan+VAAPI (`radeon_icd.json`). NVIDIA: XWayland+Vulkan (`nvidia_icd.json`). Overrides `__EGL_VENDOR_LIBRARY_FILENAMES` for NVIDIA path. **Any Chrome task: read `docs/LUMINOS_HANDBOOK.md` Part 11 first.** | BUG-046 through BUG-062. |
| `~/.config/kwinoutputconfig.json` | `sharpness: 0.35`, `vrrPolicy: "Never"` | Intentional display tuning. |
| `~/.local/share/applications/google-chrome.desktop` | Routes all Chrome launches through `chrome-luminos`. | AUR entry bypassed GPU picker. |
| `~/.local/share/kio/servicemenus/luminos-gpu-*.desktop` | Dolphin right-click GPU picker for executables and .desktop files. | Universal GPU launcher (Decision 16). |

---

## 10. File Map

### Go Daemons (`cmd/`)
| Path | Description |
|------|-------------|
| `cmd/luminos-ai/main.go` | Unix socket IPC — central routing daemon |
| `cmd/luminos-power/main.go` | EPP thermal, fan curve v5, beast mode, AC/battery |
| `cmd/luminos-sentinel/main.go` | Process security — CAP_SYS_PTRACE, /proc scan |
| `cmd/luminos-router/main.go` | .exe classifier — 80% rules + 20% ONNX fallback |
| `cmd/luminos-ram/main.go` | v3.0 — LIRS IRR, HotSet N=8, OnScreen guard, KWin D-Bus |

### HIVE
| Path | Description |
|------|-------------|
| `scripts/hive-daemon.py` | Port 8078 — routing, model lifecycle, inference |
| `src/hive/HiveChat.qml` | Main chat UI (max-width 720px) |
| `src/hive/HistorySidebar.qml` | Conversation history |
| `scripts/hive-start-model.sh` | Start llama-server with a model |
| `scripts/hive-idle-watchdog.sh` | Auto-kill llama-server after 5min idle |

### KCMs + Widgets
| Path | Description |
|------|-------------|
| `src/kcms/kcm_luminos_keyboard/` | Keyboard backlight (C++/QML, 7 modes) |
| `src/kcms/kcm_luminos_hive/` | HIVE AI settings KCM |
| `src/widgets/org.luminos.powerwidget/` | Power monitor Plasma widget |
| `src/widgets/org.luminos.ramwidget/` | RAM monitor Plasma widget |

### Scripts → `/usr/local/bin/`
| Script | Description |
|--------|-------------|
| `scripts/luminos-notes.sh` | SQLite knowledge base |
| `scripts/luminos-display-hz` | Hz settings dialog (kdialog) |
| `scripts/luminos-60hz` / `luminos-120hz` | Direct Hz switch |
| `scripts/luminos-gpu-launch` | GPU picker for any app |
| `scripts/luminos-nvidia-run` | Wake NVIDIA PCI gate + PRIME env + exec |

### Archive (DO NOT RESTORE)
`archive/windows-hive-2026/`, `archive/gtk4-ui/`, `archive/hyprland/`, `archive/stale-docs/`

---

## 11. Absolute Do-Nots

| Target | Reason |
|--------|--------|
| `.env` | Credentials — never touch |
| `data/hive.db` | Database — never touch |
| `TAG SCHEMA` in STATUS.md | Locked format — see LUMINOS_STATUS.md |
| `cmd/` Go daemons | Only touch when explicitly instructed |
| `hive-swap-server.py` (port 8079) | RETIRED — do not reference |
| `orchestrator.py` | RETIRED — do not reference |
| Tahoe macOS theme | White panel bugs — archived, do not restore |

---

## 12. Power & Thermal — Summary

Full detail: `docs/LUMINOS_HANDBOOK.md` Part 4.

**Fan curve v5 (ACTIVE, 2026-05-24):**
CPU/GPU: `30c:0%,40c:5%,45c:22%,50c:55%,60c:88%,70c:100%,80c:100%,90c:100%`
Mid fan:  `30c:0%,40c:0%,45c:15%,50c:37%,60c:59%,70c:70%,80c:88%,90c:100%`

**Adaptive Governor v4.0:** `cap = 1.8GHz + (load/100) × (hwMax − 1.8GHz)`, EMA α=0.3, iGPU dominance penalty ≤300MHz, 70/30 smooth, >150MHz threshold to write sysfs.

**Thermal zones (AC):** Hot=87°C→3GHz | Emergency=92°C→2GHz+Quiet | 5°C hysteresis on exits.
**Battery:** ZoneWarm=62°C→3.5GHz | ZoneHot=72°C→2.5GHz.

**EPP:** `power` always except beast mode (`performance`). Always call `setEPPAfterAsusctl()` with 350ms sleep — never write EPP immediately after asusctl.

---

## 13. Mandatory Update Protocol

### After every task
```bash
~/luminos-os/scripts/luminos-notes.sh add [TAG] "[summary]"
luminos-brain log "[summary]"
```
Tags: `[HIVE]` `[POWER]` `[GPU]` `[DISPLAY]` `[RAM]` `[SENTINEL]` `[ROUTER]` `[UI]` `[DOCS]` `[BUG]` `[AUDIT]`

### Doc trigger table — scan after every task

| File | Update when… |
|------|-------------|
| `LUMINOS_STATUS.md` | Any component status changes |
| `LUMINOS_DECISIONS.md` | Architectural/config decision made OR two settings found to conflict |
| `docs/BUGS.md` | Bug found or fixed |
| `AGENTS.md §9` | Any `/etc/` file changed |
| `AGENTS.md §12` | Fan curve, zone thresholds, or EPP policy changed |
| `AGENTS.md §14` | Open task completed or added |
| `docs/CODE_REFERENCE.md` | New file, deleted file, function signature changed |
| `docs/LUMINOS_HANDBOOK.md` | User-facing behaviour changed (power, display, Chrome, Wine, shortcuts) |
| `docs/DAEMON_ARCHITECTURE.md` | Daemon internals changed |
| `docs/LUMINOS_RAM_ARCHITECTURE.md` | luminos-ram changed |
| `HIVE_ARCHITECTURE.md` | HIVE stack changed |

### Never miss these

| What you did | Where it must go |
|---|---|
| Changed `/etc/modprobe.d/` | AGENTS.md §9 + LUMINOS_DECISIONS.md (include power/perf implications) |
| Changed `/etc/environment` | AGENTS.md §9 — what it overrides + side effects |
| Added/changed udev rule | AGENTS.md §9 + LUMINOS_DECISIONS.md |
| Made a sysfs write permanent | AGENTS.md §9 + LUMINOS_DECISIONS.md |
| Removed a flag from a launcher | BUGS.md — why it was wrong, what it broke |
| Disabled/enabled a service | LUMINOS_STATUS.md |
| Two settings conflict | LUMINOS_DECISIONS.md — both sides + tradeoff + cross-ref both bugs |
| Bug caused by a previous fix | BUGS.md — cross-reference the original fix that introduced it |

### Git commit format
```bash
git add -A && git commit -m "type(scope): description

Agent: [claude-code|gemini-cli|antigravity|cowork]
Task: [what was asked]" && git push origin main
```

---

## 14. Open Tasks

1. Eye model download + wire vision route in hive-daemon.py
2. KDE right-click service menus for HIVE (kcm_luminos_hive.so already installed)
3. ydotool type-into-apps integration
4. Firefox WhiteSur theme
5. HIVE chat web panel (Flask localhost:7437)
6. Go orchestrator (replace Python hive-daemon.py)
7. Zone indicator Plasma widget
8. SDDM custom Luminos theme

---

## 15. Emergency Recovery

Full reference with root causes: `docs/LUMINOS_HANDBOOK.md` Emergency Card.

| Symptom | Fix |
|---------|-----|
| Fans silent at 70°C+ | `sudo systemctl restart luminos-power` |
| HIVE not responding (SUPER+SPACE) | `pkill -f hive-daemon.py; pkill -f llama-server; SUPER+SPACE` |
| NVIDIA won't sleep (8W idle) | Check `/etc/environment` has `__EGL_VENDOR_LIBRARY_FILENAMES=...50_mesa.json` |
| Chrome GPU process dead / SwiftShader | Check `chrome://gpu` GL_RENDERER. If SwiftShader: verify `VK_ICD_FILENAMES=radeon_icd.json` in `/usr/local/bin/chrome-luminos`. Clear `~/.config/google-chrome/{GPUCache,GrShaderCache,ShaderCache}`. |
| Chrome NVIDIA path stutters (GL=NVIDIA confirmed but slow) | `nvidia-smi` — check pstate. P8/210MHz = `NVreg_DynamicPowerManagement=0x02` throttling GPU. Known conflict — see LUMINOS_DECISIONS.md. |
| Panel broken/white | `systemctl --user restart plasma-plasmashell` |
| KDE Settings can't find HIVE KCM | `kbuildsycoca6 --noincremental` |
| Display stuck at wrong Hz | `luminos-120hz` or `luminos-60hz` |
| KWin crash (blank screen) | `kwin_wayland --replace &` |
| Launcher blank/empty | Set `applicationsDisplay=1` in `plasma-org.kde.plasma.desktop-appletsrc` |

---

## 16. Reply Format (mandatory — end every response with this)

```
REPLY TO MANAGEMENT:
  - Task completed: [yes/no/partial]
  - What changed: [list files modified/created]
  - LUMINOS_STATUS.md updated: [yes/no]
  - Luminos Notes updated: [yes/no]
  - Ready for: [what comes next]
```
