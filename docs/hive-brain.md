---
# HIVE Brain — Luminos OS Security Logbook
# Role: Security Guard — Observe, Report, Guide
# Rule: NEVER fix. NEVER touch. ONLY inform.
# Updated: 2026-05-09 (Full System Audit)

## HOW TO USE THIS FILE
Agents: run `luminos-brain safe "action"` before acting.
Agents: run `luminos-brain log "what you did"` after acting.
Never read this whole file — use luminos-brain CLI.
HIVE reads this file to answer queries.

## PYTHON VERSIONS
System Python: 3.14.4
pyenv available: 3.12.13
Rule: ML/AI always use pyenv 3.12.13
Rule: System tools can use 3.14
Rule: NEVER install torch on system Python

## PYTHON ENVIRONMENTS
### MemPalace Venv (Broken)
Path: /home/shawn/mempalace-venv
Python: 3.12.13
Purpose: chromadb (retired)
Status: BROKEN - python binary missing
Do not touch: yes
Notes: Legacy venv. See .mempalace-venv for active one.

### MemPalace Venv (Active)
Path: /home/shawn/.mempalace-venv
Python: 3.12.13
Purpose: chromadb (retired)
Status: BROKEN - hnswlib SEGV
Do not touch: yes
Notes: hnswlib imports but search crashes. Do not attempt to fix.

### Triton Venv
Path: /home/shawn/luminos-os/.triton_venv
Python: 3.12.13
Purpose: NPU / Triton inference
Status: healthy (80 packages)
Do not touch: yes
Notes: Core Luminos AI stack. Stable.

### Forex Bot Venv
Path: /home/shawn/Forex-Trading-Bot-main/Forex-Trading-Bot-main/.venv
Python: 3.14.4 (CRITICAL CONFLICT)
Purpose: Forex Trading Bot
Status: BROKEN - uses system 3.14 instead of 3.12
Do not touch: yes
Notes: Critical: Installed torch/xgboost on 3.14. Needs pyenv 3.12.13 rebuild.

## PROJECTS
### Luminos OS
Path: ~/luminos-os
Language: Go + Python
Entry: systemctl start luminos-*
Daemons: luminos-ram, power, sentinel, router
Status: active
Notes: Go daemons in cmd/, Python in src/hive/

### Forex Trading Bot
Path: ~/Forex-Trading-Bot-main/Forex-Trading-Bot-main
Language: Python 3.12 ONLY
Entry: python run.py
Pre-run: source .venv/bin/activate
         python -m mt5linux 18812 &
Requires: MT5 terminal running in Wine on port 18812
Status: BROKEN - Environment conflict (Python 3.14)
Critical: NEVER run with system Python 3.14. Packages installed: torch (2.11.0), xgboost (3.2.0), mt5linux (1.0.3).

### code-review-graph
Path: /home/shawn/.local/bin/code-review-graph
Status: found (not in PATH)
Notes: Utility for mapping codebase dependencies.

## KNOWN CONFLICTS
### Python 3.14 + torch
Severity: CRITICAL
Description: torch not installable on Python 3.14
Affected: forex-bot, HIVE orchestrator
Resolution: always use pyenv Python 3.12.13

### Python 3.12 + hnswlib
Severity: CRITICAL  
Description: hnswlib SEGV crash on this system
Affected: MemPalace (retired), any chromadb user
Resolution: use FAISS instead. Never install hnswlib.

### Vulkan flags + Mesa 26 + Chrome
Severity: MEDIUM
Description: experimental Vulkan causes input lag
Affected: Chrome/Flatpak
Resolution: removed from chrome wrapper. Do not re-add.

### MemPalace
Severity: PERMANENT
Description: retired — hnswlib crash unresolvable
Resolution: use luminos-notes.sh instead
Do not attempt to revive MemPalace.

## VENV ISOLATION RULES
Each project has its own venv. Never share.
Never install ML packages system-wide.
Never upgrade packages without checking this file.
Always verify Python version before pip install.

## HIVE MODELS
- DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf (4.4G)
- DeepSeek-R1-Distill-Qwen-8B-Q4_K_M.gguf (4.4G)
- Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf (4.6G)
- Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf (4.4G)
- nomic-embed-text-v1.5.Q4_K_M.gguf (81M)

## RUNNING SERVICES
- luminos-ram: active
- luminos-power: active
- luminos-sentinel: active
- luminos-router: active
- luminos-hive: inactive
- earlyoom: active
- ksm: active

## CRASH LOG
- May 09 11:54:43 kwin_wayland: Touchpad kernel bug: Touch jump detected and discarded
- May 09 12:03:06 kwin_wayland: Touchpad kernel bug: Touch jump detected and discarded
- May 09 12:11:33 kwin_wayland: Touchpad kernel bug: Touch jump detected and discarded
- [historical] MemPalace: hnswlib SEGV on Python 3.12
- [historical] HIVE popup: import: command not found (bash/python mismatch)

## INCIDENT LOG
### 2026-05-09 Terminal watcher active via zshrc preexec hook. Crash analyzer installed. Systemd path watcher on coredump directory.
### 2026-05-09 hive-mcp stdio built. Works with Claude Code natively. Gemini and Antigravity use CLI fallback. Zero RAM when idle.
### 2026-05-09 HIVE popup and daemon wired to brain. System context and semantic knowledge injection active.
### 2026-05-09 Step 3 completed: RAG system built with nomic-embed and FAISS. 'think' command active.
### 2026-05-09 Step 2 completed: luminos-brain CLI built and rules enforced.
### 2026-05-09 test log entry from build
### 2026-04-25 MemPalace Retired
Cause: hnswlib SEGV on Python 3.12
Decision: replaced with luminos-notes.sh SQLite
Prevention: never install hnswlib or chromadb

### 2026-05-09 Chrome Input Lag Fixed
Cause: libinput touch jump detection + powersave governor
Fix: libinput quirks + schedutil governor
See: /etc/libinput/local-overrides.quirks

### 2026-05-09 Vulkan Lag Fixed
Cause: experimental Vulkan/SkiaGraphite flags on Mesa 26
Fix: removed from chrome wrapper
Prevention: do not add Vulkan flags to chrome-luminos

## PENDING ACTIONS
- Install MT5 terminal via Wine for Forex bot
- Fix forex bot torch installation (use pyenv 3.12)
- Download Eye model: Qwen2.5-VL-7B Q4_K_M
- Build luminos-brain CLI (Step 2 of HIVE Brain)
- Build RAG system with nomic-embed + FAISS (Step 3)
- Wire HIVE popup to hive-brain.md (Step 5)

## WHAT HIVE NEVER DOES
- Fix broken packages
- Install or remove anything  
- Touch venvs directly
- Override human decisions
- Run commands without being asked
---
