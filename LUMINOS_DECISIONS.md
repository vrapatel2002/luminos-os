# LUMINOS OS — DECISIONS LOG
# Version: 1.0
# This file explains WHY every major decision was made.
# Read this before questioning anything in LUMINOS_PROJECT_SCOPE.md
# Every entry has: the decision, why we made it, what we rejected and why.

---

## DECISION 21 — One token source of truth feeds every toolkit (anti-fragmentation pipeline)
Date: June 14, 2026
Made by: claude-code
**Status: SCAFFOLDED (repo-only, NOT yet applied live — built during a no-checkpoint training run; apply post-training)**

### The Decision
All visual tokens (color, radius, spacing, motion, font) live in ONE source: `design/luminos-tokens.json`, mirrored by the canonical QML component `src/theme/Theme.qml`. A Go generator `scripts/luminos-theme-gen` fans them out to every toolkit so nothing can drift by hand:
- **QML** (plasmoids + HIVE): the generator copies `Theme.qml` verbatim into each package's `contents/ui/` (and `src/hive/`). It is an **instantiable** `QtObject` (`Theme { id: theme }`), NOT a `pragma Singleton`, so there is no cross-module QML import-path runtime dependency — each Plasma package stays self-contained.
- **Qt/KDE**: generated `config/kde/colors/Luminos.colors` (electric-blue scheme matching the spec; replaces reliance on stock Breeze `#3DAEE9`).
- **GTK + libadwaita**: generated `config/gtk-{3,4}.0/gtk.css` `@define-color` overrides — the only lever that reaches libadwaita.

Consumers refactored off hardcoded hex onto tokens: `org.luminos.powerwidget`, `org.luminos.ramwidget`, `src/hive/HiveChat.qml`, `src/hive/HistorySidebar.qml`. Keyboard KCM left as-is (already Kirigami-themed; its color grid is a *functional* backlight picker, not UI theming — only the one stray `#cc2200` delete badge was aligned to `Kirigami.Theme.negativeTextColor`).

### Why
- The fragmentation problem was never a missing design — `LUMINOS_DESIGN_SYSTEM.md` is complete. It was missing **enforcement**: its Rule 1 ("every color from `luminos_theme.py`") pointed at a file archived when the GTK4 shell was abandoned, so every widget improvised (three different "accent" colors across the codebase). A live token source makes "no hardcoding" actually enforceable (`-check` mode fails CI if any output is stale).
- macOS-grade cohesion has a hard ceiling on Linux: libadwaita ignores `gtk-theme-name`, Electron/Flatpak ship their own toolkits. The achievable target is mechanical consistency across everything we control (Qt + our widgets + theme-respecting GTK), with documented holdouts — not literal parity everywhere.

### What Was Rejected
- **`pragma Singleton` shared QML module** (`import org.luminos.theme`): cleaner on paper, but adds a QML import-path install dependency that breaks plasmoids if the module isn't installed first. Per-package generated copy is more robust for Plasma packaging.
- **Regenerating Theme.qml text from JSON in Go**: error-prone (could emit non-compiling QML). Instead `Theme.qml` is the canonical QML mirror, edited alongside the JSON; the generator distributes it and generates only the non-QML artifacts.
- **Flattening HIVE's warm accent (`#D4784A`) to system blue**: it's a deliberate sub-brand (full warm palette). Routed through tokens as a named `hive.*` group instead; keep-warm-vs-unify is an OPEN DECISION left for Sam.

### Conflict resolved (per Rule 11)
GTK↔Qt toolkit mismatch: repo `config/gtk-{3,4}.0/settings.ini` still shipped `WhiteSur-Dark`/`WhiteSur-cursors` despite BUG-068's live fix (2026-06-11). Synced to Breeze (BUG-071). Tradeoff: Breeze GTK ≠ pixel-identical to Qt Breeze, but token `gtk.css` accent overrides close most of the gap and reach libadwaita; full GTK/Qt parity is not achievable without owning the toolkit.

### Cross-references
- Report/diagnosis: this session's deep-dive; `LUMINOS_DESIGN_SYSTEM.md` (Rule 1 updated to point at the JSON)
- BUG-068 (original incomplete Tahoe revert) + BUG-071 (repo-mirror divergence) → `docs/BUGS.md`
- `src/theme/README.md` — deploy/apply order (post-training only)
- NOT in `AGENTS.md §9` — repo mirrors only; live `~/.config` untouched this session.

---

## DECISION 20 — Training RAM headroom is a REVERSIBLE toggle (luminos-train-ram), not a permanent swap/sysctl change
Date: June 13, 2026
Made by: claude-code
**Status: ACTIVE — `scripts/luminos-train-ram` deployed to /usr/local/bin (verified on/off cycle)**

### The Decision
RAM headroom for ML training is delivered as an on/off toggle (`luminos-train-ram`), mirroring `luminos-train-mode` (GPU). While ON it (1) adds a low-priority on-disk swapfile `/swapfile.train` (default 16G, **not** in /etc/fstab), (2) sets `vm.swappiness=10` at runtime via `sysctl -w` (**not** written to /etc/sysctl.d), and (3) optionally runs the trainer in a memory cgroup (`run` subcommand, MemoryHigh/MemoryMax). OFF removes the swapfile and restores swappiness to the saved baseline. Nothing persists across `off` or reboot.

### Why
- Root cause of training OOM (BUG-070): the box has 14GB RAM and **only zram swap** (compressed RAM, prio 100) — no real spill valve. A 7.6GB memmap dataset + DataLoader pin/worker buffers exhaust anon RAM → instant OOM-kill, no traceback. A real disk swapfile + lower swappiness gives the kernel somewhere to put cold pages and biases reclaim toward the reclaimable memmap cache.
- User constraint (explicit): the normal desktop config is good and must stay unchanged; training needs maximum headroom but only transiently. A toggle satisfies both — "absolute best for training" while ON, "old good thing" the rest of the time.

### What Was Rejected
- **Permanent swapfile in /etc/fstab:** would change normal-desktop memory behavior 24/7 and re-introduce disk swap the system was deliberately run without. Violates the "non-permanent" constraint.
- **Persistent vm.swappiness in /etc/sysctl.d:** same objection — alters idle desktop reclaim balance permanently.
- **Recompiling luminos-ram to whitelist the trainer:** investigated and unnecessary — luminos-ram's victim sets are window-keyed and `isSafeToFreeze` exempts CPU>5%, so a headless busy trainer is already untouched. Adding a code path would be a permanent binary change for no proven benefit (AGENTS §5 minimal-changes).
- **Bigger zram:** zram is compressed RAM; enlarging it cannot relieve genuine RAM exhaustion, it competes for the same RAM.

### Division of ownership
- **luminos-os (this repo):** OS-side headroom only — the toggle above.
- **hope-llm repo (separate):** the application data-path fix (DataLoader workers/pin_memory/get_batch, seq_len/batch sizing). Not changed here.

### Cross-references
- BUG-070 → `docs/BUGS.md`
- `AGENTS.md §10` File Map row for `scripts/luminos-train-ram`
- Companion: `scripts/luminos-train-mode` (GPU power+fans) / BUG-069
- NOT in `AGENTS.md §9` — by design there is no permanent on-disk /etc config to record.

---

## DECISION 19 — RuntimeDirectoryPreserve=yes on all shared-/run/luminos units + luminos-ram capability set
Date: June 10, 2026
Made by: claude-code
**Status: INSTALLED — activates fully on one-time restart (PENDING_RESTART.md)**

### The Decision
1. All five Go daemon units (`luminos-ai`, `luminos-power`, `luminos-router`, `luminos-sentinel`, `luminos-ram`) get `RuntimeDirectoryPreserve=yes`. `luminos-ram` additionally declares `RuntimeDirectory=luminos` (it bound `/run/luminos/ram.sock` without ever declaring the dir).
2. `luminos-ram` bounding set widened: `CAP_SYS_PTRACE` → `CAP_SYS_PTRACE CAP_SYS_NICE CAP_KILL`.

### Why
- systemd removes a RuntimeDirectory when its service stops. Five daemons SHARE `/run/luminos`, so the first restart wipes every sibling's socket. Proven incident: luminos-power restart 2026-06-08 07:07 unlinked ai.sock/sentinel.sock/ram.sock — daemons kept listening on dead inodes, clients got ENOENT for 2 days, silently (BUG-067).
- `process_madvise(MADV_PAGEOUT)` requires CAP_SYS_NICE; SIGSTOP/SIGKILL of other-user processes requires CAP_KILL; setpriority requires CAP_SYS_NICE. The old bounding set stripped all three from root, so the RAM manager's freeze/kill/compress actions were EPERM no-ops (BUG-066) — invisible because madvise() was also a code stub (BUG-065) and syscall errors were unchecked.

### What Was Rejected
- **Per-daemon runtime dirs** (`/run/luminos-ram/` etc.): would fix the wipe but breaks every documented socket path in AGENTS.md §3, internal/config, and all clients. Too invasive.
- **One owning service + others not declaring the dir:** fragile ordering dependency; a restart of the owner still wipes everyone.
- **tmpfiles.d static dir:** works, but RuntimeDirectoryPreserve is the idiomatic single-line fix and keeps unit-file ownership of the path.
- **Full caps for root (no bounding set):** unnecessary attack surface; the three named caps are the exact set the code needs.

### Cross-references
- BUG-065/066/067 → `docs/BUGS.md`
- `AGENTS.md §9` row for the five unit files
- `PENDING_RESTART.md` — restart deliberately deferred (HOPE training in progress)

---

## DECISION 18 — NVreg_DynamicPowerManagement=0x02 vs Chrome NVIDIA P-State Conflict
Date: May 28, 2026
Made by: claude-code
**Status: KNOWN CONFLICT — no resolution yet, tradeoff accepted**

### The Conflict
Two settings set at different times now fight each other:

1. **BUG-047 fix (May 10, 2026):** Added `NVreg_DynamicPowerManagement=0x02` to `/etc/modprobe.d/nvidia.conf`. This enables fine-grained dynamic power management — NVIDIA GPU aggressively enters low P-states when workload is light. Solved NVIDIA drawing 8W constantly.

2. **Chrome NVIDIA path (May 28, 2026):** User can now route Chrome to NVIDIA RTX 4050 via `chrome-luminos` GPU picker. Chrome's ANGLE Vulkan workload (2D rendering, video decode) is not heavy enough to trigger NVIDIA P-state boost. GPU stays at P8/210MHz (6.7% of max 3105MHz). Video playback stutters even though GL_RENDERER confirms NVIDIA and video decode is hardware-accelerated.

### Why We Can't Just Remove DPM=0x02
Removing `DPM=0x02` would revert to `DPM=0x00` (always-on D0), restoring the 8W idle draw that BUG-047 fixed. On battery this is unacceptable. `DPM=0x01` (coarse-grained) would reduce idle power but not as effectively.

### What Was Rejected
- **nvidia-settings GPUPowerMizerMode=1** (prefer max performance): Requires X server running, not persistent across sessions, doesn't set at launch time reliably.
- **Removing DPM=0x02:** Restores 8W idle — unacceptable on battery.
- **nvidia-smi persistence mode:** Controls process persistence, not P-state selection.

### Current Tradeoff
DPM=0x02 stays. Chrome NVIDIA path is best-effort — good for GPU-heavy WebGL/3D sites where the high workload will naturally trigger P-state boost. For video streaming (YouTube), AMD path is better (native Wayland + VAAPI + no P-state issue). The GPU picker dialog makes this choice explicit.

### Cross-references
- BUG-047 (NVIDIA always-on fix) → `docs/BUGS.md`
- BUG-062 (Chrome NVIDIA XWayland fix) → `docs/BUGS.md`
- `/etc/modprobe.d/nvidia.conf` → `AGENTS.md §9`

---

## DECISION 16 — GPU-Per-App Selector Architecture
Date: May 21, 2026
Made by: claude-code
**Status: SUPERSEDED by DECISION 25 (2026-07-04)** — `luminos-nvidia-run` was folded into the single `luminos-gpu-launch` (styled QML picker) and deleted; the two direct AMD/NVIDIA right-click actions were removed. History below kept for context.

### What We Decided
Universal GPU launcher via env var injection, not per-app wrappers. Two scripts:
- `luminos-gpu-launch` — kdialog picker → sets AMD or NVIDIA env vars → execs any command
- `luminos-nvidia-run` — writes `"on"` to PCI power/control sysfs → sets PRIME env vars → execs

Dolphin KDE service menus wire these to right-click for executables (.desktop: `luminos-gpu-select.desktop`) and .desktop app files (`.desktop: luminos-app-gpu.desktop`).

### Why
- PRIME render offload works via env vars for native Wayland apps without system-level changes
- Dolphin service menus cover any installed app without needing per-app wrappers
- Flatpak apps (Chrome) need wrapper scripts — handled separately via `chrome-luminos`
- NVIDIA requires explicit PCI power gate wake (`echo "on" > .../power/control`) before use; bare `env ... exec` doesn't do this — hence a dedicated `luminos-nvidia-run` binary

### What We Rejected
- System-wide NVIDIA default: increases VRAM pressure and heat when idle
- Per-app wrappers for every binary: unmaintainable at scale
- GPU selector widget in panel: adds complexity, breaks panel (proven during session)

---

## DECISION 17 — Chrome Wayland Mode + GPU-Specific GL
Date: May 21, 2026
Made by: claude-code
**Status: FINAL**

### What We Decided
- Global `--ozone-platform=wayland` in chrome-flags.conf (reduces CPU vs XWayland path)
- Removed `--use-gl=angle --use-angle=vulkan` (wrong for AMD, high overhead)
- `chrome-luminos` wrapper: AMD branch uses `--use-gl=egl`; NVIDIA branch uses `--use-gl=desktop`

### Why
ANGLE+Vulkan was a leftover flag optimized for NVIDIA/Windows. On AMD iGPU (primary renderer), EGL via mesa is the correct path. XWayland added unnecessary compositor overhead causing 95% CPU in competing with KWin.

### What We Rejected
- Global `--use-gl=egl` for all cases: breaks NVIDIA path (NVIDIA EGL context is different)
- NIS upscaling system-wide on Wayland PRIME: not possible — compositor owns the framebuffer

---

## Decision 15: Three-Phase AI Maturity
- B: 0.7 threshold gates NPU, rules fallback
- A: Auto-collect rule decisions as training data
- C: HIVE Phase 4 on dGPU after fine-tuning

## DECISION 15 — HATS Architecture: Host-Assisted Tile-Streaming
Date: April 22, 2026 | Updated: April 24, 2026
Made by: gemini-cli | Updated by: claude-code
**Status: FINAL — Implementation complete. Pipeline verified end-to-end.**

### Implementation Status (claude-code | 2026-04-24)
- ✅ triton-xdna 3.6.0 installed in `.triton_venv` (torch 2.11.0+cpu backend)
- ✅ MobileLLM-R1-140M INT8 quantized (64MB weights, 105 tensors, 15 layers)
- ✅ aie.xclbin compiled (85KB — proves Triton→MLIR→Peano→xclbin path)
- ✅ `src/npu/hats_kernel.py` — HATSSentinel class with load_weights + classify
- ✅ `src/npu/quantize_int8.py` — formal quantization entry point
- ✅ `src/sentinel/sentinel_daemon.py` — wired to HATS (replaced SmolLM2 ONNX)
- ✅ `src/classifier/onnx_classifier.py` — wired to HATS (replaced stub)
- ✅ Memory footprint: 312.7MB / 800MB budget (PASS)
- ✅ Inference: 1.6–22ms (CPU/Triton respectively, both well under 100ms)
- ⚠️ Model not fine-tuned for sentinel/classifier tasks — classification outputs
  are heuristic until supervised fine-tuning is applied (future Phase 3+ work)
- ⚠️ Triton-XDNA runs on CPU torch backend (NPU silicon path requires XRT BO
  allocation via amdxdna driver at runtime — needs on-device validation)

### On-Device Validation Result (claude-code | 2026-07-01)
On-silicon testing resolved the open ⚠️ above. Findings (full write-up: `docs/NPU_INVESTIGATION.md`):
- ✅ **bf16 matmul WORKS on npu1** end-to-end (Triton→MLIR→AIR→Peano→aircc→XRT→NPU).
  Vendor `matmul_bf16_m64_n64_k64` compiled fresh xclbins and passed `assert_close`
  vs CPU at M,N,K ∈ {256,1024,4096}. The silicon path is real.
- ❌ **int8 matmul does NOT compile on npu1** (AIE2 / Hawk Point). Our `npu_int8_gemv.py`
  fails in aircc (`operand does not dominate`); the vendor's own int8 example fails in
  aiecc (`Resource allocation pipeline failed`); and int8 transform scripts ship only for
  `aie2p` (npu2 / Strix). **int8 is an NPU2 feature; our silicon is npu1.**
- Consequence: HATS/Sentinel's CPU fallback is CORRECT for this hardware, not a bug.
  Offloading Sentinel to *this* NPU would require a **bf16** path, not int8.
- Working-recipe requirements (all three were previously missing): pinned
  `mlir-air==e279756`; a real `AIR_TRANSFORM_TILING_SCRIPT` (driver's hardcoded fallback
  is stale → `MLIRError: expected ':'`); `.triton_venv/bin` on PATH + `PEANO_INSTALL_DIR` set.

### What We Decided
Formally adopt the **HATS (Host-Assisted Tile-Streaming)** architecture for all Luminos OS AI workloads. This follows the successful verification of the Triton-XDNA compiler stack on April 22, 2026, which proved we can generate valid `.xclbin` binaries for the `npu1` (Phoenix/Hawk Point) architecture.

### The HATS Model
1. **CPU as Host (The "Brain")**: Manages logic, XRT Buffer Object (BO) allocation, DMA scheduling, and synchronization.
2. **NPU as Accelerator (The "Muscles")**: Executes raw tiled math via the AIE2 tile array.
3. **Tile-Streaming**: Large models (like MobileLLM) are decomposed into Triton kernels that stream weights and activations through NPU tiles in a coordinated "Host-Assisted" dance.

### Why
- **Efficiency**: Offloading matmul and activations to the NPU preserves iGPU cycles for the KDE Plasma UI and CPU cycles for system daemons.
- **Privacy**: Local NPU execution ensures zero data leakage while maintaining high performance.
- **Proven Path**: Triton-XDNA removes the "black box" of the VitisAI VOE compiler, allowing us to tune kernels specifically for SmolLM2 and MobileLLM architectures.

### What We Rejected
**Continued reliance on ROCm iGPU (Phase 3 fallback)**
- Pros: Stable and easy.
- Cons: Competes with the desktop compositor (KWin) and increases thermal pressure on the shared CPU/GPU heatpipe. The NPU is dedicated silicon sitting idle; HATS puts it to work.

---

## DECISION 13 — Go/Python Split Architecture For All Daemons
Date: April 2026
Made by: Sam + Claude Code (claude-code)
**Status: FINAL — Governs all daemon development going forward.**

### Decision 13 Update: Model Selection Locked (April 2026)
- **MODEL**: SMOLLM2-135M INT8 ONNX (HuggingFaceTB)
- **SIZE**: ~140MB MODEL, <300MB TOTAL WITH RUNTIME
- **Why this model and no other**:
  * RAM LIMIT ADJUSTED: 300MB SOFT LIMIT, 800MB HARD LIMIT.
  * REVERTED TO 135M TO KEEP BASE FOOTPRINT EXTREMELY SMALL.
  * GGUF format rejected — llama.cpp has no NPU backend
  * Only ONNX works with AMD XDNA VitisAI EP
  * Router and Sentinel SHARE one loaded instance
  * HIVE agents (Phase 4) use separate GGUF on dGPU
- **This decision is final. Do not reopen.**

### What We Decided
Split daemon layer into two tiers based on workload type:
- **Go** handles all system daemon logic (socket servers, routing, rules, power, process monitoring)
- **Python** handles all AI inference (ONNX/VitisAI NPU, llama.cpp, HIVE models)
- **IPC**: Unix sockets between Go and Python tiers (JSON protocol)

### Go handles
- `luminos-ai` — main Unix socket server, request routing, session management
- `luminos-power` — AC/thermal monitoring, CPU governor writer, 10s auto-apply loop
- `luminos-sentinel` — /proc scanner, threat rule engine, notification dispatch, process kill
- `luminos-router` — PE header analysis, rule-based compatibility classification (80% of cases)
- GPU lifecycle manager — VRAM state, gaming mode eviction, idle timeout policy

### Python handles
- NPU inference service — ONNX VitisAI provider for sentinel + router models on AMD XDNA
- AI router edge-case inference — quantized model for the 20% cases rules can't resolve
- llama.cpp / HIVE model serving — llama-cpp-python for Nexus/Bolt/Nova/Eye on NVIDIA dGPU

### Why
Code analysis of the existing Python daemons reveals a clear split:

| Component | ML inference? | Right language |
|-----------|--------------|----------------|
| main.py socket server | No | Go |
| powerbrain.py | No (pure rules) | Go |
| sentinel_daemon.py process scanning | No | Go |
| sentinel npu_classifier call | Yes (ONNX) | Python |
| router_daemon.py socket + cache | No | Go |
| router classify_binary rules | No | Go |
| router AI edge cases | Yes (ONNX) | Python |
| npu_interface.py | Yes (VitisAI) | Python |
| model_manager.py state machine | No | Go |
| llama.cpp actual inference | Yes | Python |

**Go rationale**: Single static binary, no venv, no pip, no Python version fragility.
Fast startup, low memory, goroutine concurrency maps perfectly to socket servers
and background polling loops. Pure-rule logic has no benefit from Python.

**Python rationale**: ONNX Runtime VitisAI provider has no mature Go bindings.
llama-cpp-python is the standard llama.cpp Python interface — no equivalent in Go.
numpy is required for inference tensor operations. Python wins only where ML is mandatory.

### What We Rejected

**All-Go (including inference)**
- Pros: Single language, no subprocess management
- Cons: ONNX Runtime Go bindings are immature; no VitisAI support; no llama.cpp Go binding
  that matches llama-cpp-python quality. Would require building C bridges manually.

**All-Python (keep existing code)**
- Pros: Existing code, no rewrite needed
- Cons: venv fragility (the reason we moved away from Python for UI).
  Python global interpreter lock limits true concurrency in socket servers.
  Known failure mode: Python 3.14 broke chromadb, onnxruntime had version conflicts.
  System daemons should not depend on pip.

---

## DECISION 12 — Complete Permanent Move To KDE Plasma
Date: April 2026
Made by: Sam
**Status: FINAL — No going back. Hyprland and GTK4 completely removed.**

### What We Decided
Retire Hyprland, GTK4, HyprPanel, PyGObject, and all Python UI code permanently.
New stack: KDE Plasma + KWin + Qt/QML + Go.
There are no plans to return to Hyprland under any circumstances.

### Why
6+ weeks were lost fighting gtk4-layer-shell anchor bugs, WAYLAND_DISPLAY propagation,
Python venv fragility, and taskbar input failures. Every problem existed only because we
were building a full desktop environment from scratch on Hyprland with a third-party
layer-shell library. KDE does this natively.

Key comparison:

| Requirement | Hyprland+GTK4 | KDE Plasma |
|-------------|---------------|------------|
| Wayland native | YES | YES |
| Lightweight | 150MB | 300MB |
| Animations/blur | YES | YES — Better |
| Window buttons all apps | BROKEN | WORKS |
| Taskbar | BUGGY | WORKS |
| Minimize button | BROKEN | WORKS |
| App launcher | Manual setup | Built in |
| Time to implement | Months | 1 install |

The product is AI/NPU/compat router — not the shell.
AI cannot do visual fine-tuning. Custom shell needs human designer.
A human designer would use established tools, not custom GTK4.

### Zone Indicators — New Approach
Dropped: colored window borders per zone.
New: Small KDE Plasma widget dot on window corner.
  Blue dot = Zone 2 (Wine/Proton), Orange = Zone 3 (Firecracker),
  Red = Zone 4 (KVM), No dot = native Linux app.

### What Was Removed Entirely
Hyprland, GTK4, gtk4-layer-shell, PyGObject, all Python UI,
AGS/Astal, Waybar, HyprPanel, swww, hyprlock, all systemd user UI services.

### New Stack
Shell: KDE Plasma (Wayland) | Compositor: KWin | Custom widgets: Qt/QML + JavaScript
Login: SDDM | Backend: Go (unchanged) | Styling: KDE themes

### What We Rejected
**Keeping Hyprland as "future advanced mode"**
- Every feature Hyprland has that we need, KDE also has.
- Coming back means rebuilding the shell from scratch again.
- AI cannot do visual fine-tuning — this was proven over 6 weeks.

---

## DECISION 1 — Base OS: Arch Linux (not Ubuntu)
Date: Session 2
Made by: Sam

### What We Decided
Switch from Ubuntu 24.04 to Arch Linux as the base OS.

### Why
Ubuntu was causing real problems that had no clean fix:

1. Casper (Ubuntu's live boot system) hardcodes the username "ubuntu" everywhere.
   Our user is "luminos". This caused 6+ boot errors on every single boot.
   Fixing it meant patching Ubuntu's own tools — fighting the base constantly.

2. Ubuntu packages are 6-12 months old. Our project needs:
   - Latest Hyprland (Wayland compositor)
   - Latest XDNA NPU drivers
   - Latest NVIDIA Wayland support
   - Latest asusctl and supergfxctl
   Ubuntu's versions of all of these were lagging or required unofficial PPAs.

3. Ubuntu forces Snapd. Snap is a package format controlled by Canonical.
   It runs background daemons, uses extra RAM, and we have no control over it.
   On a system where we're trying to manage resources intelligently this is unacceptable.

4. Ubuntu ships Apport, ubuntu-advantage-tools, release upgrader, and other
   Canonical-specific tools we don't want. Removing them without breaking things
   is genuinely difficult.

5. Hyprland, asusctl, supergfxctl — all the tools central to Luminos — are
   maintained by the same community that maintains Arch and AUR. They work
   naturally on Arch. On Ubuntu they require workarounds.

6. SteamOS 3.0 (Valve's gaming OS, the most successful Linux gaming platform)
   is Arch-based. This validates Arch as the right foundation for a
   gaming-capable Linux OS.

### What We Rejected

**Staying on Ubuntu**
- Pros: Faster short term, familiar, large community
- Cons: Every core tool fights Ubuntu. Boot errors would multiply as project grew.
  We'd spend more time fighting the base than building features.

**Debian (Ubuntu's parent)**
- Pros: Cleaner than Ubuntu, no Canonical overhead, no Casper issues
- Cons: Even older packages than Ubuntu. Hyprland/asusctl support is poor.
  Rolling release not available. Same package staleness problem.

**Fedora**
- Pros: Fresh packages, good Wayland support, corporate backing (Red Hat)
- Cons: RPM package format, less Hyprland community support, asusctl not native.

### Conclusion
Arch gives us a clean foundation that matches exactly what we're building.
No inherited mess. Everything we need is in AUR. Rolling release keeps us current.

---

## DECISION 2 — Compatibility Router Runs On CPU (not NPU or GPU)
Date: Session 2
Made by: Sam + Claude

### What We Decided
The AI compatibility router (sub 1GB model that decides Proton vs Firecracker vs KVM)
runs on CPU. The Ryzen AI CPU delivers 16 TFLOPS which is sufficient.

### Why
1. The CPU has 16 TFLOPS available — more than enough for a sub-1GB quantized model.
   Inference on a small Q4 quantized model takes milliseconds at this compute level.

2. The NPU is reserved for Sentinel security which must run always-on and passively.
   If the router also ran on NPU, it would compete with Sentinel for NPU resources.
   Security monitoring cannot be interrupted — it has priority.

3. The GPU is reserved for games, rendering, and heavy AI inference.
   Using it for a 3-second routing decision wastes GPU resources needed elsewhere.

4. CPU inference for a small model is fast enough that the user won't notice.
   Target is under 3 seconds for any routing decision.

### What We Rejected

**Router on NPU**
- Pros: Would free CPU for other tasks
- Cons: Competes with Sentinel. NPU has limited memory. Sentinel cannot share resources.

**Router on GPU**
- Pros: Fastest inference possible
- Cons: GPU needed for games and rendering. Wasteful for a sub-1GB model.
  Also GPU is powered down in battery mode — router must work on battery too.

---

## DECISION 3 — Always Hybrid GPU (no mode switching)
Date: Session 2
Made by: Sam

### What We Decided
supergfxctl is set to Hybrid at install and never changed.
No GPU mode switcher is exposed anywhere in the UI.

### Why
1. The whole point is a laptop that just works. Making users choose between
   iGPU and dGPU modes is exactly the kind of manual tuning we're eliminating.

2. Hybrid mode means:
   - AMD iGPU handles desktop and light tasks (efficient, low heat)
   - NVIDIA dGPU activates for games and heavy workloads (powerful when needed)
   This is the optimal configuration in literally every scenario.

3. iGPU-only mode (Integrated) is bad for gaming and AI tasks.
   dGPU-only mode (NVIDIA) wastes battery and runs hot constantly.
   Hybrid is always the right answer so there's no decision to make.

4. Other OSes expose this choice because they couldn't automate it properly.
   We can and should automate it. The choice shouldn't exist.

### What We Rejected

**Exposing GPU mode in settings**
- Pros: Power users might want control
- Cons: Contradicts core philosophy (no manual tuning). Most users would
  set it wrong and blame Luminos when things run hot or slow.

---

## DECISION 4 — Two Power Modes Only (no profiles)
Date: Session 2
Made by: Sam

### What We Decided
Luminos has exactly two power states: unplugged (battery) and plugged in (performance).
These switch automatically. No power profiles menu exists anywhere.

### Why
1. Gaming laptops with 5 power profiles (Silent, Balanced, Performance, Turbo, etc.)
   are confusing. Most users set it to Performance and leave it forever,
   making the other modes pointless.

2. The real decision is simple: on battery you want to save power,
   plugged in you want full performance. Everything else is noise.

3. Thermal management handles the nuance automatically (fan curves, throttling).
   Users don't need to think about thermals — the OS handles it.

4. Fewer options = harder to misconfigure = better user experience.

### What We Rejected

**Multiple power profiles (Silent, Balanced, Performance, Turbo)**
- Pros: Granular control for power users
- Cons: Contradicts core philosophy. Creates support burden.
  Most users don't understand the difference. Thermal management
  makes most of these profiles redundant anyway.

---

## DECISION 4b — Thermal Target: 45°C Regardless of AC State
Date: 2026-05-15
Made by: Shawn + claude-code

### What We Decided
- Target CPU temperature: ~45°C idle, regardless of whether on AC or battery.
- EPP=power is the default in both states. Gaming detection is the only thing
  that raises EPP (to `performance`) and only on AC.
- Frequency caps (scaling_max_freq) are a last resort — only applied when
  the CPU is genuinely overheating (62°C+ battery, 72°C+ AC). They are never
  applied preemptively.

### Why This Works Without Causing Lag
- EPP=power is a *hint* to the AMD SMU firmware, not a hard clock limit.
  The CPU can still boost to 5.1 GHz when a burst of work arrives —
  EPP=power just tells the SMU "recover to low-power state faster when idle."
- This is exactly how Ubuntu achieves 45°C idle: power-profiles-daemon sets
  EPP=power, the SMU handles everything. No freq cap needed for idle temps.
- Frequency caps would cause lag because they prevent boost even during
  legitimate work bursts. EPP hints do not — the hardware decides.

### The Concern: EPP=power vs balance_performance on AC
- `balance_performance` lets the CPU sit at a higher idle frequency and
  boosts more aggressively. It keeps the CPU warmer even when idle (~55-65°C).
- `power` tells the SMU to clock down between work bursts. The CPU is
  just as fast during bursts, but spends more time at low freq/voltage.
- For HIVE inference, Forex, development: sustained load already keeps the
  CPU busy — EPP makes no difference to throughput in those cases.
- For desktop idle (browsing, reading, typing): EPP=power can drop idle
  temp from 60°C to 42-47°C. This is the target.

### Gaming Mode Exception
When GPU load > 80% for 30s on AC, luminos-power switches to
EPP=performance + asusctl Performance profile. This is the only time
the system intentionally runs hot. Exits back to EPP=power when GPU cools.

---

## DECISION 5 — Compatibility Router Uses Rules First, AI Second
Date: Session 2
Made by: Sam + Claude

### What We Decided
80% of routing decisions are handled by a deterministic rule-based system.
The AI model only handles the 20% edge cases rules can't resolve.
AI can never override a rule — rules are hard guardrails.

### Why
1. Most Windows apps fall into clear categories:
   - Has anticheat → KVM/QEMU (rule, not AI decision)
   - Uses only Wine-supported APIs → Proton/Wine (rule)
   - Needs specific Windows kernel calls → Firecracker (rule)
   These don't need AI — they need reliable rules.

2. AI models can be wrong. A wrong compatibility decision means the app
   doesn't launch or launches in the wrong layer. Rules are deterministic —
   they're always correct for the cases they cover.

3. Running AI inference takes a few seconds. Running rules takes milliseconds.
   For the 80% of apps rules handle, users get a faster experience.

4. The AI model exists for genuinely ambiguous cases where rules can't decide.
   This is the right use of AI — handling uncertainty, not replacing certainty.

### What We Rejected

**Pure AI routing (no rules)**
- Pros: More flexible, handles novel cases
- Cons: Slower, can be wrong, unpredictable. Anticheat detection must be
  100% reliable — AI can't guarantee that. Rules can.

**Pure rule-based (no AI)**
- Pros: Fast, deterministic, always correct
- Cons: Can't handle edge cases or novel apps rules don't cover.
  Would fail on unusual apps or new Windows API patterns.

---

## DECISION 6 — AI Is Infrastructure, Not The Product
Date: Session 1 and 2
Made by: Sam

### What We Decided
AI runs underneath everything in Luminos. It is not marketed, not visible,
not something the user interacts with. It just makes things work better.

### Why
1. The product is a Windows replacement. That's what users want.
   They don't want "an AI OS" — they want something that replaces Windows
   and runs their apps. AI is how we deliver that, not what we sell.

2. AI-as-product means users expect to talk to it, query it, use it as a tool.
   AI-as-infrastructure means users don't think about it at all — things
   just work. The second experience is better.

3. HIVE agents exist and are available — but they're optional.
   The OS works perfectly without ever using them.

### What We Rejected

**AI as the main feature / visible product**
- Pros: Trendy, marketable in current AI hype cycle
- Cons: Distracts from core value (Windows replacement). Ages poorly.
  Users who just want their apps to work don't care about AI features.

---

## DECISION 7 — Firecracker For Middle Layer (not Docker or full VM)
Date: Session 1
Made by: Sam + Claude

### What We Decided
The middle compatibility layer uses Firecracker microVMs, not Docker containers
or a full QEMU/KVM VM.

### Why
1. Docker is not a VM. It shares the host Linux kernel. Windows apps need
   Windows kernel calls — Docker cannot provide that. Wrong tool entirely.

2. Full KVM/QEMU is too heavy for apps that just need some Windows isolation.
   Boot time is too long, resource usage too high for frequent use.

3. Firecracker boots in under 125ms (proven by AWS who built it for Lambda).
   It's a real VM (proper isolation) but lightweight enough to feel instant.
   Perfect middle ground between Wine (no isolation) and full VM (too heavy).

### What We Rejected

**Docker for middle layer**
- Pros: Lightweight, familiar
- Cons: Cannot provide Windows kernel — fundamentally wrong for this use case.

**Full KVM/QEMU for middle layer**
- Pros: Complete Windows environment
- Cons: 30-60 second boot time, high RAM overhead. Too heavy for frequent use.
  Reserved for last resort (Layer 3) only.

---

## DECISION 8 — Four-Way Hardware Split (CPU / iGPU / NPU / dGPU)
Date: Session 3
Made by: Sam

### What We Decided
Each piece of silicon has exactly one job. Nothing shares unless necessary.

```
CPU cores  → OS and apps only. Never AI.
iGPU       → All UI rendering. Frees NVIDIA completely for heavy tasks.
NPU        → All AI inference (Router + Sentinel). No fallbacks.
dGPU       → Games, HIVE, heavy GPU tasks only.
```

### Why

The goal is to keep CPU cores free for actual user work.
Every other OS wastes CPU on AI tasks because they have no NPU strategy.
The Ryzen AI chip has three separate compute engines built in —
using all three independently is the right architecture.

iGPU for UI specifically:
  Hyprland compositor runs fine on AMD RDNA3 integrated graphics.
  No reason to waste NVIDIA power on rendering a dock or settings panel.
  iGPU handles UI at full speed with minimal power draw.
  NVIDIA stays idle until a game or heavy task actually needs it.

NPU for AI specifically:
  XDNA is dedicated silicon — running AI there does NOT slow down CPU.
  This is the entire point of having an NPU.
  Windows barely uses NPUs for anything meaningful.
  Luminos uses it as real infrastructure.

### What We Rejected

**CPU as AI fallback**
  Pros: Simple, always available
  Cons: Defeats the entire purpose of keeping CPU free.
  If Router ran on CPU it would slow down whatever the user is doing.

**GPU as AI fallback**
  Pros: Powerful, fast
  Cons: GPU needed for games. Can't use it for routing when a game is running.
  Also wastes serious power for a task NPU handles fine.

---

## DECISION 9 — NPU Abstraction Interface
Date: Session 3
Made by: Sam + Claude

### What We Decided
All NPU calls go through a single abstraction layer: npu_interface.py
Nothing else in the codebase talks to the NPU directly.

### Why
AMD XDNA driver on Linux is actively being developed.
The API may change. Driver bugs may exist on specific hardware.
If NPU calls are scattered across 20 files, a driver change breaks 20 files.
If they all go through npu_interface.py, a driver change breaks one file.

This is standard engineering practice for hardware that is still maturing.
Test on actual G14 hardware in Phase 5.4 before depending on NPU behavior.

### What We Rejected

**Direct NPU calls everywhere**
  Pros: Slightly less code
  Cons: Unmaintainable. One driver update breaks everything.

---

## DECISION 10 — Custom GTK4 Bar/Dock (Not Waybar)
Date: Session 6
Made by: Sam + Claude
**Status: SUPERSEDED by Decision 11**

### What We Decided
Luminos keeps its custom GTK4 bar and dock (luminos-bar, luminos-dock).
We are not switching to Waybar or any other existing bar.

### Why
1. HyprYou (hyprland-material-you) proves GTK4 + Hyprland works perfectly
   for custom bars and docks. Their bar.py uses the exact same GTK4LayerShell
   API we use. The tech stack is validated.

2. Our bugs were:
   - venv not including system site-packages (GTK4/PyGObject invisible) — FIXED
   - Wrong layer shell anchors (Layer.BOTTOM for dock, manual exclusive_zone) — FIXED
   Both were implementation bugs, not architectural problems.

3. Custom GTK4 gives full Luminos integration:
   - Direct access to the AI daemon via Unix socket
   - NPU/Sentinel awareness (bar can reflect system state)
   - Consistent theming via luminos_theme.py
   - AI-driven workspace and app routing — impossible with Waybar

4. Waybar is JSON-configured and requires shell scripts for any dynamic behavior.
   Our bar can run native Python logic — GPU state, thermal alerts, zone badges.

### What We Rejected

**Waybar**
  Pros: Mature, battle-tested, less code to maintain
  Cons: JSON config only, no native Python integration, cannot talk to AI daemon.
    Loses Luminos-specific features (zone badges, NPU alerts, smart workspace routing).
    HyprYou proves GTK4 is the better path for a fully integrated desktop.

---

## DECISION 11 — Stack Migration: AGS/JS + Go Replaces Python UI
Date: April 2026
Made by: Sam

### What We Decided
DECISION: Stack changed from Python GTK4 to AGS/JS + Go + libadwaita

- **Bar + Dock**: AGS (Astal) + JavaScript + CSS
- **Settings + Login screen**: Go + GTK4 + libadwaita + CSS
- **AI daemon + NPU + Compat Router**: Go
- **Window manager**: Hyprland (locked forever)
- **Drawing engine**: GTK4 (locked forever)
- **Styling**: CSS + libadwaita

### Why
1. Python caused venv issues, slow startup, bad aesthetic out of the box.
   BUG-005 (Python 3.14 incompatibility), BUG-007 (venv system packages missing)
   both traced back to Python packaging fragility.

2. AGS/JS chosen for bar/dock — proven Mac-like results on Hyprland.
   The best macOS-inspired Hyprland desktops all use AGS. Fastest UI dev cycle.

3. Go chosen for all daemons and apps — fast, single binary, no deps.
   No venv, no pip, no Python version issues. Single static binary deployment.

4. libadwaita chosen for instant beautiful GTK4 styling.
   CSS + libadwaita gives GNOME-quality aesthetics with zero custom theming code.

### What We Rejected

**Staying on Python GTK4**
  Pros: Existing code, familiar
  Cons: venv hell, Python 3.14 breaks dependencies, slow startup,
    poor aesthetics without heavy custom CSS. Every session hit a new
    Python packaging bug.

**Rust for daemons**
  Pros: Performance, memory safety
  Cons: Slower development cycle, steeper learning curve. Go is fast enough
    and compiles to single binaries just as easily.

### What This Supersedes
Decision 10 (Custom GTK4 Bar/Dock). The bar and dock are still custom-built
for Luminos — but now in AGS/JavaScript instead of Python GTK4.
Python is deprecated for all UI work. No new Python UI code.

---

## Decision: Windows VM Fallback for .exe Compatibility
- **Date:** 2026-04-25
- **Agent:** gemini-cli
- **Decision:** Implement a KVM/QEMU Windows VM fallback mechanism for failed Wine launches and forced routing for Zone 3/4.
- **Why:** Some applications (Zone 3/4 or failed Zone 2) require full Windows APIs or anti-cheat support that Wine cannot provide. Automating the transfer to a VM via a shared folder (`~/VMShare`) provides a seamless user experience.
- **Alternatives considered:** Firecracker microVMs — kept as an option, but KVM provides better compatibility for the absolute last resort.

---

## DECISION 16 — Model Upgrades April 2026
Date: April 26, 2026
Made by: gemini-cli
**Status: FINAL**

### What We Decided
Upgrade core HIVE models to latest 2026 standards and implement "AI Mode" for concurrent CPU/GPU inference.

- **Nexus:** Llama3.1-8B → **Dolphin3-Llama3.1-8B**
  * Why: Uncensored, follows instructions precisely, no refusals for OS-level tasks.
- **Nova:** DeepSeek-R1-Distill-7B → **R1-0528-Qwen3-8B**
  * Why: Massive reasoning jump, matches O3, surpasses Qwen3-235B-thinking on AIME 2024 benchmarks.
- **Bolt:** Qwen2.5-Coder-7B (Kept)
  * Why: Still the most reliable 7B coding model available.
- **TurboQuant:** Enable turbo4 KV cache compression (type_k=12, type_v=12) on all GPU models.
- **AI Mode:** Allow Nova to run on CPU (n_gpu_layers=0) alongside a GPU model to bypass the "one model at a time" VRAM limit for reasoning tasks.

### Why
The previous stack was based on early 2025 distillations. The April 2026 releases (Dolphin3 and R1-0528) provide significant intelligence gains without increasing VRAM footprint. AI Mode maximizes the Ryzen 7's CPU overhead for background reasoning while keeping the RTX 4050 free for UI-latency sensitive tasks.


---

## DECISION 17 — MemPalace Retired, Replaced with SQLite Notes
Date: April 26, 2026
Made by: gemini-cli
**Status: FINAL**

### What We Decided
Retire the `mempalace` Python-based knowledge mining system and replace it with a lightweight, standalone SQLite-based bash script: `luminos-notes.sh`.

- **Mechanism**: `~/luminos-os/scripts/luminos-notes.sh`
- **Storage**: `~/luminos-os/.notes.db` (SQLite3)
- **Commands**: `add TAG NOTE`, `search TERM`, `list`
- **Dependencies**: Removed Python 3.12, `hnswlib`, `chromadb`, and the `~/.mempalace-venv`.

### Why
1. **Technical Failure**: `hnswlib` (the vector database dependency for MemPalace) causes consistent Segmentation Faults on Python 3.12 under Arch Linux. This rendered the knowledge system unusable for all agents.
2. **Complexity**: MemPalace required a large Python virtual environment and multiple heavy dependencies just to store and search project notes.
3. **Reliability**: A SQLite-based bash script is essentially indestructible, has zero start-up latency, and requires only `sqlite3` which is a core system package.
4. **Maintenance**: Agents can now perform knowledge updates in milliseconds without risk of environment corruption.

### What We Rejected
**Fixing hnswlib/chromadb**
- Pros: Keeps vector search capability.
- Cons: Wasted hours of engineering time on upstream dependency bugs. Not worth the overhead for simple project note tracking.

**Moving to a different Vector DB (Qdrant/Milvus)**
- Pros: Advanced search.
- Cons: Requires background daemons/Docker (BANNED). Too heavy for a local dev environment.

---

## DECISION 18 — Claude Code Router for Multi-Model Orchestration
Date: May 7, 2026
Made by: gemini-cli
**Status: FINAL**

### What We Decided
Implement `claude-code-router` to dynamically route Claude Code tasks to the most appropriate model based on task type.

- **Default:** Claude 3.5 Sonnet (Anthropic)
- **Reasoning/Thinking:** DeepSeek R1 (OpenRouter)
- **Long Context:** Gemini 2.5 Pro (Google)
- **Background:** DeepSeek V4 Chat (OpenRouter)
- **Implementation:** Global installation of `@musistudio/claude-code-router` with a dedicated startup script `/usr/local/bin/luminos-claude-router`.

### Why
1. **Model Specialization:** While Claude 3.5 Sonnet is excellent for general coding, DeepSeek R1 excels at complex reasoning/debugging, and Gemini 2.5 Pro handles massive context windows better.
2. **Cost & Rate Limits:** Offloading simpler background tasks or massive context reads to cheaper or higher-limit models preserves Claude API credits.
3. **Seamless Integration:** The router acts as a local proxy (port 3456), allowing the `claude` CLI to remain the primary interface while gaining multi-model powers.
4. **Resilience:** Provides fallbacks if one provider is down or rate-limited.

### What We Rejected
**Manual Model Switching**
- Pros: Simple, no extra tools.
- Cons: High friction; requires manually changing environment variables for every task type.

---

## DECISION 19 — GPU Policy: NVIDIA reserved for AI/HIVE/Gaming only
Date: May 11, 2026
Made by: gemini-cli
**Status: FINAL**

### What We Decided
Strictly enforce AMD iGPU usage for secondary non-AI workloads like MetaTrader 5 (Wine) and CPU-only inference for background trading bots (Forex bot).

- **MT5 (Wine):** Forced AMD iGPU via `DRI_PRIME=0`, `VK_ICD_FILENAMES`, and `WINEDLLOVERRIDES` (WineD3D).
- **Forex Bot:** Forced CPU inference via `CUDA_VISIBLE_DEVICES=""` to keep NVIDIA in sleep state.
- **NVIDIA:** Explicitly reserved for HIVE model serving, heavy LLM inference, and gaming.

### Why
1. **Power & Heat:** Running MT5 or background bots on NVIDIA prevents the dGPU from entering its lowest power state, increasing heat and reducing battery life unnecessarily.
2. **Thermal Budget:** Keeping the dGPU off during background trading ensures the system remains cool and silent for the user's primary desktop work.
3. **Resource Availability:** Ensures VRAM is fully available for HIVE models without fragmentation from minor apps.

---

## DECISION 20 — User-Centric GPU and Power Control
Date: May 11, 2026
Made by: gemini-cli
**Status: FINAL**

### What We Decided
Implement explicit user control for GPU selection in Wine and real-time power monitoring via a custom KDE widget.

- **Wine GPU Selector:** Instead of hardcoded AMD usage, users are prompted via `kdialog` to choose `igpu` or `nvidia` for every `.exe` launch.
- **Power Monitor Widget:** A dedicated Plasma 6 widget (`org.luminos.powerwidget`) displays current power profile, CPU temp, fan speed, and NVIDIA sleep state.
- **Manual Override:** The widget includes buttons to manually switch `asusctl` power profiles (Quiet, Balanced, Performance).

### Why
1. **Flexibility:** While the default policy favors the iGPU for efficiency, power users may need the NVIDIA dGPU for specific high-performance Windows applications or games.
2. **Visibility:** The system's power state and NVIDIA's "wake" status should be visible at a glance to ensure the user understands why fans are spinning or battery is draining.
3. **Control:** Providing a central location for power profile switching reduces the need to hunt through system settings or use the CLI for common tasks.


---

## DECISION 21 — Games Partition Removed
Date: May 31, 2026
Made by: claude-code
**Status: REVERTED**

### What We Decided
Removed the separate Games partition concept. Games install to wherever the installer chooses (default `~/Downloads` or user-selected path). Root partition (nvme0n1p5, 629 GB) has sufficient free space.

### Why
User preference — simpler is better. No separate partition management needed.

## DECISION 22 — Light/Dark is owned by the KDE color scheme, NOT a custom daemon
Date: June 24, 2026
Made by: claude-code
**Status: ACTIVE**

### What We Decided
The system's single source of truth for light/dark is the **KDE Plasma color scheme**. Everything else follows it automatically; Luminos ships **no daemon, timer, or script** to manage light/dark. GTK theme name is pinned to the **adaptive** `Breeze` (never the fixed-dark `Breeze-Dark`).

### Why
On KDE, kded's `gtkconfig` module already keeps the GTK `gtk-application-prefer-dark-theme` flag AND the xdg-desktop-portal `org.freedesktop.appearance color-scheme` (what Electron/Chromium/Flatpak read) in sync with the active Plasma color scheme. That machinery is built in and already running — re-implementing it is redundant and actively fights kded. An earlier `luminos-theme-switch` Go daemon was built (sun-calc + propagation) and then removed for exactly this reason. The only thing kded does NOT manage is the GTK theme **name**; pinning it to the adaptive `Breeze` lets the flag do its job. See BUG-072.

### The Conflict (both sides, per Rule 11)
- **Fixed-dark `Breeze-Dark`**: looks "more dark by default," but ignores the prefer-dark flag → permanently contradicts KDE's light/dark state → foreign-toolkit fragmentation. REJECTED.
- **Adaptive `Breeze`**: honors the flag, so one KDE color-scheme switch moves the whole desktop (Qt/GTK/Electron/Chromium/Flatpak) together. CHOSEN.

### Consequence for day/night auto-switching
KDE 6.6.x ships the day/night *backend* (`knighttimed` / `org.kde.NightTime`, surfaced as "Day-Night Cycle") but only wires it to Night Light (color temperature), NOT to the color scheme — so there is no native time-based light/dark yet, and Arch's newest (6.6.5) does not add it. Options if automation is wanted later: (a) wait for KDE to ship it natively; (b) a single oneshot hooked onto KDE's existing `org.kde.NightTime` DBus signal calling `plasma-apply-colorscheme` — reuses KDE's clock, not custom sun math. Until then: manual toggle in System Settings → Colors. Deliberately NOT building a daemon (user directive 2026-06-24).

### Durability
This fix survives package updates (user `~/.config` files are never overwritten by pacman) and KDE re-syncs (kded only writes the flag, defaulting the name to `Breeze`). The only regression vectors are (1) a human/agent hand-editing the theme name back to a fixed-dark value, and (2) `scripts/smart_build.sh` /etc/skel shipping `Adwaita-dark` to fresh installs — both documented in BUG-072.

## DECISION 23 — Weight-offload inference requires CROSS-DAEMON coordination (PCIe link + RAM pinning)
Date: June 28, 2026
Made by: claude-code
**Status: PROPOSED — design phase, not yet built**

### Context
To run the ~10.4B HOPE model (20.8 GB bf16 / ~5.2 GB at 4-bit) it cannot fit VRAM (4.6 GB usable), so weights are parked in system RAM and streamed to the dGPU layer-by-layer over PCIe. This makes inference **PCIe-bandwidth-bound**, which exposes two OS-level constraints that no single daemon can solve alone — the daemons must cooperate.

### What We Decided (the requirement)
Every Luminos daemon that touches power or memory must become **offload-aware** and coordinate so the streaming path runs at full speed **without giving up the idle power savings the rest of the time**. Specifically:
- **luminos-power** must detect an active offload-inference session and hold the dGPU + PCIe link at full performance (P0 / Gen4) for its duration, then revert to power-saving when it ends. The mechanism in `scripts/luminos-train-mode` (nvidia-powerd lifecycle + perf pin) is the starting point.
- **luminos-ram** must (a) **exempt** the registered pinned weight region from `MADV_PAGEOUT`/zram so DMA never hits a compressed page, and (b) **reserve/account** the pinned budget (~5 GB of 14 GB) in its headroom math so squeezing the desktop into zram doesn't re-trigger OOM (BUG-070). It should drop swappiness for the session like `luminos-train-ram` does.
- A shared signal (socket/D-Bus) announces "offload session start/stop" so power + ram + sentinel react together, not independently.

### The Conflict (both sides, per Rule 11) — DPM=0x02 vs PCIe bandwidth
- **`NVreg_DynamicPowerManagement=0x02`** (set for BUG-047, saves ~8W idle): aggressively downtrains the dGPU and its PCIe link during light load. **Measured 2026-06-28: link sitting at Gen1 (2.5 GT/s) x8 = ~2 GB/s, one-eighth of the Gen4 x8 ~16 GB/s capability.** This is the same family of conflict as the Chrome P8/210MHz issue.
- **Streaming inference** needs the link held at **Gen4 x8** the whole session, including the micro-gaps between layers, or throughput collapses (~4–5 tok/s → ~0.4 tok/s).
- **Resolution direction:** do NOT globally disable DPM (idle savings matter). Instead, **session-scoped override** — power daemon pins P0/Gen4 only while an offload session is active, reverts after. Cross-ref BUG-047 and BUG-069 (mobile TGP no-op).

### Open question handed back to the model side
Whether the resident/streamed VRAM split fits 4.6 GB depends on the size of the **memory-block (CUDA-kernel) weights** at 4-bit — these stay resident ("the pens") alongside the states, KV, embeddings, output head, double-buffer, and activations. That number is being requested from the model/LLM expert before the split is finalized.

### Why PROPOSED not ACTIVE
No code written yet. This entry records the requirement so the daemon work is scoped as one coordinated change, not three disconnected hacks. See AGENTS.md §14 task 9.

## DECISION 24 — The Conductor: unified per-component power/thermal policy (one brain, independent levers)
Date: June 30, 2026
Made by: claude-code
**Status: PHASES 0-3 LANDED — wired into monitorLoop but gated OFF by default (`LUMINOS_CONDUCTOR=1`)**

### Context (three user pains, grounded in code)
1. **No per-component control.** A single coarse `asusctl profile` moved every knob together — no way to "unlock PCIe but keep the rest normal."
2. **PCIe capped during training.** The machine was **always on the 180W brick, never battery.** `DPM=0x02` (BUG-047) parks the unpinned dGPU in its lowest P-state and downtrains the link to Gen1 **even on AC**; the old daemon never recognized the training job as GPU-busy so it never pinned P0. Not a battery issue.
3. **Open-loop cooling.** Fan control was a static table handed to the EC once, with a 52°C burst panic-button. No real-time temp→PWM feedback; the lazy 45-55°C mid-band stayed hot.

### What We Decided
Build a single policy engine — the **Conductor** — that lives INSIDE `luminos-power` (single-writer discipline for sysfs) and replaces "one profile moves everything" with **independent levers driven from one workload Intent**:
- **`Intent`** (per-workload posture): fan target °C, GPU fan target °C, whether to pin the dGPU to P0. Each lever reads only the fields it owns.
- **`Lever` interface** (fan, pcie): `Apply(Intent)` on change, `Revert()` on shutdown. This is the "per-component control under one rule" mechanism.
- **Fan lever (Phase 2):** closed-loop PID (`fan_control.go`) holding a **workload-aware** fair target — 47°C at light load, a fair higher ceiling (~55-65°C) under heavy load — using the **least** PWM that holds it. Writes `asus_custom_fan_curve` hwmon directly with a baked-in EC failsafe ramp ≥70°C (survives a daemon crash). NOT a single aggressive 47°C setpoint (user rejected maxing fan at 50-55°C as wasteful).
- **PCIe lever (Phase 1):** reuses the proven `applyOffloadPin` P0 mechanism (persistence + `lock-gpu-clocks`, **never** `-pl` — BUG-069), fired by the classifier on training/heavy-GPU **on AC only**, with `current_link_speed` read-back verification. Defers if a real offload session already owns the pin.
- **Classifier (Phase 4 seed):** heuristic `classify()` maps live signals → class (idle/light/media/compute/gaming/training) → Intent. NPU/LLM policy model deferred (Phase 5).

### Why gated OFF by default
Handing fan + PCIe control to brand-new code on a machine probed at 83.5°C carries thermal risk. The whole engine is behind `LUMINOS_CONDUCTOR=1`: when unset, `conductor` stays nil, every guard short-circuits, the legacy asusctl curves + thermal burst run unchanged, and committing/pushing/restarting cannot change live cooling. The user enables it deliberately and watches it.

### The Conflict (both sides, per Rule 11)
- **Keep firmware open-loop curves:** simple, self-protecting, but blind in the 45-55°C band → the heat-soak pain. Kept ONLY as the disabled-Conductor default and the hardware failsafe ramp.
- **Closed-loop PID owning the fan:** smart minimum-effort cooling, but a bug could under-cool a hot machine → mitigated by the baked-in EC failsafe ramp ≥70°C + gated-OFF default + retained 92°C emergency CPU cap path.

### Consequence / single-writer
When the Conductor owns the fan, `applyAggressiveFanCurve` / `applyBurstFanCurve` no-op (`conductorOwnsFan()`), so exactly one code path ever writes the fan hwmon. See `docs/CONDUCTOR_DESIGN.md` for the full design + Phase 0 probe findings. Files: `cmd/luminos-power/conductor.go`, `cmd/luminos-power/fan_control.go`.

### Phase 4 addendum — intent broadcast + cross-daemon coordination (claude-code | 2026-07-01)
The Conductor now broadcasts its Intent so the whole daemon stack reacts under ONE rule instead of each daemon guessing (still entirely behind `LUMINOS_CONDUCTOR=1` — no broadcast happens when disabled):
- **Broadcast:** on every intent *change* the Conductor writes `/run/luminos/intent.json` atomically (temp+rename — generalises the old `/run/luminos/offload.active` signal into a full posture) and pushes an `intent` socket message to `luminos-ram` (`/run/luminos/ram.sock`) and `luminos-ai`. Socket pushes run off-loop so a slow peer can't stall the fan PID; the file is the durable pollable fallback.
- **ram reaction (SOFT, revertible):** `luminos-ram` handles `intent` → for a heavy class (training/gaming/compute/heavy) it lowers `vm.swappiness` to keep the working set resident; light/idle restores the baseline. It deliberately does **NOT** fabricate a pinned-region reservation — that hard number still comes only from a real `offload_start` carrying the actual weight budget (avoids reserving memory that isn't real → BUG-070 risk). **Precedence: offload session > intent**, enforced by the new single-writer `reconcileSwappinessLocked()`, which fixes a latent baseline-corruption bug (an intent lowering swappiness to 10 before `offload_start` could otherwise be captured as the "original" and never restored to 60).
- **status/telemetry:** `luminos-ram` now pushes `report_ram` to `luminos-ai` on state change (offload start/stop, intent change) — `luminos-ai` previously aggregated power/sentinel/router but not ram — and caches the `intent` broadcast, so a single `status` call shows the full picture.
- **Phase 5 corpus:** the Conductor appends one `telemetryRow` per tick to `<logdir>/conductor-telemetry.jsonl` (numeric sensor vector → action: fair targets, resulting fan duties, pin decision), rotating past 64 MiB. This is the training data the deferred NPU/LLM policy model (Phase 5) will learn from — logged from day one so it exists by then.

Files touched: `cmd/luminos-power/conductor.go`, `cmd/luminos-ram/main.go`, `cmd/luminos-ai/main.go`. New cross-daemon message type `intent`; new `report_ram` report type.

### Phase 2 addendum — fan PID retuned after the first live tests (claude-code | 2026-07-04)
The first real enablement of the fan lever exposed the open pain the design warned about — "smart minimum-effort cooling, but a bug could …" — as **inefficiency, not danger**. Two live tests, both time-boxed with an automatic revert to the static curve:
- **2026-07-03 (first enable):** with the untuned gains (`Kp=14`) the PID wrote duty **254/255 at ~53°C idle** — the exact wasteful "max fan at 50-55°C" the user rejected. Enable reverted; binaries left installed but gated OFF.
- **2026-07-04 (retuned):** a cleaner idle test showed the fan *hunting* — surging 2100↔3500 rpm on a FLAT 49.8°C (BUG-079). Root cause was four compounding flaws: Kp too hot, hard-clamp integral windup, no smoothing on spiky per-core Tctl, and a 47°C target below the workload's natural settling temp so the integral kept accumulating a standing error.
- **Fix (BUG-079):** `fan_control.go` retuned — Kp 14→8, a **±2°C deadband** around the target (no correction in-band), **EMA smoothing** of the control temp (TempAlpha=0.30), and **back-calculation anti-windup** (Kbc=0.5) + an in-band **integral leak** (0.90/tick) replacing the hard clamp. Post-fix idle test held a STEADY ~2100-2200 rpm (CPU) / ~2400-2500 rpm (GPU), no surging.
- **Status:** idle-validated only; the Conductor remains **gated OFF by default**. A load test (compute/gaming, where the fair target rises to ~55-60°C → *less* fan for the same heat) is still recommended before considering default-on. This confirms the workload-aware design intent: a correctly-classified heavy job raises the target, so it should never be the case that heavy load = max fan unless the temp genuinely demands it.

## DECISION 25 — dGPU access gate: default-deny the discrete GPU, picker is the only door
Date: July 3, 2026
Made by: claude-code
**Status: INSTALLED — authoritative driver-param layer takes full effect on next REBOOT**

### Context (user pain, grounded in reality)
The user believed a "GPU permission" system already existed (they remembered the `luminos-gpu-launch` kdialog picker) and was confused why `claude-desktop` and `antigravity` freely hold the dGPU. Investigation: **no access control existed.** The NVIDIA driver creates `/dev/nvidia*` **world-open (`0666 root:root`)**, so any process opens the discrete GPU with zero check. `claude-desktop` (`--render-node-override=/dev/dri/renderD129` = AMD iGPU) and `antigravity` (`__EGL...=50_mesa.json` = iGPU) both **render on the iGPU** and only *probe* the dGPU at startup — but that probe keeps the RTX 4050 awake. The existing `luminos-gpu-launch` picker was purely **opt-in**; nothing forced apps through it.

### What We Decided
Make the dGPU **default-deny** so the picker becomes the ONLY door. Because everything runs as user `shawn`, per-user file perms can't tell apps apart — so the gate is per-process via a setgid group + the authoritative driver param:
- **`dgpu` system group** — `shawn` is deliberately NOT a member ⇒ normal apps denied by default.
- **Authoritative layer (the one that actually holds): `/etc/modprobe.d/luminos-dgpu-gate.conf`** → `options nvidia NVreg_DeviceFileUID=0 NVreg_DeviceFileGID=<dgpu> NVreg_DeviceFileMode=0660`. This is REQUIRED because **`nvidia-modprobe` (setuid-root) recreates `/dev/nvidia*` at `0666` on every open/wake**, defeating any udev-only change. The driver params tell nvidia-modprobe what owner/group/mode to stamp. Applies when the module loads — and nvidia loads **late from the real root** here (autodetect prunes it from initramfs since the display is AMD), so the conf is read at boot. **⇒ full effect after reboot.**
- **udev rule `70-luminos-dgpu-access.rules`** (`root:dgpu 0660`) — belt-and-suspenders for node creation between boots.
- **`dgpu-exec`** — a tiny setgid-`dgpu` helper (`2755 root:dgpu`). Apps launched through it inherit `egid=dgpu` and can open the nodes; everything else falls back to the iGPU. `luminos-gpu-launch` (the single picker) routes the NVIDIA choice through it.

### Update (claude-code | 2026-07-04) — styled picker + single launch path
The kdialog picker was replaced by a styled QML dialog (`scripts/dgpu-gate/luminos-gpu-picker.qml`, installed to `/usr/local/share/luminos/`): one Chrome-style dialog listing AMD (default/recommended, battery-friendly) vs NVIDIA (performance), a "remember for this app" tick (persisted to `~/.config/luminos/gpu-choices.conf`), battery-aware warning copy. **Consolidation:** the redundant `luminos-nvidia-run` helper was **deleted** — its only unique job (waking the PCI power gate before launch) is now inline in `luminos-gpu-launch`'s NVIDIA branch, so there is exactly ONE launch path. The KDE service menu `luminos-gpu-select.desktop` collapsed to a single "Run on GPU..." action that opens the picker (old direct AMD/NVIDIA right-click actions removed).

### Why this is safe (user's #1 rule: "don't crash yourself")
Changing device perms does **not** revoke already-open FDs, so installing live did not touch the running `claude`/`antigravity` session. Both already render on the iGPU, so when they relaunch denied they simply stop probing the dGPU — no render path is removed. Root services (`nvidia-powerd`, `luminos-power`/Conductor) bypass DAC. Display is AMD-driven, so gating nvidia nodes does not affect the desktop. Forex bot is off until Monday and must be launched via `dgpu-exec`/picker to keep GPU access.

### The Conflict (both sides, per Rule 11)
- **Leave it world-open (0666):** zero risk of denying a legit app, but any unknown app silently grabs the dGPU and holds it awake (the pain). Rejected.
- **Hard default-deny:** strong, but a mis-scoped allowlist could deny a legit consumer. Mitigated by: the picker/`dgpu-exec` allow path, root-service bypass, iGPU fallback, and an instant kill switch (`sudo chmod 0666 /dev/nvidia*`).

### v2 (not built) — bypass-proof gate
`CONFIG_BPF_LSM=y` and `bpf` is in the active LSM list, so a true **BPF-LSM** gate that allow-lists apps by binary at `open()` (defeats even a hostile process calling `dgpu-exec` itself) is possible. v1 covers the accidental-grab threat model; v2 covers the adversarial one.

Files: `scripts/dgpu-gate/` (dgpu-exec.c, install-dgpu-gate.sh, luminos-gpu-picker.qml, README.md), `scripts/luminos-gpu-launch` (the single launcher), `config/modprobe.d/luminos-dgpu-gate.conf`, `config/udev/70-luminos-dgpu-access.rules`. KILL SWITCH: `sudo chmod 0666 /dev/nvidia*` (temp) or remove the modprobe+udev files and `mkinitcpio -P` (permanent).

---

## DECISION 26 — Level-0 of the safe-update ladder: pin kernel + NVIDIA branch in pacman.conf
Date: July 21, 2026
Made by: claude-code
**Status: ACTIVE (live in /etc/pacman.conf)**

### Context
System was 2.5 months stale (last full upgrade 2026-05-10; 645 packages behind). User
wanted to install Steam (which needs matching 32-bit NVIDIA libs) and asked, more
broadly, how to "act like an OS developer" and keep Luminos current **without breaking**.
Investigation of a full `pacman -Syu` showed it is NOT a small update: it drags in
`linux` 7.0.5→7.1.4, **`nvidia` 595.71.05 → 610.43.03 (a full driver-branch jump)**,
`plasma-workspace` 6.6.4→6.7.3, `systemd` 260→261. Two specific dangers on THIS tuned
machine: (a) the 595→610 branch jump can silently undo the true-0W dGPU RTD3 gating +
DPM=0x02 power tuning; (b) Plasma 6.6→6.7 breaks the hand-built KCM `.so` plugins
(kcm_luminos_hive/keyboard/lid_light) until recompiled. Root FS is **ext4**, so Btrfs
instant-snapshot rollback is not available without a filesystem migration.

### The framing (why "never breaks" is the wrong goal)
A rolling release + a customized machine cannot guarantee break-free upgrades. The real
engineering goal is upgrades that are **reversible + verifiable + pinnable**. The
safe-update ladder: **L0 pin fragile pkgs** → L1 restore points (timeshift on ext4; Btrfs
later) → L2 verification harness (KCMs load? 5 Go daemons bind sockets? dGPU 0W? HIVE up?
fans alive?) → L3 auto-rebuild customs (cmake+go) as post-upgrade hook → L4 one
`luminos-update` command tying it together → L5 (aspirational) immutable A/B image
(SteamOS-style, Arch-based) or NixOS declarative.

### What We Decided (L0)
`/etc/pacman.conf`: `IgnorePkg = linux linux-headers nvidia-utils nvidia-open-dkms
opencl-nvidia lib32-nvidia-utils lib32-opencl-nvidia`. Now `pacman -Syu` keeps ~640
packages current but never moves the kernel or the version-locked NVIDIA driver set as a
side effect. Kernel/NVIDIA are upgraded ONLY deliberately (unpin → upgrade → DKMS rebuild
→ verify true-0W gating + KCMs → re-pin). Backup: `/etc/pacman.conf.bak-20260721`.
(lib32-nvidia-utils/lib32-opencl-nvidia pinned pre-emptively so the Steam install pulls
them at 595.71.05 to match the installed 64-bit driver.)

### The Conflict (both sides, per Rule 11)
- **Pin (chosen):** protects the tuned power stack + custom KCMs; lets the user stay
  current elsewhere. Cost: creates a permanent partial-upgrade state — held pkgs can
  eventually diverge from the rest (e.g. a future glibc/mesa bump wanting a newer driver).
  Mitigation: revisit pins at each deliberate kernel/NVIDIA window; keep the window short.
- **Don't pin (rejected):** always fully coherent, but every routine `-Syu` risks a
  silent branch jump that undoes power tuning + breaks KCMs with no safety net (ext4, no
  snapshots yet). Rejected until at least L1 restore points exist.

Files: `/etc/pacman.conf` (+ .bak-20260721). Cross-ref AGENTS.md §9. Next rungs (L1–L4)
not yet built — tracked as an open initiative.

---

## DECISION 27 — Local caching DNS resolver (systemd-resolved) for Chrome new-page-load speed
Date: July 22, 2026
Made by: claude-code
**Status: APPLIED (live)**

### The Decision
Enable `systemd-resolved` as a local caching DNS resolver and route NetworkManager's DNS
through it. Concretely: drop-in `/etc/NetworkManager/conf.d/dns-systemd-resolved.conf`
(`[main] dns=systemd-resolved`), `systemctl enable --now systemd-resolved`, and symlink
`/etc/resolv.conf` → `/run/systemd/resolve/stub-resolv.conf` (stub `127.0.0.53`). Upstream
DNS is unchanged (router `192.168.2.1` + `207.164.234.129`, pushed to resolved by NM).

### Why
User reported brand-new pages/tabs (type "youtube" → Enter) render slower than on Windows —
distinct from MemorySaver-discarded tabs. Measured: no local DNS cache existed; NetworkManager
wrote `resolv.conf` straight to the router, so every new domain cost 30–50 ms (youtube.com 49,
i.ytimg.com 50, github.com 33), and a page like YouTube pulls 10+ domains. Repeat lookups were
~7 ms but cached at the ROUTER only — non-persistent. Windows caches DNS locally by default;
this was the gap. After the change: fresh domain first hit ~50 ms, repeats <1 ms and persistent
(verified via `resolvectl statistics` cache hits).

This is "Chrome fix #3" in a small perceived-slowness punch-list. Fix #1 (removed the
`--renderer-process-limit=8` + `--process-per-site` renderer caps) is also applied. Fix #2
(remove `MemorySaver`) was tried then REVERTED at user request — MemorySaver stays on; it is a
built-in Chromium feature, only toggleable, not externally rewritable.

### What we rejected
- **NetworkManager `dns=dnsmasq` caching mode:** also gives a local cache, but requires the
  `dnsmasq` package. `systemd-resolved` ships with systemd (already installed) and needs no new
  package — preferred for a zero-install, native fix.
- **Just cleaning nsswitch** (dropping the dead `resolve`/`mymachines` entries) without a
  resolver: removes a little dead-stub walk overhead but provides NO caching — misses the actual
  win. Rejected.
- **Do nothing:** rejected — the DNS cost is real, measured, and Windows-parity is achievable
  cheaply and reversibly.

### Revert
`rm /etc/NetworkManager/conf.d/dns-systemd-resolved.conf` → `systemctl disable --now
systemd-resolved` → restore `/etc/resolv.conf` from `/etc/resolv.conf.bak-20260722` (replace the
symlink with the plain file) → `systemctl restart NetworkManager`.

Files: `/etc/NetworkManager/conf.d/dns-systemd-resolved.conf` (new), `/etc/resolv.conf`
(→ stub symlink, backup `.bak-20260722`). Cross-ref AGENTS.md §9, docs/LUMINOS_HANDBOOK.md §11.5.

---

## DECISION 28 — SDDM login screen matches the KDE lock screen (Breeze)
Date: July 22, 2026
Made by: claude-code
**Status: APPLIED (visible at next login/reboot)**

### The Decision
Switch the SDDM login theme from `Sugar-Candy` to **Breeze**, and set the Breeze SDDM theme's
background to the same wallpaper the KDE lock screen uses
(`/usr/share/sddm/themes/Sugar-Candy/Backgrounds/Mountain.jpg`, via
`/usr/share/sddm/themes/breeze/theme.conf.user`). All `/etc/sddm.conf.d/*.conf` consolidated to
`Current=breeze` (`hidpi.conf`, `luminos.conf`, and the KCM-managed `kde_settings.conf`).

### Why
User wanted the login screen and lock screen to look the same ("use the KDE theme everywhere").
They previously looked different: SDDM = Sugar-Candy frosted style, lock screen = Breeze. The two
use different theming systems — SDDM loads "SDDM themes" while the KDE screen-locker loads a Plasma
"Look & Feel" package and CANNOT load an SDDM theme. So the only clean way to match them is to move
SDDM onto Breeze (the direction the lock screen already uses), then give SDDM the lock screen's
wallpaper. Result: both show Breeze widgets + the Mountain wallpaper.

### What we rejected
- **Make the lock screen look like Sugar-Candy:** would require hand-building a custom Plasma
  lock-screen QML theme imitating Sugar-Candy — high effort, fragile across Plasma updates. Rejected.
- **Leave the two mismatched:** rejected — user explicitly wanted consistency.

### Revert
Set `Current=Sugar-Candy` in `/etc/sddm.conf.d/luminos.conf` (or restore
`/etc/sddm-luminos.conf.bak-20260722`); optionally clear the `background=` line in
`/usr/share/sddm/themes/breeze/theme.conf.user`.

Files: `/etc/sddm.conf.d/{luminos,hidpi,kde_settings}.conf`,
`/usr/share/sddm/themes/breeze/theme.conf.user`, backup `/etc/sddm-luminos.conf.bak-20260722`.
Cross-ref AGENTS.md §9, docs/LUMINOS_HANDBOOK.md. Relates to open task #8 (custom Luminos SDDM
theme) — for now standardized on Breeze to match the lock screen rather than a bespoke theme.

## DECISION 29 — Auto-sync SDDM + lock screen to the desktop wallpaper (theme-sync watcher)
Date: July 22, 2026
Made by: claude-code
**Status: APPLIED + LIVE (path watcher enabled)**

### The Decision
Make the DECISION 28 matching automatic instead of manual. A script `luminos-theme-sync`
(`/usr/local/bin/`, source `scripts/luminos-theme-sync`) reads the CURRENT desktop wallpaper
(fallback chain: `plasma-org.kde.plasma.desktop-appletsrc` → `kscreenlockerrc` → SDDM current)
and pushes it into both the lock screen (`kscreenlockerrc`, written as the user via
`kwriteconfig6`) and the SDDM Breeze theme (`/usr/share/sddm/themes/breeze/theme.conf.user`).
It is debounced via `/var/lib/luminos/theme-sync.wallpaper` (no-op if unchanged). A systemd
**system** path unit `luminos-theme-sync.path` watches the two config files and triggers the
oneshot `luminos-theme-sync.service` on change — so changing the desktop wallpaper re-matches
login + lock automatically, no manual step.

### Why
User is about to reskin the desktop (Ubuntu/Yaru look, DECISION 30) and did not want to hand-match
SDDM every time the theme changes ("write code to make it automatically"). SDDM/lock are separate
theming systems from the Plasma desktop (see DECISION 28), so the wallpaper has to be copied across;
the watcher removes the manual copy.

### Design notes / what we rejected
- **Root path unit watching the user's home:** chosen — root can read `/home/shawn/.config` and
  write both `/etc` (SDDM) and (as the user) `kscreenlockerrc`, so ONE privilege model, no sudoers
  or polkit rule. User path `/home/shawn` hardcoded (single-user box, matches other configs).
- **User-level watcher + sudoers NOPASSWD helper for the /etc write:** rejected for v1 — adds a
  sudoers security file for little gain.
- Currently syncs **wallpaper only** (the visible mismatch). Color-scheme sync into SDDM is a
  possible future add.

### Revert
`sudo systemctl disable --now luminos-theme-sync.path`; optionally
`sudo rm /etc/systemd/system/luminos-theme-sync.{path,service} /usr/local/bin/luminos-theme-sync`
and `sudo systemctl daemon-reload`. The last-synced wallpaper stays in the SDDM/lock config
(harmless); restore DECISION 28 state if desired.

Files: `scripts/luminos-theme-sync`, `systemd/luminos-theme-sync.{service,path}`,
`/usr/local/bin/luminos-theme-sync`, `/etc/systemd/system/luminos-theme-sync.{service,path}`,
state `/var/lib/luminos/theme-sync.wallpaper`. Cross-ref DECISION 28, DECISION 30.

## DECISION 30 — Ubuntu (Yaru) look on KDE Plasma, no GNOME
Date: July 22, 2026
Made by: claude-code
**Status: APPLIED (live in session; fonts/full repaint finalize on next re-login)**

### The Decision
Give the Plasma desktop an Ubuntu look by layering the **Yaru** theme onto KDE — WITHOUT switching
to GNOME. Installed (AUR via yay + official repo): `yaru-icon-theme` (icons + Yaru cursors),
`yaru-gtk-theme` (GTK apps), `yaru-sound-theme`, `ttf-ubuntu-font-family`. Applied via
`scripts/luminos-ubuntu-look` (→ /usr/local/bin): icons=Yaru, cursor=Yaru, UI font=Ubuntu 10,
mono=Ubuntu Mono, GTK apps→Yaru (gtk-3.0/4.0 settings.ini + gsettings), and a custom Ubuntu-orange
Plasma color scheme `share/color-schemes/Yaru.colors` (accent #E95420) installed to
`~/.local/share/color-schemes/` + `/usr/local/share/color-schemes/`. The script finishes by calling
`luminos-theme-sync` so login/lock pick up the wallpaper.

### Why
User wanted the desktop to look like Ubuntu but explicitly did NOT want to run GNOME. Yaru is
Ubuntu's own theme; on KDE the convincing signals are icons + Ubuntu font + orange accent, all of
which are Qt/Plasma-side and don't require GNOME.

### Notes / limits / rejected
- **Widget style stays Breeze** (Ubuntu-orange accent via the color scheme). No maintained "KvYaru"
  Kvantum theme was found; Breeze + orange is the low-risk choice. Adwaita-Qt was rejected (that's
  GNOME-generic, not Ubuntu-orange).
- **Layout (top bar + left vertical dock)** — NOT done; the classic Ubuntu layout is a separate,
  more invasive step (rearranges panels). Offered to the user as a follow-up.
- Wallpaper left as-is (Ubuntu default wallpaper not installed); if the user sets one, DECISION 29's
  watcher propagates it to login/lock automatically.
- Live-apply from a non-session shell crashes the `plasma-apply-*` tools (no Wayland attach); applied
  live by sourcing the running plasmashell's env (WAYLAND_DISPLAY/XDG_RUNTIME_DIR/DBUS). Config-file
  writes are the durable path and survive re-login regardless.

### Revert
`luminos-ubuntu-look --revert` (restores icons→Papirus, colors→BreezeLight, cursor→breeze_cursors;
re-login to finish). Optionally `yay -Rns yaru-icon-theme yaru-gtk-theme yaru-sound-theme
ttf-ubuntu-font-family`. Previous icon theme was **Papirus**.

Files: `scripts/luminos-ubuntu-look`, `share/color-schemes/Yaru.colors`,
`/usr/local/bin/luminos-ubuntu-look`, `~/.config/{kdeglobals,kcminputrc,gtk-3.0/settings.ini,gtk-4.0/settings.ini}`.
Cross-ref DECISION 29 (auto-sync), AGENTS.md §9.

### AMENDMENT — 2026-07-26: KDE's automatic Global Theme switching is OFF, and it is a hard conflict
<!-- [CHANGE: claude-code | 2026-07-26] -->
This decision was incomplete: it layered Yaru on top of Plasma but never disabled the thing that
undoes it. **`kdeglobals [KDE] AutomaticLookAndFeel` and `AutomaticLookAndFeelOnIdle` are now both
`false`** (BUG-088). The kded module `lookandfeelautoswitcher` re-applies a whole Look-and-Feel
package — colours, icons, cursor, widget style, Plasma style, window decoration — on a time-of-day
schedule **and after `AutomaticLookAndFeelIdleInterval` seconds of idle, which defaults to 5**. Any
lock, resume or short idle therefore reverted the desktop to Breeze Dark within seconds.

**These two features are mutually exclusive by design and cannot be reconciled.** Automatic
day/night switching works by swapping between two *Look-and-Feel packages*, and there is no Yaru
Look-and-Feel package to swap to (per the note above, there is not even a Yaru widget style). The
tradeoff, stated plainly per Rule 11: **choosing the Ubuntu look means giving up KDE's automatic
light/dark switching.** If the user ever wants day/night switching back, the Ubuntu look has to go
with it — turning the setting back on in System Settings → Colors & Themes will silently undo
DECISION 30 again, and the symptom will look like "the theme randomly resets", not like a setting.

Two further traps recorded so they are not rediscovered:
- **`AutomaticLookAndFeelOnIdle` defaults to `true`.** Writing only `AutomaticLookAndFeel=false`
  is not enough; the idle path stays armed. Write both.
- **`plasma-apply-colorscheme` refuses to act when the name key already matches** (`"…is already
  set as the theme for the current Plasma session"`, exit 0). So the scheme *name* in
  `[General] ColorScheme` and the actual `[Colors:*]` payload can disagree indefinitely. Anything
  that verifies this look must check a real colour value — `[Colors:Button] DecorationFocus`
  should be `233,84,32` (#E95420) — never the name.

## DECISION 31 — Keep web live-wallpapers animating while the desktop is covered
Date: July 23, 2026
Made by: claude-code
**Status: APPLIED (live this session; permanent via session env script, finalizes each login)**

### The Decision
Set `QTWEBENGINE_CHROMIUM_FLAGS="--disable-backgrounding-occluded-windows --disable-renderer-backgrounding"`
for the whole Plasma session via `~/.config/plasma-workspace/env/luminos-wallpaper-nothrottle.sh`
(KDE sources every `*.sh` there at session start). This stops KWin/QtWebEngine from throttling the
`org.luminos.livewallpaper` WebEngineView to 0 fps when a window fully covers the desktop.

### Why
User reported web wallpapers (particles, etc.) "freeze" and unchecking the plugin's
**"Freeze when a window covers the desktop"** box did nothing. Root cause (BUG-081): the freeze
happens *below* the plugin — the compositor stops drawing the occluded desktop surface and Chromium
background-throttles the WebEngine — so the plugin's `PauseWhenObscured=false` was overridden.
Measured: renderer 0 jiffies/3s while covered → 17–24 jiffies/3s (~30fps) after the flags.

### Conflict / interaction (two settings that touch the same behaviour)
The plugin checkbox and this flag now compose deliberately:
- Checkbox **CHECKED** (default `PauseWhenObscured=true`) → plugin explicitly sets WebEngine
  `lifecycleState=Frozen` when covered → power saving preserved.
- Checkbox **UNCHECKED** → the flags let the wallpaper keep animating while covered (small constant
  GPU/CPU cost — this is the user's explicit choice; they almost always have a window up and want to
  glance at motion). Trade-off documented per AGENTS §5 rule 11.

### Notes / limits
- The **particles** sample is cursor-reactive only → still looks static when covered (no cursor
  reaches the desktop). For visible autonomous motion use the **aurora** sample or a **video**
  wallpaper. Desktop was switched to aurora to demonstrate the fix.
- Flag is Qt-WebEngine-specific (`QTWEBENGINE_CHROMIUM_FLAGS`); Chrome/Chromium proper ignore it.
  4K Video Downloader Plus (bundles QtWebEngine) will inherit it — harmless.

### Revert
`rm ~/.config/plasma-workspace/env/luminos-wallpaper-nothrottle.sh` +
`systemctl --user unset-environment QTWEBENGINE_CHROMIUM_FLAGS` + restart plasmashell (or re-login).

Files: `~/.config/plasma-workspace/env/luminos-wallpaper-nothrottle.sh`. Cross-ref BUG-081, AGENTS.md §9.

## DECISION 32 — Wallpaper visibility is a graded policy, not a boolean (amends DECISION 31)
Date: July 24, 2026
Made by: claude-code
**Status: APPLIED (live; measured before/after)**

### The Decision
The live wallpaper's obscured guard becomes a three-way `ObscurePolicy` int instead of the
`PauseWhenObscured` bool:
- `0` — never freeze (old `false`; still useful for a glanceable web toy)
- `1` — freeze only while a **fullscreen** window is up
- `2` — freeze whenever the desktop is hidden at all, fullscreen **or** maximized — **the default**

Per-window cover is now graded (`fullscreen=2`, `maximized=1`, `minimized/normal=0`) and the maximum
across windows is debounced 400 ms before it is acted on.

### Why
DECISION 31 turned the guard OFF so *web* wallpapers would keep animating while covered. That bool
also governed the *video* path, so a 3840×2160 H.264 wallpaper decoded + composited 24/7 behind a
maximized Chrome — a constant 24% of a core, 810 MB RSS and 16–18% iGPU busy on the **same iGPU KWin
and Chrome use**. The user experienced it as the browser and desktop "not responding". A boolean
cannot express "keep the web toy alive but stop burning the iGPU on frames nobody sees" — the policy
has to be graded. See BUG-083 for the measurements.

### Conflict / interaction (per Rule 11) — with DECISION 31
Both settings touch the same behaviour and are now deliberately layered:
- DECISION 31's session-wide `QTWEBENGINE_CHROMIUM_FLAGS` anti-throttle is **kept**. It removes the
  *involuntary* Chromium/KWin throttle, which is what makes `ObscurePolicy=0` actually work.
- The plugin's `ObscurePolicy` is now the **authority** — it decides voluntarily whether to render.
- Trade-off: default `2` means a maximized window stops the wallpaper. Anyone who wants motion behind
  a maximized window sets `1` (fullscreen only) or `0` (never freeze) and pays ~12% of a core.

### Companion change — right-size the source, don't just gate it
Gating fixes the hidden case; it does nothing while the desktop is visible. The wallpaper video was
also transcoded 3840×2160 → **2880×1620** (panel is 2880×1800) H.264 CRF 20, audio stripped:
**−47% CPU, −27% RSS** while playing, with the 4K original kept. Rule of thumb recorded here: a
wallpaper should never be encoded above the panel's resolution — the extra pixels are decoded, then
thrown away by the scaler.

### Known gap (deliberately not fixed here)
A locked session / DPMS-off screen does not register as "covered" — the lock greeter is not a window
in `TasksModel`. Wants a lock/idle signal; tracked in BUG-083.

### Revert
Set `ObscurePolicy=0` in
`~/.config/plasma-org.kde.plasma.desktop-appletsrc [Containments][30][Wallpaper][org.luminos.livewallpaper][General]`
and point `Video=` back at the `4K HD (h264).mp4` file. Config backups:
`~/.config/plasma-org.kde.plasma.desktop-appletsrc.bak-wallpaper-20260724`,
`~/.config/kscreenlockerrc.bak-wallpaper-20260724`.

Files: `src/wallpapers/org.luminos.livewallpaper/contents/{config/main.xml,ui/main.qml,ui/config.qml}`.
Cross-ref BUG-083, BUG-081, DECISION 31.

---

## DECISION 33 — Agent tooling is pinned and self-verifying: one venv per tool, one registration, one loud check
Date: July 25, 2026
Made by: claude-code
**Status: APPLIED (live; every failure mode negative-tested)**

### The Problem
The user's report was: *"they work, we add some new things, it breaks its environment and it stops
working."* Investigation (BUG-085) found the two MCP tools AGENTS.md makes **mandatory before every
task** — `code-review-graph` and MemPalace — were degrading continuously with **no error surfaced
anywhere**. Both servers still answered a handshake, which is why this went unnoticed for months.

The common cause was not a bug in either tool. It was that **every dependency they had was a moving
target, and every failure was silent**:

| Moving target | What it broke |
|---|---|
| Arch's `/usr/bin/python3` (rolling) | `code-review-graph`'s shebang; its packages sat in `~/.local/lib/python3.14/` and would vanish on the next minor bump |
| the `~/mempalace` git checkout | an **editable** install meant `git pull` silently changed the live server |
| `~/.local/lib/python3.14/site-packages` | a shared **301-package** user-site; every unrelated `pip install --user` mutated what these tools resolved against |
| `PATH` that only exists in interactive zsh | both hooks resolved to `command not found`, silently, on every single invocation |
| the same server name in two config files | you got whichever won scope precedence, not what you edited |

### The Decision
Three rules, applied to all agent tooling:

1. **One tool, one venv, pyenv 3.12.13.** Never `pip install --user`, never Arch's system python,
   never a shared site-packages. This matches the existing `luminos-brain safe` house rule
   ("ML/AI always use pyenv 3.12.13") — the outages were precisely what happened when tooling
   drifted off it.
2. **Never editable.** Install pinned copies (`==<version>`). If a source checkout must be hackable,
   register it under a **different server name** so it cannot silently replace the stable one.
3. **One registration: `.mcp.json` in the repo.** Never `~/.claude.json` — its local scope silently
   shadows `.mcp.json`.

And the part that makes it durable:

4. **The invariants are enforced by a check that fails loudly**, `luminos-verify --mcp`
   (section [5]), wired to the SessionStart hook. It does a **real MCP `initialize` handshake** per
   server and hard-fails on: duplicate registration · interpreter under `/usr/bin/python*` ·
   interpreter outside `~/.pyenv` · any editable install · missing binary · server that starts but
   returns no valid result. Every one of those was verified by deliberately reintroducing the fault.

### Tradeoffs
- Pinned versions mean upgrades are now **deliberate**, not incidental. That is the point — but it
  does mean nobody gets fixes for free. Bump the pin explicitly, then re-run `luminos-verify --mcp`.
- A per-tool venv costs disk (duplicated deps) in exchange for blast-radius isolation. Worth it:
  the 301-package shared user-site is exactly how one `pip install` broke unrelated tools.
- The PostToolUse hook now genuinely runs on every `Edit|Write|Bash` where it previously no-opped.
  Measured cost is **1.1 s** per invocation, well inside the 30 s timeout.

### Conflicts documented (Rule 11)
- **vs. Rule 9 (No Ollama):** `code-review-graph`'s `all` extra depends on `ollama`. Resolved by
  installing with **no extras**. Anyone bumping the pin must not use `[all]`.
- **vs. Rule 5 (`luminos-brain safe`):** brain returned `NO: ML/AI always use pyenv 3.12.13` for a
  plan that *was* pyenv 3.12.13 — a keyword match, not a real objection. Proceeded under an
  explicit `--reason` override with user authorization. This is a live instance of open task 0b
  (brain's NO reasons are unreviewable) and is the second time it has blocked correct work.

### Verification
`luminos-verify --mcp` → 8 checks PASS. Functionally confirmed with real `tools/call`, not just a
handshake: MemPalace 29 tools, `mempalace_search("dGPU power gating RTD3")` → 15 hits from the
2.0 GB store; code-review-graph 24 tools, `list_graph_stats_tool` → 259 files / 3161 nodes /
21658 edges, `query_graph_tool(callers_of, setEPPAfterAsusctl)` → 4 callers.

### Related
BUG-085 (the six defects and the fix). BUG-086 (found during this work — a live OpenRouter API key
is committed and pushed; unrelated cause, same root habit of `git add -A` sweeping in files that
were never meant to be tracked).

---

## DECISION 34 — MCP config lives in the scope every host reads; hooks must prove they ran
# [CHANGE: claude-code | 2026-07-25]

### Context
DECISION 33 said "`.mcp.json` is the ONLY registration." That was right about the *principle* (one
authoritative place per client) and wrong about the *place*. Cowork / Claude Desktop launches Claude
Code with `--setting-sources=user`, so project scope is never read there. The BUG-085 fix therefore
worked from a terminal and was **completely inert** in the host the user actually spends time in —
registration absent, both hooks dead — while every config file looked correct.

### Decision
1. **For Claude Code, user scope (`~/.claude/settings.json`) is authoritative** — registration *and*
   hooks. `.mcp.json` is kept empty with a comment. Rationale: user scope is the intersection of
   what the CLI and Cowork both load; project scope is the difference.
2. **Other clients get their own registration** — Claude Desktop and Antigravity are separate apps,
   not duplicates. The invariant is not "one file" but **"one binary"**: every client must point at
   the same pinned venv. Divergence, not multiplicity, is what caused v3.1.0 and v3.3.1 to fight
   over one store.
3. **User-scope hooks must be self-gating.** User scope applies to every project, so the hook
   commands are wrappers that exit 0 unless the current repo opts in.
4. **`--repo` is mandatory for GUI clients** and deliberately omitted for Claude Code. A tool that
   returns `status: ok` with an empty result set when misconfigured is worse than one that crashes.
5. **Configured is not running. Hooks must leave a trace.** Both wrappers append to
   `~/.luminos-hooks.log`; `luminos-verify` warns while a configured hook has never been observed.

### Why 5 matters more than the rest
Every fault in BUG-085 and BUG-087 shared one shape: **the config was correct and the thing never
ran.** No amount of config inspection distinguishes those states — only evidence from execution
does. This is also why hooks cannot be validated with `claude -p`: hooks do not run in headless
mode at all (tested across every `--setting-sources` value), so the log is the only instrument.

### Tradeoffs
- User-scope config is **not version-controlled**. Mitigation: `luminos-verify` fails loudly if it
  drifts, and the repo documents the expected contents. Accepted because a git-tracked file that is
  never loaded is worse than an untracked one that is.
- Three registrations mean three places to update. Accepted: cross-client binary agreement is
  checked automatically, which is the property that actually matters.
- Registering the tools in more clients invites concurrent access. Measured as safe for reads;
  heavy simultaneous ingest can hit SQLite contention. Accepted, documented in BUG-087.

### Rule 11 — conflicts documented
- **Supersedes DECISION 33's "`.mcp.json` and nothing else."** The one-authoritative-place principle
  stands; the location moves to user scope. DECISION 33 is otherwise intact.
- **AGENTS.md §6** rewritten to match; it previously instructed agents to register in `.mcp.json`,
  which would now silently fail in Cowork.

### Related
BUG-087 (findings, verification, and the still-open question of whether user-scope hooks fire in
Cowork). BUG-085 (the original rot). DECISION 33 (pinning, which still holds).

---

## DECISION 35 — The media server's BitTorrent port is open to the internet on purpose; everything else stays LAN-only
<!-- [CHANGE: claude-code | 2026-07-31] -->
**Date:** 2026-07-31
**Status:** Accepted (user-consented)
**Applies to:** the media server (Dell Inspiron 3590, `192.168.2.61`), not the G14.

### Context
qBittorrent had **uploaded 0 bytes in its entire life**. With no inbound port it can only dial
*out*, which limits it to the minority of peers that are themselves reachable. On large,
thinly-seeded 4K swarms that meant 1 connection and a stalled download — the symptom looked like a
speed problem and was actually a reachability problem.

Separately, an earlier audit found the router had **already** been forwarding port 25989 from the
internet, created silently by qBittorrent's own UPnP with nobody's consent. So the honest choice was
never "closed vs open" — it was "open by accident vs open on record."

### Decision
1. **Exactly one port is exposed: 25989/tcp + 25989/udp**, in `/etc/nftables.conf`, with a comment
   saying why. It is a peer data port: no login, no admin surface, no directory listing.
2. **Every service keeps its LAN-only rule** — WebUI 8080, Jellyfin 8096, Sonarr 8989, Radarr 7878,
   Prowlarr 9696, ssh 22. nftables, not the router, is the authority; a stray UPnP mapping can no
   longer open anything by itself.
3. **The router forward is owned by us, not by the client.** `qbt-portmap.service` + `.timer`
   (boot+90 s, hourly) re-assert the mapping at `192.168.2.61`. qBittorrent's own UPnP is **off**:
   it had mapped the *ethernet* address `.62`, and later stopped mapping at all.
4. **Firewall changes load behind an auto-rollback.** `nft -c -f` to syntax-check, then
   `systemd-run --on-active=180` armed to restore the backup, cancelled only after SSH is confirmed
   alive. A ruleset that locks you out of a headless box in another building is unrecoverable.

### Why this is acceptable rather than merely convenient
A listening BitTorrent port is the same class of exposure as any peer-to-peer client. The risk is
concentrated in the *client binary*, not in the port, and `qbittorrent-nox` runs as an unprivileged
user with no shell. Closing it again is one line and a `systemctl disable --now qbt-portmap.timer` —
documented in `docs/MEDIA_SERVER_SECURITY.md` §2a.

### How it was proven, and what lied
- **An online port checker reported 25989 CLOSED. It was wrong.** Replaced with a positive control:
  a throwaway port, `python3 -m http.server`, and a genuinely external fetcher that came back with
  our sentinel string.
- **Never test your own public IP from inside your own LAN.** Hairpin NAT makes every result
  ambiguous — refused and timed-out become indistinguishable from open.
- **`upnpc -l` prints an empty table on the Bell hub even while a mapping is live.** Only the `-d`
  return code is trustworthy: 714 = nothing there, 0 = existed and is now deleted, 606 = refused.
- The port-map unit was **negative-tested**: mappings deleted (714), unit run, mapping back (0).

### Tradeoffs
- Accepted: the box is now addressable from the internet on one port. Mitigated by scope (one port),
  by ownership (our timer, not the client's UPnP), and by a written close-it-again procedure.
- Accepted: the mapping depends on UPnP staying enabled on the Bell hub. If the owner disables it,
  the timer fails quietly and throughput regresses — the doc says to check `qbt-portmap` first.
- Not accepted: exposing the WebUI, even behind a password. There is no version of that trade that
  pays.

### Related
`docs/MEDIA_SERVER_SECURITY.md` §2a (the exception) and §2b (ARP flux on a dual-homed host — the
routing table does **not** tell you which cable a packet arrived on). Memory:
`reference_linux_silent_failures.md`, same shape as every entry there — each of these checks asked
whether a thing *existed* instead of whether it *worked*.
