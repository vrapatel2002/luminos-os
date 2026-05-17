# LUMINOS OS — PROJECT MASTER FILE
# Generated: May 2026
# Purpose: Complete context transfer for new chat sessions
# IMPORTANT: Read this + AGENTS.md + hive-brain.md before starting any task

---

## 1. PROJECT OVERVIEW

**Project Name:** Luminos OS
**Repo:** https://github.com/vrapatel2002/luminos-os
**Branch:** main
**User:** Sam (username: shawn on G14)

### Core Purpose
Custom Arch Linux distribution for ASUS ROG G14 GA403UU.
AI-native. Privacy-first. Windows compatible.
Triple boot: Windows / Default Arch / Luminos OS.

### Vision
A privacy-first Windows alternative that:
- Runs ALL Windows apps automatically
- Has AI woven into every layer (not bolted on)
- Never requires manual tuning from user
- Feels as smooth as macOS
- Keeps all data local — no cloud

### What It Is NOT
- Not a themed Linux distro
- Not Ubuntu with AI slapped on
- Not an AI assistant OS
- Not complicated — zero manual tuning ever

---

## 2. HOW IT WORKS (WORKFLOW)

### Multi-Agent Development System
Five tools work together:

**Claude Chat (this chat)**
- Architecture, planning, writing prompts
- Debugging edge cases, reviewing agent work
- Never writes files directly

**Gemini CLI (--yolo flag)**
- Daily tasks, config changes, bash scripts
- File edits, git operations, quick fixes
- 80% of daily work — cheapest option
- Start: `cd ~/luminos-os && gemini --yolo`

**Claude Code**
- Complex multi-file Go/Python code
- Hard bugs needing deep reasoning
- Uses DeepSeek V4 Pro via OpenRouter
- Start: `cd ~/luminos-os && claude`
- Settings: `~/luminos-os/.claude/settings.local.json`

**Antigravity (Opus model)**
- Full feature builds (100+ lines)
- Complex UI work
- Has output token limits — split long prompts
- CLI mode: `antigravity chat "prompt"`

**Cowork (Claude Desktop)**
- Autonomous background tasks
- Delegates to Gemini CLI and Claude Code
- Open folder first: File → Open Folder → ~/luminos-os
- Cannot open GUI apps like Antigravity

### HIVE Brain Protocol (MANDATORY)
```bash
# BEFORE any action:
luminos-brain safe "what you are about to do"
# → YES: proceed
# → NO: find another way

# AFTER any action:
luminos-brain log "what you did"

# Query knowledge:
luminos-brain query "topic"    # grep-based
luminos-brain think "question" # RAG semantic
luminos-brain status           # system health
```

### Session Start (Every Agent, Every Time)
```bash
cat ~/luminos-os/AGENTS.md
cat ~/luminos-os/docs/LUMINOS_OS_GUIDE.md
luminos-brain status
luminos-brain query "[task topic]"
```

### Git Commit Format (Mandatory)
```
type(scope): description

Agent: [gemini-cli|claude-code|antigravity|cowork]
Task: [what was asked]
```

---

## 3. TECHNICAL ARCHITECTURE & STACK

### Hardware (ASUS ROG G14 GA403UU — Never Change)
```
CPU:     AMD Ryzen 7 8845HS (Zen 4, 16 threads, 5.1GHz boost)
NPU:     AMD XDNA 1 (RyzenAI-npu1, 16 TOPS)
GPU:     NVIDIA RTX 4050 Laptop 6GB (dGPU) — SM89
iGPU:    AMD Radeon 780M RDNA3
RAM:     16GB LPDDR5X
Storage: NVMe SSD (~330GB partition for Luminos)
Display: 2560x1600 @ 2x HiDPI scaling (192 DPI)
```

### GPU Assignment Rules (CRITICAL — Never Change)
```
iGPU (Radeon 780M):  KDE desktop, ALL UI rendering,
                      Chrome, all Electron apps
dGPU (RTX 4050):     HIVE AI inference, gaming, training
NPU (XDNA 1):        Sentinel + Router (HATS)

DRI_PRIME=0 = AMD iGPU (default for everything)
DRI_PRIME=1 = NVIDIA (only games/HIVE)

NVIDIA power gated when idle → 0W (sleeping)
Wakes automatically when needed
```

### Base OS Stack (Locked)
```
Base:         Arch Linux (rolling release)
Desktop:      KDE Plasma 6.6.4 (Wayland session)
Compositor:   KWin
Login:        SDDM
GPU Control:  supergfxctl (always Hybrid mode)
Fan/Power:    asusctl v6.3.6
Shell:        ZSH + Starship prompt
```

### Tech Stack (Locked)
```
AI Daemons:    Go
AI Inference:  llama.cpp (TurboQuant fork, SM89 CUDA)
AI Models:     Python (llama-cpp-python)
Custom UI:     Qt/QML + JavaScript
Package Mgr:   pacman + AUR (yay)
```

### BANNED Technologies (Never Use)
```
Ollama         → use llama.cpp direct
Docker         → use native daemons
GTK4/PyGObject → use PyQt6 or bash
Hyprland       → KDE Plasma only
hnswlib        → use FAISS (SEGV crash always)
chromadb       → use SQLite or FAISS
MemPalace      → permanently retired (hnswlib SEGV)
```

### NVIDIA Driver
```
Driver:  nvidia-dkms 595.58.03
CUDA:    13.2.1 at /opt/cuda
Modules: /etc/modules-load.d/nvidia.conf
Power:   /etc/udev/rules.d/99-nvidia-power-gate.rules
         NVreg_DynamicPowerManagement=0x02
```

### llama.cpp Build
```
Fork:    TheTom/llama-cpp-turboquant
Flags:   GGML_CUDA=ON, SM89, FA_ALL_QUANTS=ON
KV cache: -ctk turbo4 -ctv turbo4 --flash-attn
Binary:  /usr/local/bin/llama-*
```

---

## 4. CORE COMPONENTS & FEATURES

### A. Go Daemons (All Running as systemd services)

**luminos-ram** (LIRS v3.4)
- LIRS algorithm for RAM management
- Hot set 1-4: full RAM, no touch
- Warm set 5-8: MADV_COLD after 5min idle
- Cold set 9+: MADV_PAGEOUT immediately
- Chrome renderers: MADV_PAGEOUT at 10min idle
- Chrome tabs: discard at 30min idle
- Video URLs protected 25min after focus
- macOS-style silent restart on memory leak
- CDP health check on startup
- Restart=always (5s recovery)
- HTTP metrics: :9091/metrics and :9091/meminfo
- Config: ~/.config/luminos-ram.conf

**luminos-power** (v2.1)
- Load-based profile switching (not temperature)
- Battery → always Quiet
- AC + idle (<40% CPU, 3min) → Quiet (DEFAULT)
- AC + normal work (>40% CPU, 3min) → Balanced
- AC + GPU gaming (>80% GPU, 30s) → Performance
- Emergency: temp >85°C → force Quiet
- Aggressive fan curves in ALL modes
- Fan handles heat, mode changes on LOAD
- Config: compiled into binary

**luminos-sentinel**
- Watches all processes via /proc
- Blocks Wine/Proton accessing ~/.ssh, ~/.gnupg
- Reports to luminos-ai socket
- Future: HATS AI classification

**luminos-router**
- Classifies .exe files into zones
- Zone 1: Native Linux binary
- Zone 2: Wine (standard Windows app)
- Zone 3: Firecracker (planned)
- Zone 4: KVM (anticheat games)
- Socket: /tmp/luminos-router.sock

### B. ZRAM + RAM Stack
```
ZRAM:         8GB zstd (replaces SSD swap)
swappiness:   30 (proactive compression)
KSM:          enabled (page merging)
earlyoom:     installed (crash prevention)
page-cluster: 3 (bulk page restoration)
vm.vfs_cache_pressure: 50

ZRAM compression ratio: ~2.8x
Effective RAM: 16GB + 22GB ZRAM = ~24GB usable
```

### C. HIVE AI System

**Architecture:**
- No Ollama. No Docker. llama.cpp direct.
- Orchestrator: src/hive/hive-daemon.py
- Popup server: scripts/hive-popup-server.py
- Popup UI: scripts/hive-popup-ui.html
- Backend: scripts/hive_backend.py

**Models (at ~/.local/share/luminos/models/hive/):**
```
Nexus:  dolphin3.0-llama3.1-8b-Q4_K_M.gguf  → GPU ~36t/s
Bolt:   Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf → GPU ~38t/s
Nova:   DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf → CPU ~10t/s
Embed:  nomic-embed-text-v1.5.Q4_K_M.gguf    → CPU (RAG)
Eye:    NOT DOWNLOADED YET (Qwen2.5-VL-7B)
```

**Routing by message keywords:**
- "code/script/write" → Bolt
- "analyze/think/why" → Nova (AI mode)
- default → Nexus

**HIVE Popup:**
- Shortcut: SUPER+SPACE (Meta+Space)
- Script: /usr/local/bin/luminos-hive-popup
- CRITICAL: Lines 9-54 = Wayland env setup
- DO NOT TOUCH lines 9-54 — breaks shortcut
- Status: Opens, basic chat works
- Missing: Native PyQt6 window (still uses browser)

**HIVE Brain (Security Guard):**
- Logbook: ~/.local/share/luminos/hive-brain.md
- CLI: /usr/local/bin/luminos-brain
- RAG: src/hive/luminos-rag.py (nomic-embed + FAISS)
- MCP: src/hive/hive-mcp.py (stdio, Claude Code native)
- Terminal watcher: /usr/local/bin/hive-watch
- Crash analyzer: /usr/local/bin/hive-crash-analyzer
- preexec hook in ~/.zshrc

### D. Windows Compatibility
```
Zone 2 (Wine 11.6): Standard apps, auto-launches
Wine launcher:      /usr/local/bin/luminos-wine-launcher
                    Shows GPU selector (AMD/NVIDIA)
MT5 launcher:       /usr/local/bin/mt5-luminos
                    Forces AMD, DXVK disabled
.exe association:   luminos-wine.desktop → gpu selector
```

### E. KDE Desktop
```
Theme:       Breeze Dark (Tahoe theme reverted — caused issues)
Scaling:     2x HiDPI (192 DPI)
Sleep mode:  s2idle (instant wake)
Screen lock: enabled on resume
Panel guard: luminos-plasmashell-watchdog.service
```

**KDE Widgets:**
- org.luminos.ramwidget: RAM hot/cold/ZRAM stats
- org.luminos.powerwidget: Mode/temp/fan/NVIDIA status

**KWin Scripts:**
- luminos-maximize: unmaximize → 80% centered window

### F. Chrome Optimization
```
Wrapper:   /usr/local/bin/chrome-luminos
GPU:       DRI_PRIME=0 (AMD iGPU only)
           VK_ICD_FILENAMES → radeon_icd
           NO renderD129 (NVIDIA removed)
Flatpak:   com.google.Chrome
Flags file: ~/.var/app/com.google.Chrome/config/chrome-flags.conf
```

### G. HIVE Brain Files
```
hive-brain.md:        ~/.local/share/luminos/hive-brain.md
luminos-brain CLI:    /usr/local/bin/luminos-brain
RAG index:            ~/.local/share/luminos/hive-rag.index
RAG chunks:           ~/.local/share/luminos/hive-rag-chunks.json
Crash log:            ~/.local/share/luminos/hive-crashes.log
Events log:           ~/.local/share/luminos/hive-events.log
```

---

## 5. KEY CONFIGURATIONS & CODE

### Directory Structure
```
~/luminos-os/
├── cmd/                    # Go daemons source
│   ├── luminos-ai/
│   ├── luminos-power/
│   ├── luminos-ram/
│   ├── luminos-sentinel/
│   └── luminos-router/
├── src/
│   ├── hive/              # HIVE AI system
│   │   ├── hive-daemon.py
│   │   ├── luminos-rag.py
│   │   ├── hive-mcp.py
│   │   └── .venv/         # Python 3.12.13
│   ├── widgets/           # KDE Plasma widgets
│   │   ├── org.luminos.ramwidget/
│   │   └── org.luminos.powerwidget/
│   └── kernels/           # Triton kernels
├── scripts/               # Helper scripts
│   ├── luminos-hive-popup # CRITICAL: lines 9-54 untouchable
│   ├── hive-popup-server.py
│   ├── hive-popup-ui.html
│   ├── hive_backend.py
│   ├── hive_context.py
│   ├── luminos-brain      # HIVE Brain CLI
│   ├── hive-watch         # Terminal watcher
│   ├── hive-crash-analyzer
│   ├── luminos-wine-launcher # GPU selector for Wine
│   ├── mt5-luminos        # MT5 AMD launcher
│   ├── chrome-luminos     # Chrome AMD wrapper
│   ├── luminos-notes.sh   # SQLite notes
│   ├── luminos-keyboard-smart
│   └── install-daemons.sh
├── config/
│   ├── kde/               # KDE config backups
│   ├── gtk/               # GTK settings
│   ├── themes/            # Wallpapers
│   ├── zram-generator.conf
│   ├── 99-luminos-ram.conf
│   └── claude-code-router.json
├── docs/
│   ├── LUMINOS_OS_GUIDE.md       # Full system guide
│   ├── AGENT_HANDOFF.md          # Agent workflow guide
│   ├── HIVE_FUTURE_VISION.md     # HIVE roadmap
│   ├── hive-brain.md             # Brain copy in repo
│   ├── LUMINOS_RAM_ARCHITECTURE.md
│   ├── LUMINOS_RAM_PLAN.md
│   └── BUGS.md
├── AGENTS.md              # Agent constitution
├── CLAUDE.md              # Claude Code rules
├── GEMINI.md              # Gemini CLI rules
├── FOCUS.md               # Current focus
├── LUMINOS_DECISIONS.md   # All decisions (18+)
├── LUMINOS_STATUS.md      # Component status
└── go.mod
```

### Critical File Paths
```
HIVE popup:       /usr/local/bin/luminos-hive-popup
                  LINES 9-54 = CRITICAL WAYLAND SETUP
                  NEVER TOUCH LINES 9-54

Chrome wrapper:   /usr/local/bin/chrome-luminos
Brain CLI:        /usr/local/bin/luminos-brain
Brain file:       ~/.local/share/luminos/hive-brain.md
Wine launcher:    /usr/local/bin/luminos-wine-launcher
MT5 launcher:     /usr/local/bin/mt5-luminos
RAM widget:       ~/.local/share/plasma/plasmoids/org.luminos.ramwidget/
Power widget:     ~/.local/share/plasma/plasmoids/org.luminos.powerwidget/
KWin maximize:    ~/.local/share/kwin/scripts/luminos-maximize/
Panel watchdog:   ~/.config/systemd/user/luminos-plasmashell-watchdog.service
NVIDIA power:     /etc/udev/rules.d/99-nvidia-power-gate.rules
ZRAM config:      /etc/systemd/zram-generator.conf
sysctl:           /etc/sysctl.d/99-luminos-ram.conf
Screen lock:      ~/.config/kscreenlockerrc (LockOnResume=true)
```

### asusctl Correct Syntax (v6.3.6)
```bash
# CORRECT
asusctl profile set Quiet
asusctl profile set Balanced
asusctl profile set Performance
asusctl aura effect static -c ffffff

# WRONG (broken in v6.3.6)
asusctl profile -P Quiet
asusctl fan-curve -m quiet
```

### Python Environment Rules (CRITICAL)
```
System Python:  3.14.4 (KDE tools ONLY)
ML Python:      ~/.pyenv/versions/3.12.13/bin/python3

NEVER:  pip install ML packages system-wide
NEVER:  install hnswlib (SEGV always)
NEVER:  use Python 3.14 for torch/ML
ALWAYS: use pyenv 3.12.13 for ML/AI
ALWAYS: activate venv before pip install

Safe pip: ~/.pyenv/versions/3.12.13/bin/pip
Override: luminos-brain safe "action" --reason "why"
```

### Python Environments
```
Forex bot:    ~/Forex-Trading-Bot-main/.venv
              Python 3.12.13 (pyenv)
              Status: NEEDS REBUILD (check hive-brain)
              
HIVE:         ~/luminos-os/src/hive/.venv
              Python 3.12.13
              Packages: faiss-cpu, llama-cpp-python, flask
              
Triton:       ~/luminos-os/.triton_venv
              Python 3.12.13 (80 packages)
              Status: Healthy
              
MemPalace:    PERMANENTLY RETIRED
              Both venvs removed
              Use luminos-notes.sh instead
```

### Key Decisions (18 total, see LUMINOS_DECISIONS.md)
```
Decision 12: KDE Plasma over Hyprland (permanent)
Decision 13: Go/Python split architecture
Decision 14: HATS architecture for XDNA 1 NPU
Decision 15: Three-phase AI maturity (A+B+C)
Decision 16: Model upgrades (Dolphin3, R1-0528, Qwen3)
Decision 17: MemPalace retired → luminos-notes.sh
Decision 18: Multi-model routing via claude-code-router
```

---

## 6. CURRENT STATUS

### ✅ Working
```
OS & Desktop:
  Arch Linux triple boot
  KDE Plasma 6.6.4 Wayland
  SDDM (Wayland session)
  NVIDIA 595.58.03 + CUDA
  AMD NPU /dev/accel/accel0
  ZSH + Starship + Albert launcher
  Keyboard backlight smart daemon
  s2idle instant wake from sleep
  Screen lock on resume
  Plasmashell watchdog (auto-restart)
  KWin maximize toggle (80% centered)

RAM Management:
  ZRAM 8GB zstd active
  luminos-ram LIRS v3.4 running
  Hot/warm/cold set management
  Chrome renderer compression
  macOS-style silent leak restart
  CDP health check on startup
  RAM widget showing stats

Thermal Management:
  luminos-power v2.1 running
  Load-based switching (not temperature)
  Quiet mode as daily driver
  Aggressive fan curves all modes
  Emergency Quiet at 85°C
  BUG-048 thermal oscillation FIXED
  Power widget in panel

GPU Management:
  NVIDIA power gated (0W idle)
  Chrome using AMD only (BUG-046 fixed)
  NVIDIA power gating rules (BUG-047 fixed)
  Wine GPU selector dialog
  MT5 forced AMD (DXVK disabled)

HIVE Brain:
  hive-brain.md populated
  luminos-brain CLI working
  RAG system (nomic-embed + FAISS)
  Terminal watcher (preexec hook)
  Crash analyzer (auto on coredump)
  Override protocol (soft/hard blocks)
  MCP wrapper for Claude Code
  HIVE popup wired to brain
  Agent protocol updated

AI Infrastructure:
  llama.cpp TurboQuant built
  4 HIVE models downloaded
  HIVE popup opens (SUPER+SPACE)
  HIVE Settings KCM working

Windows Compatibility:
  Wine 11.6 + .exe auto-routing
  Wine GPU selector dialog
  MT5 terminal installed in Wine
  MT5 AMD launcher created
  Forex bot luminos-run.sh (CPU only)
```

### ⚠️ Partial / Needs Work
```
HIVE popup:
  Opens but uses browser (not native window)
  Conversation history works
  Needs PyQt6 native window

KDE Theme:
  Tahoe theme reverted (caused crashes)
  Back to Breeze Dark
  White panel bug never fully fixed
  Pixelated corners at 2x HiDPI unsolved
  Power widget created but needs testing

Forex bot:
  MT5 installed ✅
  luminos-run.sh created ✅
  Venv may need pyenv 3.12 rebuild
  mt5linux bridge: configured localhost:18812
  Status: NOT YET RUNNING end-to-end
```

### ❌ Not Done
```
Eye model download (Qwen2.5-VL-7B)
HIVE right-click KDE service menus
HIVE type into apps (ydotool)
HIVE chat web panel (Flask localhost:7437)
MCP JSON-RPC proper protocol fix
Forex bot end-to-end test
Zone 3 (Firecracker) implementation
SDDM custom Luminos theme
Offline Claude Code via llama-server
```

---

## 7. ROADBLOCKS & UNSOLVED ISSUES

### Active Bugs
```
BUG-046: Chrome using NVIDIA GPU → FIXED
BUG-047: NVIDIA always active → FIXED  
BUG-048: Thermal oscillation → FIXED
BUG-049: Claude Desktop memory leak → MONITORING

BUG-OPEN-01: HIVE popup uses browser not native window
  Cause: PyQt6 WebEngine not wired up
  Fix: rewrite popup to PyQt6 QMainWindow

BUG-OPEN-02: KDE Tahoe theme white panel
  Cause: Theme opaque/ folder has white SVG
  Triggered when window maximizes/touches panel
  Fix: Edit SVGZ properly (needs Inkscape)
  Status: Theme reverted to Breeze, issue deferred

BUG-OPEN-03: Pixelated window corners at 2x HiDPI
  Cause: MacTahoe SVG only has 1.25x/1.5x variants
  Upscaled to 2x = jagged edges
  Fix: kwin-effect-rounded-corners (tried, conflicted)
  Status: Deferred, theme reverted

BUG-OPEN-04: KWin panel fullscreen hide
  Cause: KWin script crashed plasmashell
  Status: Script removed, deferred
```

### Known Conflicts
```
Python 3.14 + torch = CRITICAL (use pyenv 3.12)
Python 3.12 + hnswlib = SEGV (use FAISS)
Vulkan flags + Mesa 26 + Chrome = input lag (fixed)
KWin scripts + panel manipulation = plasmashell crash
MacTahoe theme + 2x HiDPI = pixelated corners
DXVK + Wine MT5 = wakes NVIDIA (fixed with mt5-luminos)
```

### Architecture Constraints
```
6GB VRAM:  One 7B model at a time
16GB RAM:  Nova on CPU uses ~4.7GB extra
NPU XDNA1: 16 TOPS, ONNX via XRT only
           No VitisAI EP on Linux
Python 3.14: System Python, incompatible with ML
2x HiDPI:   SVG themes need 2x variants
```

---

## 8. NEXT STEPS

### Immediate Priority
```
1. Forex bot end-to-end test
   - Verify pyenv 3.12 venv is healthy
   - Run: bash luminos-run.sh
   - Check mt5linux bridge connects
   - Verify bot can place paper trades

2. HIVE popup native window
   - Rewrite to PyQt6 QMainWindow
   - Keep lines 9-54 of luminos-hive-popup
   - Flask backend stays, just change window

3. Eye model download
   Model: Qwen2.5-VL-7B Q4_K_M GGUF
   Repo: bartowski/Qwen2.5-VL-7B-Instruct-GGUF

4. Power widget verification
   Right-click panel → Add Widget → Luminos Power Monitor
   Verify temp/fan/mode showing correctly
```

### Medium Priority
```
5. MCP JSON-RPC proper protocol
   Fix hive-mcp.py to use proper JSON-RPC
   Currently custom protocol, not MCP spec

6. HIVE context scenarios (from vision doc):
   - Chrome extension analyzer
   - System intelligence queries
   - Terminal co-pilot
   - File intelligence right-click
   - Forex bot log reader

7. KDE theme (when ready to try again):
   - Use WhiteSur or Layan (HiDPI-native)
   - OR fix MacTahoe with Inkscape
   - Install kwin-effect-rounded-corners properly
```

### Forex Bot Specific
```
Location: ~/Forex-Trading-Bot-main/
Entry:     bash luminos-run.sh
           (NOT python directly — hides NVIDIA)
Pre-run:   python -m mt5linux 18812 &
MT5:       installed in Wine (~/.wine/)
           Use: mt5-luminos to launch
           
Venv check:
  cd ~/Forex-Trading-Bot-main
  .venv/bin/python3 --version  # must be 3.12.x
  .venv/bin/pip show torch      # must be installed
  
If venv broken:
  luminos-brain safe "rebuild forex venv pyenv 3.12"
  ~/.pyenv/versions/3.12.13/bin/python3 -m venv .venv
  .venv/bin/pip install torch xgboost mt5linux
```

---

## QUICK REFERENCE

### Common Commands
```bash
# Start agents
cd ~/luminos-os && gemini --yolo    # Gemini CLI
cd ~/luminos-os && claude           # Claude Code (DeepSeek)
antigravity chat "prompt"           # Antigravity headless

# HIVE Brain
luminos-brain status
luminos-brain safe "action"
luminos-brain log "what happened"
luminos-brain query "topic"
luminos-brain think "fuzzy question"

# Services
systemctl is-active luminos-ram luminos-power earlyoom
sudo systemctl restart luminos-ram
sudo systemctl restart luminos-power

# Apps
chrome-luminos &          # Chrome (AMD GPU)
mt5-luminos &             # MT5 in Wine (AMD GPU)
/usr/local/bin/luminos-hive-popup  # HIVE chat
# or press SUPER+SPACE

# Thermal
asusctl profile set Quiet
asusctl profile set Balanced
asusctl profile set Performance
sensors | grep temp1

# RAM check
free -h
zramctl
curl -s http://localhost:9091/meminfo
curl -s http://localhost:9091/metrics | grep hot_set
```

### Model Selection Guide
```
Gemini CLI auto:     Simple tasks, configs, scripts
Claude Code DeepSeek: Complex Go/Python, hard bugs
Antigravity Gemini Pro High: Complex UI, full features
Antigravity Opus:    Hardest problems only
Cowork:              Long autonomous tasks (delegates to CLI/Code)
```

### Emergency Recovery
```bash
# Panels disappeared:
plasma-interactiveconsole
# Open: ~/tahoethemes/scriptFullConfigs → Run
# OR:
kstart6 plasmashell &

# From TTY (Ctrl+Alt+F2):
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 \
XDG_RUNTIME_DIR=/run/user/1000 \
kstart6 plasmashell &

# Reapply theme after reset:
bash ~/luminos-os/scripts/apply-tahoe-theme.sh

# Check all services:
systemctl is-active luminos-ram luminos-power \
  luminos-sentinel luminos-router earlyoom ksm

# NVIDIA stuck awake:
for dev in /sys/bus/pci/devices/*/; do
  vendor=$(cat ${dev}vendor 2>/dev/null)
  [ "$vendor" = "0x10de" ] && \
    echo "auto" | sudo tee ${dev}power/control
done
```

---
Last updated: May 2026
Session: This master file covers the full conversation history
Next: Start fresh chat, give agent this file + AGENTS.md + hive-brain.md
