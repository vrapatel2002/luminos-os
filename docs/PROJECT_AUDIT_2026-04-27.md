# Luminos OS — Full Project Audit
**Date:** 2026-05-06  
**Auditor:** claude-code  
**Method:** Read-only. No files modified. No commits made.

---

## System Reality vs Documentation

### Hardware

| Component | Docs Say | Actual | Status |
|---|---|---|---|
| NVIDIA RTX 4050 | 6GB | 6141 MiB, driver 595.58.03 | ✅ Accurate |
| AMD XDNA NPU | /dev/accel0 active | /dev/accel0 ✓, firmware 1.5.2.380 | ✅ Accurate |
| KDE Plasma | 6.6.4 Wayland | plasmashell 6.6.4 ✓ | ✅ Accurate |
| Wine | 11.6 | wine-11.6 ✓ | ✅ Accurate |

### Go Daemons

| Daemon | Docs Say | Actual | Status |
|---|---|---|---|
| luminos-ai | ✅ Running | `active` ✓ | ✅ Accurate |
| luminos-power | ✅ Running | `active` ✓ | ✅ Accurate |
| luminos-sentinel | ✅ Running | `active` ✓ | ✅ Accurate |
| luminos-router | ✅ Running | `active` ✓ | ✅ Accurate |

### HIVE Models

| Agent | LUMINOS_STATUS.md says | CLAUDE.md says | Actual file on disk | Status |
|---|---|---|---|---|
| Nexus | Dolphin3-Llama3.1-8B | Llama-3.1-8B-Instruct ❌ | Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf | ⚠️ CLAUDE.md wrong |
| Bolt | Qwen2.5-Coder-7B | Qwen2.5-Coder-7B ✓ | Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf | ✅ Accurate |
| Nova | DeepSeek-R1-0528-8B | DeepSeek-R1-Distill-Qwen-7B ❌ | DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf | ⚠️ CLAUDE.md wrong |
| Sentinel | MobileLLM-140M NPU | MobileLLM-R1-140M-INT8.onnx | (ONNX, not GGUF, NPU) | ✅ Accurate |
| Eye | 📋 Pending | Not listed | Not on disk (no Qwen-VL file) | ✅ Accurate (pending) |
| Old Nova | — | — | DeepSeek-R1-Distill-Qwen-8B-Q4_K_M.gguf still on disk | ⚠️ Orphan file, 4.4GB wasted |

**Note:** nomic-embed-text-v1.5.Q4_K_M.gguf (81MB) exists in the models folder — not documented anywhere.

### HIVE Services

| Component | Docs Say | Actual | Status |
|---|---|---|---|
| HIVE popup (SUPER+SPACE) | ✅ Working | /usr/local/bin/luminos-hive-popup exists, executable | ✅ Accurate |
| HIVE Daemon (port 8078) | ✅ Working | scripts/hive-daemon.py present; luminos-hive-popup launches it | ✅ Accurate |
| HIVE Swap Server (port 8079) | 🛠 Retired | Still referenced in launcher trap cleanup line | ⚠️ Minor — retired but still in trap |
| luminos-hive.service | ✅ Working | Runs `src/hive/orchestrator.py` — NOT hive-daemon.py | ❌ **WRONG** — service runs old orchestrator, not the daemon the popup uses |
| HIVE Settings KCM | ✅ Working, kcm_luminos_hive.so | `ls /usr/lib/qt6/plugins/kcms/kcm_luminos_hive*` → NOT FOUND | ❌ **WRONG** — KCM does not exist on disk |

### Git State

| Item | Expected | Actual | Status |
|---|---|---|---|
| Branch pushed | Every task pushes (AGENTS.md rule) | 6 commits ahead of origin/main, NOT pushed | ❌ **RULE VIOLATION** |
| Submodules | Clean | research/turboquant/* has modified/untracked content | ⚠️ Dirty submodules |

---

## Docs Needing Updates

### P1 — Wrong / Broken Information

**`CLAUDE.md`** — Model names are the OLD pre-April-2026 stack:
- Line: `Nexus: Llama-3.1-8B-Instruct-Q4_K_M.gguf` → should be `Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf`
- Line: `Nova: DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf` → should be `DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf`
- This file is loaded by every claude-code session — stale models mean wrong agent instructions every time.

**`LUMINOS_STATUS.md`** — KCM plugin marked Working but doesn't exist:
- `HIVE Settings in KDE | ✅ Working | Native KCM plugin (kcm_luminos_hive.so)` is false.
- The .so is not installed at `/usr/lib/qt6/plugins/kcms/`.

**`LUMINOS_STATUS.md`** — luminos-hive.service description is misleading:
- Service runs old `orchestrator.py`. The actual HIVE popup flow uses `hive-daemon.py` (port 8078), which the launcher starts separately. The service running orchestrator.py alongside this may cause two competing Python processes managing the same llama-server.

**`FOCUS.md`** — Entirely stale task list and old model names:
- Task 1 "HIVE popup chat window" → DONE months ago
- Task 3 "Model upgrades (Dolphin3 Nexus, R1-0528 Nova)" → DONE April 2026
- Model names still show old Llama-3.1-8B and DeepSeek-R1-Distill-Qwen-7B
- Last updated: 2026-04-26 — not touched since the April upgrade

### P2 — Missing Important Info

**`CLAUDE.md`** — No mention of:
- `hive-daemon.py` (the actual orchestration daemon at port 8078)
- `HistorySidebar.qml` (new sidebar component that exists in src/hive/)
- `luminos-hive.service` vs popup launcher distinction
- History sidebar feature (conversations persisted in LocalStorage)
- The popup now routes through hive-daemon, NOT directly to llama-server

**`AGENTS.md`** (Section 4 — Bare-Metal Architecture):
- "Routing: Dolphin 3.0 (GPU) is the front-end. Routes to Qwen 3.6 (Coder)..." — "Qwen 3.6" is wrong, should be "Qwen2.5-Coder-7B". Minor but confusing.
- No mention of hive-daemon.py's role in the architecture.
- No mention that hive-swap-server.py is retired.

**`HIVE_VISION.md`** — Architecture diagram shows `luminos-hive-cli (Go binary)` in the call chain. This binary does not exist. The actual path is: QML popup → HTTP POST to hive-daemon.py on :8078. The diagram is aspirational, not current reality.

**`docs/DAEMON_ARCHITECTURE.md`** — Diagram shows `llama-server (Python)` as a leaf node managed by `luminos-sentinel`. In reality, llama-server is a compiled C++ binary (`/usr/local/bin/llama-server`), not Python. Also doesn't show hive-daemon.py at all.

**`HIVE_README.md`** — Bolt model listed as "Qwen-3.6-7B" (wrong shorthand, non-standard name). Actual is Qwen2.5-Coder-7B.

### P3 — Outdated But Not Blocking

**`docs/PROMPTS.md`** — Completely full of Hyprland references:
- "Hyprland config: ~/.config/hypr/hyprland.conf"
- "OS: Arch Linux, Wayland compositor: Hyprland 0.54.3"
- These are session-start prompts for the old Hyprland era. Hyprland is BANNED (Decision 12). These prompts should never be used and will confuse any agent that reads them.

**`docs/ROADMAP.md`** — Still references Python/GTK4 UI approach:
- Phase 5.1 mentions "luminos_theme.py" and Python UI redesign tasks
- This was superseded by Decision 11 (KDE Plasma / Qt/QML stack locked)
- Roadmap hasn't been updated to reflect the actual KDE Plasma focus

**`LUMINOS_PROJECT_SCOPE.md`** — Contains "SmolLM2-360M or DistilBERT (fits NPU budget)" — SmolLM2 was evaluated and replaced by MobileLLM-R1-140M (Decision in DECISIONS.md). Wrong model in scope doc.

**`FOCUS.md`** — The whole file needs a rewrite. It's a snapshot of April 2026 state.

### P4 — Nice to Have

**`LUMINOS_STATUS.md`** — The orphaned `DeepSeek-R1-Distill-Qwen-8B-Q4_K_M.gguf` (4.4GB) and `nomic-embed-text-v1.5.Q4_K_M.gguf` (81MB) in the models directory are not documented. Someone should either delete the old Nova file or at minimum mark it as "archived" to free 4.4GB.

**`LUMINOS_STATUS.md`** — Nova's speed is listed as "10.3 TPS CPU" but Nova is now a different model (R1-0528-Qwen3-8B vs the old Distill). The TPS figure may be outdated.

---

## Agent Files Audit

### AGENTS.md
| Check | Result |
|---|---|
| luminos-notes.sh mentioned correctly | ✅ Section 6.1 correct |
| MemPalace references | ✅ None (Decision 17 cleaned this up) |
| Mandatory steps current | ✅ Steps are correct |
| Model roster in Section 4 | ⚠️ "Qwen 3.6 (Coder)" — should be "Qwen2.5-Coder-7B" |
| hive-daemon.py mentioned | ❌ Not mentioned anywhere |
| hive-swap-server.py retired status | ❌ Not mentioned as retired |
| code-review-graph MCP | ✅ Documented (though MCP not available in claude-code sessions) |

### CLAUDE.md
| Check | Result |
|---|---|
| luminos-notes.sh mentioned | ✅ Correct |
| MemPalace references | ✅ None |
| Model names | ❌ Both Nexus and Nova show old pre-April-2026 models |
| hive-daemon.py | ❌ Not mentioned |
| HistorySidebar.qml | ❌ Not mentioned |
| Mandatory commit format | ✅ Correct |

### GEMINI.md
| Check | Result |
|---|---|
| MemPalace retired note | ✅ Has `[CHANGE: gemini-cli | 2026-04-26] MemPalace retired. Use luminos-notes.sh instead.` |
| code-review-graph MCP | ✅ Extensive documentation |
| Session start prompt model names | ⚠️ Prompt template doesn't specify models explicitly (neutral — OK) |
| Banned stack listed | ✅ First line lists banned stack correctly |

---

## HIVE Vision Gap Analysis

Comparing `docs/HIVE_VISION.md` planned features vs current reality:

### Built and Working ✅
- QML6 native popup window (SUPER+SPACE)
- Multi-agent routing (Nexus→Bolt/Nova via [ROUTE:X] tags)
- Model hot-swapping (hive-start-model.sh + hive-daemon.py)
- TurboQuant turbo4 KV cache compression on GPU models
- AI Mode (Nova on CPU + GPU model simultaneously)
- LocalStorage chat persistence (HiveChat.qml + SQLite)
- Conversation history sidebar (HistorySidebar.qml)
- Per-code-block copy buttons in responses
- Progress polling (pollProgress via /progress endpoint)
- Chip-based routing hints (Code→Bolt, Learn/Strategize→Nova)
- Thinking trace UI (collapsible, shows agent and timing)

### Partially Built ⚠️
- **KDE right-click context menu** — documented as planned, `luminos-hive-settings` script exists but KCM .so not installed
- **Type into apps (ydotool)** — mentioned in multiple places, not implemented
- **hive-daemon.py /progress endpoint** — QML polls it, but unclear if daemon actually implements all stage values

### Not Built ❌
- **Eye (Qwen2.5-VL-7B vision)** — model not downloaded, eye.py stub exists
- **luminos-hive-cli Go binary** — shown in HIVE_VISION.md architecture diagram, doesn't exist
- **HIVE chat web panel (Flask :7437)** — still in Open Tasks in STATUS.md
- **Go orchestrator to replace Python** — in Open Tasks
- **SUPER+H global text-selection shortcut** — not wired
- **SUPER+SHIFT+H screen understanding** — not wired
- **Zone indicator Plasma widget** — in Open Tasks
- **SDDM custom Luminos theme** — in Open Tasks
- **Firefox WhiteSur theme** — in Open Tasks

---

## Current Working State

**What definitely works right now on the G14:**

- ✅ SUPER+SPACE opens QML chat popup
- ✅ Chat sends to hive-daemon.py on :8078
- ✅ Nexus responds and routes to Bolt/Nova
- ✅ Model swap takes ~5-30s depending on cold/warm state
- ✅ Conversations persist to LocalStorage (HiveChatDB)
- ✅ Sidebar shows history, can load past conversations, delete them
- ✅ Relative timestamps in sidebar
- ✅ Code block rendering with per-block copy
- ✅ Go daemons all active (power, sentinel, router, ai)
- ✅ NPU active (MobileLLM-140M via HATS)
- ✅ Wine 11.6 for .exe compat
- ✅ KDE 6.6.4 Wayland

**What is uncertain / probably broken:**

- ❓ luminos-hive.service (runs orchestrator.py) — may conflict with hive-daemon.py if both start. The popup launcher starts hive-daemon.py independently, so the systemd service may be redundant or causing dual-process issues.
- ❓ KCM plugin — STATUS.md says working but binary not on disk. Either it was on a different machine or was never built.
- ❓ nomic-embed-text model — present in models dir, nothing uses it

**6 unpushed commits** — last push was before all the sidebar redesign work (May 2-6). All HIVE QML improvements from the past 4 days are local only.

---

## Needs Immediate Update (Priority List)

### P1 — Wrong/Broken Information
1. **CLAUDE.md** — Nexus/Nova model names are wrong (old stack)
2. **LUMINOS_STATUS.md** — KCM plugin marked ✅ Working but doesn't exist
3. **LUMINOS_STATUS.md** — luminos-hive.service / hive-daemon.py relationship is unclear/misleading
4. **FOCUS.md** — All task items stale, model names wrong, entire file is outdated
5. **Git** — 6 commits not pushed (AGENTS.md rule: always push after every task)

### P2 — Missing Important Info
6. **CLAUDE.md** — No mention of hive-daemon.py, HistorySidebar.qml, port 8078 architecture
7. **AGENTS.md** — "Qwen 3.6" wrong; no mention of hive-daemon.py or retired swap server
8. **HIVE_VISION.md** — luminos-hive-cli Go binary shown in diagram but doesn't exist

### P3 — Outdated But Not Blocking
9. **docs/PROMPTS.md** — Full of Hyprland references (banned WM), needs archiving/rewrite
10. **docs/ROADMAP.md** — Python/GTK4 phases still listed, superseded by Decision 11
11. **HIVE_README.md** — "Qwen-3.6-7B" wrong shorthand
12. **LUMINOS_PROJECT_SCOPE.md** — SmolLM2 listed for NPU (replaced by MobileLLM)

### P4 — Nice to Have
13. **LUMINOS_STATUS.md** — Old Nova GGUF (4.4GB) undocumented orphan on disk
14. **LUMINOS_STATUS.md** — nomic-embed-text model present, no documentation

---

## Recommended Update Prompts

**P1-1 (CLAUDE.md model names):**  
"Update CLAUDE.md: change Nexus model to Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf and Nova to DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf. Add hive-daemon.py on port 8078 and HistorySidebar.qml to the component list."

**P1-2 (LUMINOS_STATUS.md KCM):**  
"Update LUMINOS_STATUS.md: change 'HIVE Settings in KDE' from ✅ Working to 📋 Pending (KCM .so not built/installed). Add note that kcm_luminos_hive.so needs to be compiled and installed to /usr/lib/qt6/plugins/kcms/."

**P1-3 (LUMINOS_STATUS.md service confusion):**  
"Update LUMINOS_STATUS.md: clarify that luminos-hive.service runs orchestrator.py (legacy, may be redundant) while the popup launcher starts hive-daemon.py directly. Mark orchestrator.py service as 'Under Review' and hive-daemon.py as the primary popup backend."

**P1-4 (FOCUS.md full rewrite):**  
"Rewrite FOCUS.md entirely: update model names to Dolphin3/R1-0528/Qwen2.5-Coder, update task list to reflect actual current priorities (Eye model, panel polish, KCM build, ydotool, right-click menus), remove completed HIVE popup and model upgrade tasks."

**P1-5 (Git push):**  
"Push the 6 unpushed commits to origin/main to comply with AGENTS.md mandatory push rule."

**P2-6 (CLAUDE.md architecture):**  
"Add to CLAUDE.md: hive-daemon.py (port 8078) is the HIVE backend; QML popup sends POST /chat to it; HistorySidebar.qml is the history panel; hive-swap-server.py (8079) is retired."

**P2-7 (AGENTS.md model name fix):**  
"Update AGENTS.md Section 4: change 'Qwen 3.6 (Coder)' to 'Qwen2.5-Coder-7B'. Add hive-daemon.py to architecture description. Note hive-swap-server.py as retired."

**P2-8 (HIVE_VISION.md diagram):**  
"Update HIVE_VISION.md architecture diagram: remove luminos-hive-cli (Go binary, doesn't exist). Replace with actual flow: QML popup → HTTP POST :8078 → hive-daemon.py → llama-server."

---

*Audit complete. No files were modified. All findings are read-only observations.*
*Run `git push origin main` to push 6 pending commits first.*
