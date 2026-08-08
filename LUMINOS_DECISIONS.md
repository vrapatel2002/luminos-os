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

## DECISIONS 35, 36, 36a, 37 — media server

Moved to [`server/DECISIONS.md`](server/DECISIONS.md) on 2026-08-02, along with the rest of
the media server material. Numbers are kept in this sequence so references elsewhere still
resolve:

- **35** — the server's BitTorrent port is open to the internet on purpose; everything else stays LAN-only
- **36** — torrents take the ethernet cable and give up peak speed, so the wifi radio is free for the TV
- **36a** — correction: it is the socket binding that holds the split, not the policy rule
- **37** — Jellyfin transcodes on the Intel iGPU, and the render-node number is machine-specific


---

## DECISION 38 — The laptop sleeps on lid close again, and PowerDevil's real config file is `powerdevilrc`
<!-- [CHANGE: claude-code | 2026-08-02] -->

**Status:** Applied 2026-08-02. Reverses DECISION-era commit `f8e00ab0` (2026-06-03,
*"keep all processes running on lid close, screen off only"*).

### What the user asked for
Lid close = sleep, on **both** AC and battery ("Sleep always"), and idle-suspend at
**"whatever is the system default"** — i.e. KDE's own shipped numbers, not invented ones.

### Why the machine was not sleeping — three independent layers, all deliberate
1. `/etc/systemd/logind.conf.d/luminos-nolidsleep.conf` set `HandleLidSwitch`,
   `HandleLidSwitchExternalPower` and `HandleLidSwitchDocked` all to `ignore`.
2. `~/.config/powermanagementprofilesrc` had `lidAction=0` on both profiles.
3. `/etc/udev/rules.d/99-luminos-lid.rules` → `luminos-lid.service` → `kscreen-doctor`
   blanked the panel *instead of* sleeping.

There was **no idle-suspend setting at all** on either profile, and logind's `IdleAction`
is `ignore`, so nothing ever suspended on inactivity either.

### The suspend path itself was never broken
Proven, not assumed, with a controlled `rtcwake -m freeze -s 30`: the machine slept the full
30 s, `Timekeeping suspended for 25.480 seconds`, `ACPI: \_SB_.PEP_: Successfully transitioned
to state lps0 entry`, `amd_pmc: SMU idlemask s0i3: 0x3ffb3eb5`, woke on IRQ 9 (RTC),
`suspend_stats` success 0→1, fail 0.

The 2026-08-01 "suspend loop" in the journal was **not a fault**: `upowerd` was requesting
suspend at critical battery while the user repeatedly opened the lid to wake the machine.
The final suspend had no exit because the battery died. Do not re-open this as a bug.

Known-benign and out of scope: the `\_SB.PCI0.GPP7.CADR` / `_SB.PEP._DSM` ACPI error fires
only on the **exit** path and does not stop a clean resume (AMI GA403UU.306 firmware defect);
`mmc0` (`rtsx_pci_sdmmc`) logs 12 errors per boot with no card inserted and fired one wakeup
event during the test without preventing a full sleep.

### The trap that cost the most time — and the evidence that settled it
PowerDevil 6.7.3 **does not read `powermanagementprofilesrc` for these settings.**
`PowerDevil::ProfileSettings` is a `KConfigSkeleton` over **`powerdevilrc`** (filename string
recovered from the constructor's `KConfigSkeleton(QString,QObject*)` call), the group is the
bare profile id (`"%1".arg(profileId)` → `[AC]`, `[Battery]`, `[LowBattery]`), and the items
are registered against **subgroups** — `Keyboard`, `Display`, `SuspendAndShutdown`,
`Performance`, `RunScript`.

So the working path is `[AC][SuspendAndShutdown] LidAction=1`. Writing the same key to a bare
`[AC]` group parses without complaint and **does nothing** — which is exactly what happened
first, and is the same silent-success shape as BUG-088/089.

Proved by driving the live daemon, not by reading source:
`qdbus6 org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement/Actions/HandleButtonEvents \
  org.kde.Solid.PowerManagement.Actions.HandleButtonEvents.lidAction`
returned `1` → `2` → `0` → `1` as the config was changed and PowerDevil restarted.
Under a bare `[AC]` group the same edits moved nothing.

⚠️ The sibling `triggersLidAction()` method reads `true` **regardless of configuration** — it
reports that PowerDevil owns the lid event, not what it will do with it. It is useless as a
health check. `lidAction()` is the one that tracks config.

### Enum, recovered from the shipped binary rather than guessed
`PowerDevil::ProfileDefaults::defaultAutoSuspendType()` compiles to `mov $0x1,%eax`, and
`defaultLidAction()` returns `1` on the ordinary-laptop branch. The meta-object key order is
`NoAction, Sleep, Hibernate, Shutdown, …`. **`LidAction=1` is Sleep**; `0` is Do-nothing,
which is what the old config was set to.

### The "system defaults" for idle suspend, read out of the binary
`ProfileDefaults::defaultAutoSuspendIdleTimeoutSec()` disassembles to
**AC = 900 s, Battery = 600 s, LowBattery = 300 s** (the branch for a non-mobile device).
Those exact numbers were written explicitly rather than left implicit, so the behaviour cannot
change under us if a future PowerDevil changes its defaults.

### What was changed
- **Added** `/etc/systemd/logind.conf.d/luminos-lidsleep.conf` — `HandleLidSwitch=suspend`,
  `HandleLidSwitchExternalPower=suspend`, `HandleLidSwitchDocked=ignore`.
  **Deleted** `luminos-nolidsleep.conf`. Verified live over `busctl`.
  Docked stays `ignore` on purpose: closing the lid while driving an external display should
  not black out the setup. This is also upstream's default.
- **Added** `~/.config/powerdevilrc` with `LidAction=1`, `AutoSuspendAction=1` and the
  900/600/300 timeouts under `[AC|Battery|LowBattery][SuspendAndShutdown]`.
- **Set** the legacy `powermanagementprofilesrc` `lidAction` to `1` as well. It is inert today,
  but its `[Migration] MigratedProfilesToPlasma6=powerdevilrc` marker means a future migration
  could import it; leaving `0` there was a loaded gun.
- **Deleted** `/etc/udev/rules.d/99-luminos-lid.rules` and reloaded udev. `luminos-lid.service`
  is left installed but is now never triggered (it is `static` — the udev rule was its only
  entry point). This also stops `kscreen-doctor` being invoked on every lid event, which
  SIGABRTs on this box and arms a drkonqi launcher each time (BUG-084).
- **Removed** the dead `SuspendMode=s2idle` line from `/etc/systemd/sleep.conf`.
  systemd deleted that option; it logged `Support for option SuspendMode= has been removed and
  it is ignored` twice per suspend attempt. `SuspendState=freeze` is the line that does the
  work, and `freeze` is correct here — `/sys/power/mem_sleep` on this machine is `[s2idle]`
  only, there is no S3 to fall back to.

Backups of every touched file: `backups/power-2026-08-02/`.

### Which layer actually fires
While a Plasma session is running, PowerDevil holds a **`block`** inhibitor on
`handle-lid-switch`, so **`powerdevilrc` decides what a lid close does**. The logind settings
are the fallback for SDDM, a bare TTY, and the window after logout. Both were set so the
behaviour is the same either way.

### Lesson
Two of them, and they are the same lesson the repo keeps re-learning:
- **A config file that is read is not a config file that is used.** `inotifywait` proved
  PowerDevil opened `powerdevilrc`; the values still did nothing, because the group was wrong.
  "The daemon opened my file" is not evidence. Only a readback of the resulting *behaviour* is.
- **Negative-test the readback.** `triggersLidAction()` looked like a perfect health check and
  would have reported success for every wrong configuration tried. It was caught only because
  the check was deliberately run against a config known to be wrong.

---

## DECISION 39 — Hyprland is unbanned, as an opt-in second session; Plasma stays the default
<!-- [CHANGE: claude-code | 2026-08-04] -->

**Status:** ACCEPTED, 2026-08-04. Reverses the standing ban in `AGENTS.md` §1.

### What changed
`AGENTS.md` §1 read **"PERMANENTLY BANNED: Hyprland, GTK4, HyprPanel, Python UI, Docker, Ollama,
Snapd."** The user lifted the Hyprland part explicitly:

> *"bro its no longer banned now got it? you can start now working on all phase just make sure that
> you have claude desktop running in hyprland got it ?"*

The trigger was a video — *"Install Hyprland + Caelestia Shell (Complete Guide)"* by Lau
(@laustoic) — that the user wants reproduced on this machine.

### Why the ban existed, and why it no longer applies
The ban was not arbitrary. BUG-035, BUG-036 and BUG-037 (March 2026) record a real Hyprland
attempt that failed: missing packages, a `set -e` that skipped build steps silently, and a CMake
too old to proceed. It was eventually forced through in a chroot, and then the whole direction was
abandoned in favour of KDE Plasma.

**That evidence is no longer predictive, for one specific reason: it was gathered on Ubuntu 24.04.**
Luminos is now Arch, where Hyprland is a first-class repo package with maintained dependencies.
Every one of those three bugs was a consequence of building from source against a distro that
did not carry the dependencies. None of them describe a problem with Hyprland itself.

The old *decision*, however, was deliberate, so it needed an explicit reversal rather than being
quietly ignored — hence this entry.

### Scope — this is a narrow reversal
- Hyprland is installed as an **additional session**, selectable at SDDM. It does not replace
  anything.
- **KDE Plasma remains the default and the supported desktop.** If a change is needed to make
  Hyprland work and it degrades Plasma, Plasma wins.
- **HyprPanel stays banned** — it is GTK4, which is still banned on its own merits. The shell for
  the Hyprland session is **Caelestia**, built on Quickshell (Qt6/QML). Caelestia never violated
  the constitution; it sits inside the existing Qt/QML rule. Only Hyprland itself was the banned
  component.
- The 5 Go daemons (`luminos-ai`, `luminos-power`, `luminos-sentinel`, `luminos-router`,
  `luminos-ram`) are systemd services and must keep running identically under either session. A
  compositor-dependent daemon would be a defect.

### Acceptance criteria
1. Plasma still logs in and behaves exactly as before. Non-negotiable.
2. **Claude Desktop (`claude-desktop-bin`, Electron) actually runs under Hyprland.** The user made
   this an explicit condition. A Hyprland session that starts but cannot run the agent is a failure,
   because it strands the user with no way to ask for help. Escape hatches already present in the
   launcher: `CLAUDE_USE_XWAYLAND=1`, `CLAUDE_DISABLE_GPU=1|full` (`xorg-xwayland` is installed).
3. dGPU still reaches true 0 W under Hyprland. The mechanism is global, not Plasma-specific —
   `/etc/environment` forces Mesa EGL (`__EGL_VENDOR_LIBRARY_FILENAMES=.../50_mesa.json`, BUG-047 /
   BUG-050) — so **no NVIDIA-specific env vars go into `/etc/environment` for Hyprland's benefit.**
   Check with `/sys/bus/pci/devices/0000:01:00.0/power/runtime_status`, never `nvidia-smi` (BUG-078).
4. The compositor runs on the **AMD iGPU** (`0x1002`), as KWin already does. Card numbering is not
   stable — resolve it by reading `/sys/class/drm/card*/device/vendor`, never by hardcoding.

### How it gets installed
Launch Hyprland through **uwsm** (already installed at `/usr/bin/uwsm`). uwsm wires the session
into systemd's `graphical-session.target`, which gives correct environment propagation and makes
XDG autostart work — a bare Hyprland does neither, and the session recorder depends on that target.

### Reversal path
Delete the session file and restart the login manager; nothing else is touched:

    sudo rm -f /usr/share/wayland-sessions/hyprland.desktop
    sudo systemctl restart sddm

Full OS rollback if an upgrade rather than the compositor is the problem: timeshift snapshot
`2026-08-04_14-35-50`. See `docs/ESCAPE-CARD.md`.

---

## DECISION 40 — Caelestia Shell is the Hyprland shell; power-profiles-daemon is installed but permanently masked
<!-- [CHANGE: claude-code | 2026-08-04] -->

**Status:** implemented 2026-08-04. Proven in a nested session; not yet exercised on a real login.

### What was decided
Caelestia Shell provides the bar, launcher, notifications and OSDs for the Hyprland session
(DECISION 39). Installed from the AUR: `caelestia-shell 2.2.0-1`, `caelestia-cli 1.1.2-1`,
`quickshell-git 0.3.0.r20.g28771c7-1`. Started by `exec-once = qs -c caelestia`.

This does not violate the Qt-only UI rule. Caelestia is **Quickshell — Qt6/QML**. The banned shell
was **HyprPanel**, which is GTK4, and it stays banned.

### The awkward part: a forced dependency on power-profiles-daemon
`caelestia-shell` **hard-depends** on `power-profiles-daemon`. It could not be installed without it,
and the dependency is not optional.

That is a direct threat to the thermal stack. `power-profiles-daemon` and `asusd` both write
`/sys/firmware/acpi/platform_profile`. Everything this project has built on top of that file —
`luminos-power`, the Conductor PID work (BUG-079), the workload-aware fan setpoints — assumes
**`asusd` is the sole writer**. Two daemons fighting over one sysfs file is exactly the class of
bug that is miserable to diagnose, because the symptom is intermittent thermal misbehaviour with
nothing in any log.

**Resolution: install it, then mask it.** `systemctl mask` was applied *before* it ever had a
chance to start. Masking is the right tool rather than `disable`, because it blocks **D-Bus
activation** as well as systemd start — and D-Bus activation is precisely how a desktop shell would
have woken it. `/usr/share/dbus-1/system-services/*.service` delegates via `SystemdService=`, so
the mask covers that path too.

The mask was **negative-tested**, not assumed: an activation request over D-Bus returns
`unit is masked`. (Checking `is-enabled` alone would not have proven the D-Bus path was closed —
that is the BUG-088/089 "the tool reported success while doing nothing" failure mode.)

### The accepted cost
Caelestia's battery popout contains a power-profile switcher
(`modules/bar/popouts/Battery.qml:205` — `onClicked: PowerProfiles.profile = parent.profile`).
With ppd masked, those buttons do nothing.

This is accepted, and it is the right way round: battery level and charge state still display
correctly, and **profile switching is owned by `asusctl` / `luminos-power`**, which is where the
tuned setpoints live. A shell button that silently fought the thermal daemon would be worse than a
button that does nothing. Rewiring that widget to `asusd` is a candidate for Phase 5.

**Do not unmask `power-profiles-daemon` to "fix" the battery widget.** That trades a cosmetic dead
button for unpredictable thermal behaviour.

### Why `qs -c caelestia` and not `caelestia shell -d`
Both are supported upstream. `qs` is the direct Quickshell invocation with no CLI wrapper in the
path, so a startup failure surfaces in the Hyprland log instead of being swallowed by a
daemonising helper.

It runs as an `exec-once`, **not** as a systemd user unit, because it needs
`HYPRLAND_INSTANCE_SIGNATURE`. Without that variable the shell still loads and reports
"Configuration Loaded", but every Hyprland binding is silently dead — the workspace widget and
window list stop updating with no error. An `exec-once` inherits the variable for free.

### Reversal
Comment out `exec-once = qs -c caelestia`; Hyprland then runs bare. To remove entirely:
`pacman -Rns caelestia-shell caelestia-cli quickshell-git`. Package inventory taken before the
install is in `backups/pre-caelestia-2026-08-04/`. Plasma is unaffected either way.

---

## DECISION 41 — Adopt Caelestia's stock Hyprland config verbatim; all Luminos hardware settings move to override files
<!-- [CHANGE: claude-code | 2026-08-04] -->
**Date:** 2026-08-04
**Status:** ACTIVE
**Supersedes:** the hand-written `~/.config/hypr/hyprland.conf` from DECISION 39 / Phase 3.

### Decision
`~/.config/hypr/` is now a byte-for-byte copy of the `hypr/` tree from
`github.com/caelestia-dots/caelestia`. It is **read-only** as far as Luminos is concerned.
Everything specific to this laptop lives in two files that Caelestia loads last:

- `~/.config/caelestia/hypr-vars.lua` — **values**: apps, cursor theme, sleep command.
- `~/.config/caelestia/hypr-user.lua` — **behaviour**: the GPU pin, monitor rule, env vars,
  autostarts. `hyprland.lua` `require`s it after every Caelestia module, so it always wins.

Both are tracked in the repo at `config/caelestia/`.

### Why
The Phase 3 config was written from scratch to prove the compositor could start, and it did that
job. But `caelestia-shell` is not a bar you bolt onto any config — it does not listen for
keypresses at all. It registers **22 named global shortcuts** over the Wayland global-shortcuts
protocol and waits for the compositor to fire them by name. The hand-written config bound none
of them, so the bar rendered and nothing responded: no launcher, no sidebar, no lock, no OSDs, no
media keys, no screenshot. Twenty binds existed where upstream has a hundred and forty.

Hand-porting ~80 keybinds and eleven config modules would have to be redone at every upstream
release, and Caelestia moved its whole config from hyprlang to **Lua** on 2026-06-19 — a format
change that would have made a hand-maintained fork diverge permanently. Hyprland 0.56.1 supports
the Lua provider (it is linked against `liblua` and ships `example/hyprland.lua`), and prefers
`hyprland.lua` over `hyprland.conf` automatically.

### What was deliberately NOT adopted
Caelestia's installer also re-themes GTK, Qt, Firefox, VS Code and Discord — `adw-gtk-theme`,
`papirus-folders`, `qtengine`, `darkly-bin`. Installing those would undo the Ubuntu/Yaru KDE look
built in BUG-088 / BUG-090. Only the **Hyprland and shell** configuration was taken.
Reversible at any time by running `caelestia install` and enabling those components.

Related, and load-bearing: `QT_QPA_PLATFORMTHEME` is overridden from Caelestia's `qtengine` to
`kde`, because `plasma-integration` is installed and `qtengine` is not — this keeps every Qt app
looking identical in both sessions.

### The non-negotiables that live in `hypr-user.lua`
1. **`AQ_DRM_DEVICES=/dev/dri/luminos-igpu`** — the colon-free udev alias from BUG-094. Stock
   Caelestia has no idea the NVIDIA dGPU enumerates first on this machine. Never write this as a
   `by-path` value; also duplicated in `~/.config/uwsm/env-hyprland`, which wins on a uwsm login.
2. **No NVIDIA environment variables, anywhere.** Every Hyprland guide online says to add them.
   Adding them is exactly what would undo the 0 W runtime-PM gating from BUG-047/050/078.
3. **`asusd` keeps sole ownership of `platform_profile`.** `power-profiles-daemon` is a hard
   dependency of `caelestia-shell` and stays installed-but-masked (DECISION 40). Caelestia's
   power-profile buttons therefore render and do nothing. That is expected. Do not unmask ppd to
   "fix" them — wiring them to `asusd` is Phase 5 work.
4. **`scale = 2` pinned explicitly**, not left to autodetection. Stock sets `scale = 1`, which on
   this 2880x1800 14" panel is unreadable.

### One upstream behaviour disabled by removing its binary
`execs.lua` autostarts `trash-empty 30`, which permanently deletes trash older than 30 days at
every login — here, 31 of 43 items and 8.9 GB, including Luminos project documents.
`trash-cli` is therefore **not installed**, so the command no-ops and `execs.lua` stays identical
to upstream. Do not reinstall it until that trash has been triaged.

### Reversal
`cp -a ~/luminos-backups/hypr-config-pre-caelestia-20260804-170302/hypr/. ~/.config/hypr/` and
delete `hyprland.lua`, or `git show ed68e860:config/hypr/hyprland.conf`. Plasma is unaffected
either way and remains selectable at SDDM.

---

## DECISION 42 — media server
<!-- [CHANGE: claude-code | 2026-08-04] -->

Lives in [`server/DECISIONS.md`](server/DECISIONS.md), like 35/36/36a/37. The number is
kept in this sequence so references resolve:

- **42** — all torrent traffic is halted until a VPN is in front of it (amends 35)

---

## DECISION 43 — Hyprland is the only session; Luminos UI standardizes on Qt6/QML, and GTK4 is rejected on measurement
<!-- [CHANGE: claude-code | 2026-08-04] -->

**Status:** ACCEPTED, 2026-08-04. **Supersedes the scope clause of DECISION 39** ("KDE Plasma
remains the default and the supported desktop"). Confirms and closes the GTK4 question.

### What the user asked for
> *"first move every things to gt4k base got it aim is there should be no fallback i want to use
> one things only ... i dont want 2 or 3 things running right at same thime hogging the memory
> unnecessary and also hyprland is made to work smooth with gtk4"*

Two separable requests: **(A)** one desktop, no fallback, and **(B)** move the UI to GTK4.
A was accepted. B was measured and rejected — with the user's agreement once the numbers were shown.

---

### Part A — one session at the login screen

`hyprland.desktop` and `plasma.desktop` now carry `NoDisplay=true`. The login screen offers exactly
one entry: **`hyprland-uwsm.desktop` ("Hyprland (uwsm-managed)")**, which is what SDDM already had
saved in `/var/lib/sddm/state.conf`.

**The trap, and why this uses `NoDisplay` and never `Hidden`.** The entry that *looks* redundant is
the one actually in use. SDDM launches `hyprland-uwsm.desktop`, whose `Exec` is:

```
Exec=uwsm start -e -D Hyprland hyprland.desktop
```

— it resolves `hyprland.desktop` **by Desktop Entry ID at login**. And uwsm 0.26.6 validates that
entry (`/usr/share/uwsm/modules/uwsm/main.py:472`):

```python
if entry.getHidden():
    raise RuntimeError(f"Entry {entry.getFileName()} is hidden")
```

So `Hidden=true` on `hyprland.desktop` produces **a login screen with no working session.** uwsm
never reads `NoDisplay`; SDDM's greeter honours both. Verified before and after the edit:
`uwsm start -n -e -D Hyprland hyprland.desktop` → **exit 0**, resolving to `/usr/bin/start-hyprland`.

`desktop-file-validate` reports two errors on these files (`DesktopNames` not `X-`-prefixed;
`plasma.desktop` missing `Type`). Both were confirmed **pre-existing** by validating the untouched
backups in `~/luminos-backups/sessions-2026-08-04/`. They are not caused by this change.

**Plasma packages stay installed** (`plasma-desktop`, `plasma-workspace`, `kwin` — 6.7.3). The user
chose "keep installed until proven". Removal is a separate, later decision, and is gated on the
widgets/KCMs/wallpaper actually working under Hyprland (Part C).

**Persistence.** `/usr/share/wayland-sessions/*.desktop` are pacman-owned, so a `hyprland` or
`plasma-workspace` upgrade restores the entries *silently*. `/usr/local/bin/luminos-hide-sessions`
re-applies the policy, driven by `/etc/pacman.d/hooks/luminos-hide-sessions.hook` (PostTransaction
on `usr/share/wayland-sessions/*`). It refuses to run if `hyprland-uwsm.desktop` is missing or is
itself hidden, converts any `Hidden=true` to `NoDisplay=true`, and verifies by reading back.
`--check` reports drift without changing anything. All five paths negative-tested in a sandbox.

---

### Part B — GTK4 evaluated and rejected; Qt6/QML confirmed

The stated reason for GTK4 was memory ("2 or 3 things running ... hogging the memory") and a belief
that "hyprland is made to work smooth with gtk4". Both were measured on this machine, 2026-08-04:

| Toolkit | Deduplicated resident (PSS) | Processes using it |
|---|---|---|
| `libgtk-3` | **6 MB** | 13 — 9× claude (Electron), chrome, thunar, nm-applet, xdg-desktop-portal |
| `libgtk-4` | **0 MB** | **0** |
| `libQt6` | **36 MB** | 5 — incl. `qs` (Caelestia) |

**42 MB total against 6.2 GiB in use — 0.7%.** The actual consumers were chrome (~2000 MB), claude
(670 + 377 MB) and `qs` (678 MB). Toolkit choice is not the memory lever.

Three findings make GTK4 counterproductive rather than merely unnecessary:

1. **Caelestia is Qt6 and cannot move.** `ldd /usr/bin/quickshell` → **12 Qt6 libraries, 0 GTK.**
2. **GTK3 cannot be removed.** Chrome and Claude Desktop are Electron and hard-link GTK3. Claude
   Desktop running under Hyprland is a standing acceptance criterion (DECISION 39).
3. Therefore GTK4 widgets would mean GTK3 (stays) + Qt6 (stays) + GTK4 (new) — **three toolkits
   where there are currently two** — plus a rewrite of all 16 QML files. The opposite of the goal.

Hyprland is toolkit-agnostic C++; it does not prefer GTK. **All Luminos UI stays QML/Qt6, hosted in
Quickshell.** This satisfies "one thing only" — the single base is Qt6, the one Caelestia already is.

**GTK4 therefore remains banned under `AGENTS.md` §1, now on measured grounds rather than
inherited ones.** HyprPanel stays banned with it, consistent with DECISION 39.

---

### Part C — the widgets were never a toolkit problem

The reason Plasma still *felt* necessary is that these are **Plasma-shaped**, not GTK-shaped:

| Component | Shape | Fate |
|---|---|---|
| `org.luminos.{ram,power,monitor}widget` | Plasma applets | re-host as Quickshell modules (stays QML) |
| `kcm_luminos_{keyboard,hive,lid_light}` | Plasma KCMs | fold into `src/look/LookDashboard.qml` |
| `org.luminos.livewallpaper` | Plasma wallpaper plugin | **cannot be ported** — retire |

Nothing loads a Plasma applet under Hyprland, so they simply never appeared. Re-hosting them is
what actually removes the fallback.

**Live wallpaper:** replaced by **Caelestia's built-in wallpaper**, chosen by the user over
`mpvpaper` and `swww`. Rationale: no persistent `mpv` process and no continuous GPU decode, which
matters on a machine whose dGPU power gating is load-bearing (BUG-078, DECISION 25).

### Acceptance criteria
1. The login screen shows exactly one session, and it logs in. *(Verified only at next login.)*
2. `luminos-hide-sessions --check` exits 0; exits 1 after a simulated upgrade restores an entry.
3. The 5 Go daemons stay `active` — they are systemd services and must not care about the compositor.
4. Claude Desktop still runs under Hyprland (carried over from DECISION 39).
5. Plasma is not removed until 1–4 hold and the widgets/KCMs/wallpaper work.

### How to reverse
```bash
sudo rm /etc/pacman.d/hooks/luminos-hide-sessions.hook
sudo cp ~/luminos-backups/sessions-2026-08-04/*.desktop /usr/share/wayland-sessions/
```
Plasma reappears at the login screen immediately; nothing was uninstalled.

---

## DECISION 44 — media server
<!-- [CHANGE: claude-code | 2026-08-04] -->

Lives in [`server/DECISIONS.md`](server/DECISIONS.md), like 35/36/36a/37/42. The number is
kept in this sequence so references resolve:

- **44** — a series may hold at most 2 seasons, enforced by `luminos-season-limit.timer`;
  171.83 GB reclaimed from orphaned downloads and unwanted seasons

---

## DECISION 45 — Every window floats by default, and hyprbars supplies minimize / maximize / close
<!-- [CHANGE: claude-code | 2026-08-05] -->

**Supersedes the last paragraph of DECISION 41**, which recorded "no hyprbars/titlebars added —
Caelestia has none by design and user confirmed current look is correct." That is no longer what
the user wants.

### The problem, stated correctly
Shawn reported windows "locked to a certain position — all I can do is left or right." That is not
a bug. Stock Caelestia is `general:layout = dwindle`, so a second window splits the screen and the
two cannot overlap. He wants the Plasma/Windows model: windows that open free, stack on top of one
another, and carry buttons.

### What was decided
1. **Everything floats**, via a catch-all rule in `hypr-user.lua` (required last, so it wins):
   `hl.window_rule({ match = { class = ".*" }, float = true })`.
   Deliberately **not** `general:layout = floating` — that would turn `SUPER+ALT+Space`
   (kbToggleWindowFloating) into a no-op and remove tiling permanently. A rule floats at map time
   while leaving dwindle available on demand. The rule sets **only** `float`, so the sized floaters
   in `rules.lua` keep their own geometry.
2. **Titlebars via the hyprbars plugin**, configured in a new `~/.config/caelestia/hypr-bars.lua`.
   It is a separate module so the nested test compositor loads the *same file* that ships.
3. **Actions go through `luminos-win`** (`scripts/luminos-win` → `/usr/local/bin`), not inline
   command strings, so each action can be run and tested on its own.
4. **`SUPER+ALT+M` restores minimized windows.** `SUPER+SHIFT+M` was the obvious choice and is
   already volume mute (`variables.lua:133`).

### Why the implementation looks odd, in three places
- **Buttons are added from a timer, not inline.** `hl.plugin` holds only `load` while the config is
  parsing; `hl.plugin.hyprbars` appears later. Adding buttons inline is a race that fails silently.
- **`min` issues two dispatches.** Moving a window to a special workspace also *opens* it, so the
  window stays on screen — a move, not a minimize. There is no `move_silent` in the Lua dispatcher
  table, and `silent = true` is accepted and ignored, because **dispatcher tables are not validated
  and any unknown field returns `ok`**. The second dispatch closes the workspace, guarded on it
  actually being open.
- **The three button colours are hardcoded** while the bar itself is themed from the live Caelestia
  scheme. The scheme *does* define `red`/`green`/`yellow`, which is the trap: they are harmonised
  into the wallpaper palette, so `red` was `c1a5fd` (purple) and `green` was `c8e3ff` (pale blue).
  A close button must read as "close" under every look.

### Risk accepted, and how it is contained
hyprbars is a **compiled** plugin pinned `hyprland>=0.56.0 <0.57.0`. Upgrading Hyprland without
rebuilding it in the same transaction breaks the load. The `require` is wrapped in `pcall`, so a
stale plugin costs the titlebars and nothing else — unguarded, a config error drops Hyprland into
emergency mode with **no binds registered**, which is a black screen with no keyboard way out.

### Verified live, 2026-08-05
Reload clean, 0 config errors, 150 binds (steady across two reloads), 7 layers, shell alive.
`plugin:hyprbars:bar_height` reads back `26` and `bar_color` `4280295203` = `0xff201f23`, the
scheme's `surfaceContainer`, proving the theming applies rather than defaults. On a throwaway
window: `min` parked it on `special:minimized` **and left the workspace hidden**, `restore` brought
it back, `max` gave fullscreen mode 1 at 1368x852 (work area — the panel stays visible), `close`
removed it. Desktop returned to its 3-client baseline.

### How to reverse
Delete the titlebar block at the end of `~/.config/caelestia/hypr-user.lua` (or restore
`hypr-user.lua.bak-prebars`) and `hyprctl reload`. To go back to tiling as well, delete the
`hl.window_rule` float line (or restore `hypr-user.lua.bak-prefloat`).

---

## DECISION 46 — Titlebars removed; float is the default and tiling is opt-in per app
<!-- [CHANGE: claude-code | 2026-08-05] -->

**Supersedes the hyprbars half of DECISION 45.** The floating half of 45 stands unchanged —
everything still floats by default. Shawn's verdict on the buttons was simply: *"i do not like
the 3buttons remve that things."* So the plugin is gone and the same four actions are keys now.

### What was removed
`hypr-bars.lua` is deleted and its `require` is out of `hypr-user.lua`. Confirmed by measurement,
not by assuming a reload is enough: after `hyprctl reload`, `hyprctl plugin list` reports **no
plugins loaded** — the compositor drops a plugin when the config stops loading it, so no session
restart was needed. Bind count moved 150 → 152 (one retired, three added) with 0 config errors and
all three open windows surviving.

This also retires the DECISION 45 upgrade hazard: hyprbars was a compiled plugin pinned
`hyprland >=0.56.0 <0.57.0`, and a Hyprland bump without a matching rebuild would have failed at
session start. Nothing now depends on that pin. The package is left installed but unloaded, so
reversing this is a one-line `require`, not an AUR build.

### Minimize had to be rescued first
Two Chrome windows were sitting on the `special:minimized` workspace, put there by the button that
was about to be deleted. Removing hyprbars first would have stranded them with no button and no
bind. They were moved back before anything else changed.

That rescue turned up something the old code did not know: **`window = 'address:0x…'` inside the
Lua move table IS honoured.** `luminos-win restore` previously just toggled the special workspace
open, which showed the parked windows as an overlay that vanished again — they were never actually
put back. It now moves every parked window to the current workspace and re-reads the workspace list
to confirm none are left behind.

### Float by default, tile by exception
"Locked" means pinned into the dwindle tiling layout instead of floating free. The catch-all
`float = true` rule stays; classes listed in `~/.config/caelestia/hypr-locked.conf` get a later
`float = false` rule that overrides it.

That ordering was proven in a throwaway nested Hyprland before shipping, because window-rule tables
are **not validated** — an unknown key returns ok and does nothing, so "it reloaded cleanly" proves
nothing. Three kitty windows, `floating` read back off each:

| rule applied | `floating` |
|---|---|
| catch-all `float = true` only | 1 |
| later `float = false` | 0 |
| later `tile = true` | 0 |

Both spellings work; `float = false` is used as the direct inverse of the rule it overrides.

### Why the locked list is a text file and not Lua
`luminos-win` rewrites it on every lock/unlock. If it were Lua, one bad write would be a config
**syntax error**, and a config syntax error puts Hyprland in emergency mode with no binds
registered — a black screen with no keyboard way out. A text file that goes wrong costs one missing
rule. For the same reason the class is allow-listed to `[A-Za-z0-9._-]` twice, once in the script
and again in the Lua reader: these strings are interpolated into a Lua pattern, so a stray quote is
a syntax error rather than a cosmetic bug. Negative-tested by appending `bad";class="evil` to the
file and reloading — 0 config errors, binds still 152, line skipped.

### Keys
Only minimize actually needed inventing. Close, maximize and the one-shot float/tile toggle already
existed in stock Caelestia, so the rest of the desktop is untouched.

| Key | Action |
|---|---|
| `SUPER + H` | minimize (hide) the focused window |
| `SUPER + SHIFT + H` | bring every minimized window back |
| `SUPER + SHIFT + Space` | lock/unlock this **app** to tiled — persists |
| `SUPER + ALT + Space` | float/tile this **one window** — stock, until it closes |
| `SUPER + Q` / `SUPER + ALT + F` / `SUPER + P` | close / maximize / pin — all stock |

`SUPER + ALT + M` (restore, added yesterday) is retired so hide and un-hide sit together.
`SUPER + SHIFT + M` was never available — it is volume mute at `variables.lua:133`.

All combos were checked free against `hyprctl binds` on the **running** compositor. Note that this
only answers "is it taken": every Lua bind reports `dispatcher: "__lua"` with an opaque numeric
arg, so the live compositor cannot say what a bind *does*. Meaning has to come from the config.

### Bar shows all windows, not just the focused one
`~/.config/caelestia/shell.json` sets `bar.workspaces.showWindows` + `maxWindowIcons: 8`, so each
workspace pill lists one icon per open window instead of the bar naming only the active one.

The config path was **found, not guessed**. It is not in the QML tree or in any string inside the
plugin — Caelestia 2.2.0 moved config to C++ and ships the QML as a Qt resource (`prefer
:/qt/qml/Caelestia/Config/`). Candidate files were created at both plausible paths and the shell
restarted under `inotifywait`; it opened `~/.config/caelestia/shell.json` and ignored
`~/.config/quickshell/caelestia/shell.json`. Confirmed authoritative by flipping `showWindows` to
false and watching the icons disappear — and it live-reloads, no restart needed.

**Known limit, not yet solved.** These are `Icons.getAppCategoryIcon(class)` **category** glyphs
(Chrome and Claude both render as generic marks), and the `Repeater` has no `MouseArea`, so they
are an indicator and not a click-to-focus taskbar. Caelestia 2.2.0 has no Tasks/WindowList/dock
module at all — `modules/bar/components/` holds only ActiveWindow, Clock, OsIcon, Power,
StatusIcons, Tray and workspaces. A real taskbar means a custom Quickshell module plus a patch to
`Bar.qml`'s `DelegateChooser`, and `Bar.qml` is package-owned under `/etc/xdg/quickshell/caelestia/`,
so it would need the whole tree forked into `~/.config/quickshell/caelestia/` — which stops
`caelestia update` from ever updating it again. That trade is Shawn's to make, so it is deferred
rather than decided here.

### How to reverse
Delete `shell.json` for the bar icons. For the rest, remove the "Locked apps" and "Window action
binds" blocks at the end of `~/.config/caelestia/hypr-user.lua` and `hyprctl reload`. To get the
titlebars back, restore `config/caelestia/hypr-bars.lua` from git and re-add its `require`.

---

## DECISION 47 — The text editor is a single QML file on the stock `qml6` runtime, not a package
# [CHANGE: claude-code | 2026-08-05]

**Ask:** *"bro add as simple tool through which i can edit files somethings like notepad. make it
real quick"*

### The finding that shaped the decision
There was **no graphical text editor on this machine at all.** `pacman -Q` came back empty for
kwrite, kate, gedit, featherpad and mousepad; the only editors installed were `nano` and `vim`.
And `xdg-mime query default text/plain` returned **`org.kde.okular.desktop`** — a PDF *viewer*. So
double-clicking a config file opened it read-only, in a program that cannot type.

### The decision
Write the editor as **one `.qml` file executed by the stock `/usr/bin/qml6`**, rather than
installing anything.

- Every packaged lightweight editor on Arch is **GTK4**, which AGENTS.md §1 bans outright.
- `qt6-base` and `qml6` are already installed, so this costs **zero new packages and zero build
  step** — no CMake target, no `.so`, nothing to rebuild after a Qt upgrade.
- It lands inside the project's existing Qt/QML rule instead of opening a second UI toolkit.

Shipped as `src/notepad/Notepad.qml` + `scripts/luminos-notepad` (→ `/usr/local/bin`) +
`config/luminos-notepad.desktop`, registered as the default handler for text/plain, markdown,
json, yaml, csv, ini, shell, python and log.

### The tradeoff this buys — and the trap it creates
QML has **no file API**. The only way a plain `qml6` document touches the disk is
`XMLHttpRequest` against a `file://` URL, unlocked by `QML_XHR_ALLOW_FILE_READ=1` /
`QML_XHR_ALLOW_FILE_WRITE=1` (both exported by the launcher). That is the price of avoiding a
compiled backend, and it comes with a genuinely dangerous property:

> **A `PUT` that fails and a `PUT` that succeeds are byte-identical from QML's side —
> both report `readyState = DONE`, `status = 0`.**

Measured, not assumed. A probe wrote to `/tmp` (status 0, file appeared) and to
`/proc/luminos-cannot-write` (status 0, nothing written). **Status can never detect a failed
save.** So `saveFile()` issues a `GET` after every `PUT` and compares the result to the buffer;
only a match sets `savedText` and prints "Saved". On mismatch it prints `SAVE FAILED` and leaves
the buffer marked modified, so the unsaved-changes guard still fires. Negative-tested.

This is the same silent-success shape as **BUG-088/089** — a tool reporting success for work it
never did. Anyone "simplifying" the read-back away reintroduces it.

Two smaller traps recorded in `docs/CODE_REFERENCE.md`: assign `savedText` **before** `editor.text`
in `loadFile()` or the titlebar flashes a modified dot on every open; and the launcher — not the
QML — rejects directories, unreadable files and binaries, because XHR reports a *missing* file and
an *empty* file identically (status 0, empty body) while the shell still has the real errno.

### How to reverse
```bash
xdg-mime default org.kde.okular.desktop text/plain
rm ~/.local/share/applications/luminos-notepad.desktop
sudo rm /usr/local/bin/luminos-notepad
```
Recorded in AGENTS.md §9.

## DECISION 49 — Hyprland plugins run again; hyprpm is version-pinned state that must be rebuilt after every Hyprland upgrade
# [CHANGE: claude-code | 2026-08-05]

**Ask:** "make it run the hyprmods here … install whatever it takes."
**Outcome:** three plugins are built, enabled, loaded and reloaded automatically at every login —
`borders-plus-plus`, `hyprfocus`, `hyprexpo`. Before this, `hyprpm list` showed nine plugins,
**all disabled, two failing to build, zero loaded.**

### The root cause was one stale line
hyprpm plugins are C++ `.so` files compiled against the **exact Hyprland commit** in use. hyprpm
stores which commit it built for:

```
# /var/cache/hyprpm/shawn/state.toml   (BEFORE)
hash = '521ece463c4a9d3d128670688a34756805a4328f_aq_0.10_hu_0.12_hg_0.5_hc_0.1_hlg_0.6'
```

`521ece46…` is Hyprland **0.54.3, from April**. The running compositor is **0.56.1
(`5c9377c1…`)**, and the support libraries had moved with it — aquamarine 0.10 → 0.14,
hyprutils 0.12 → 0.14. That single mismatch explains **both** symptoms at once: the two plugins
that touch changed APIs failed to compile, and the rest were never loaded because nothing had
been rebuilt. `hyprpm update` pulled matching headers and rebuilt everything:

```
# /var/cache/hyprpm/shawn/state.toml   (AFTER)
hash = '5c9377c15f85c50648f35ca5a213754f95b93ca0_aq_0.14_hu_0.14_hg_0.5_hc_0.1_hlg_0.6'
```

> **This will happen again.** Any `pacman -Syu` that moves Hyprland off 0.56.1 re-breaks every
> plugin, and it breaks them **silently** — the compositor starts normally, nothing errors on
> screen, the borders and the overview simply stop existing. The fix is always
> `hyprpm update && hyprpm reload`.

### The state is not in $HOME — that cost real time
Upstream hyprpm documents `$XDG_DATA_HOME/hyprpm`. **Arch's package puts it in
`/var/cache/hyprpm/$USER/`.** Every search under `~` returned nothing while `hyprpm list`
happily printed a repo, which reads exactly like a phantom. Settled by
`env HOME=/tmp/fakehome hyprpm list` producing **identical output** — proving the state could
not be HOME-based — then finding it under `/var/cache`. Anyone debugging plugins should start
at `/var/cache/hyprpm/$USER/state.toml`, not in the home directory.

### Half the plugin roster no longer exists
`hyprexpo`, `hyprtrails`, `hyprwinwrap`, `hyprscrolling` and `xtra-dispatchers` were **deleted**
from `hyprwm/hyprland-plugins` in May 2026 — *"it's been removed. It was unmaintained"* (vaxry,
issue #672). They were not moved to another `hyprwm` repo; checked, they are not there. Only
`borders-plus-plus`, `csgo-vulkan-fix`, `hyprbars` and `hyprfocus` still ship.

`hyprexpo` was recovered from **`github.com/sandwichfarm/hyprexpo`**, the maintained community
fork that picked it up after the retirement, added as a second hyprpm source. Its `hyprpm.toml`
pins stop at 0.56.0 while we run 0.56.1. **That is not a runtime risk:** hyprpm compiles against
the *installed* headers, so a genuine API break shows up as a **build failure at install time**,
which is harmless and loud. It built clean and loaded. (I initially called this "an ABI gamble I
won't take on a live session" — that was wrong, and the correction is the useful part: an unpinned
version is a build-time question, not a crash-at-login question.)

### What is enabled, and what is deliberately not
| Plugin | State | Why |
|---|---|---|
| `borders-plus-plus` | ✅ enabled | One extra 2px border outside the normal one, `natural_rounding` so it follows the 15px corner radius |
| `hyprfocus` | ✅ enabled | Brief flash when **keyboard** focus lands on a window. Mouse animation off — with focus-follows-mouse it fires on every pointer cross |
| `hyprexpo` | ✅ enabled | Expose-style grid of all workspaces, `SUPER+G` |
| `hyprbars` | ❌ **left disabled on purpose** | It builds fine and is one command away, but titlebars and their three buttons were **removed earlier the same day at the user's request** (DECISION 46). Enabling it would silently undo that work |
| `csgo-vulkan-fix` | ❌ not enabled | Fixes mouse offsets in CS:GO under Vulkan. Not installed here |

### Nothing loaded plugins at login
`hyprpm enable` only records a choice in `state.toml`; **Hyprland does not act on it.** Without an
explicit load the plugins are absent after every logout, with nothing on screen to say so. Added
to the `hyprland.start` handler in `hypr-user.lua`:

```lua
hl.exec_cmd("hyprpm reload -n")
```

`-n` is `--notify`, i.e. **send** a notification — not "no notify". Kept on purpose: a
wrong-version plugin fails to load silently, so the login toast is the only positive confirmation
that any of this is live. **Proven, not assumed** — both `.so`s were unloaded (`hyprctl plugin
list` → nothing), the exact login command was run, and both came back with their config intact
and no root needed.

### Three traps worth keeping
1. **`hyprctl keyword plugin:…` is refused under the Lua parser** — *"keyword can't work with
   non-legacy parsers. Use eval."* This is the same shape as the `luminos-look` finding. Plugin
   options must be set in the Lua config (`hl.config { plugin = { … } }`) and applied with
   `hyprctl reload`. Note the names differ by punctuation: **underscores in Lua**
   (`borders_plus_plus`), **hyphens in the namespace** (`plugin:borders-plus-plus:…`).
2. **`hyprctl dispatch` reports a failure for a call that worked.**
   `hyprctl dispatch 'hl.plugin.hyprexpo.expo("toggle")'` **opens the overview** and then prints
   `error: expected a dispatcher` — the plugin fires as a side effect and returns nil, which
   hyprctl's own wrapper rejects. The error is about hyprctl, not the plugin. `hyprctl submap`
   reads `hyprexpo` and tells the truth. This is the *inverse* of the BUG-088/089 shape: a tool
   reporting failure for work it actually did.
3. **A colour can be "applied" and still be invisible.** The first border colour chosen here
   (`rgba(00000066)`) read as *set: true* in `hyprctl getoption` and could not be seen at all
   against the dark wallpaper. Config state is not visual proof. Settled by temporarily setting
   a 6px `rgb(00ff00)` border, screenshotting it to prove the plugin actually renders, then
   shipping `rgba(ffffff26)` at 2px and screenshotting again to confirm it is visible.

### hyprexpo bindings
`SUPER+G` toggles the overview. `SUPER+G`, `SUPER+grave` and `SUPER+Tab` were all confirmed free
by querying the **running compositor** (`hyprctl binds`), not by grepping the config — Caelestia
registers most of its keys from Lua, so the files under-report. While the overview is open,
hyprexpo activates a submap named `hyprexpo` and **only that submap's keys are live**; the rest of
the desktop is suspended until it closes. That is why `escape` is re-bound explicitly — without it
the overview would be closable only by mouse. Arrows and `hjkl` move the selection, `return`
confirms, and digits select the **Nth visible tile** (`number_key_mode = index`) rather than a
global workspace ID, which is what you actually mean when looking at a grid. `drag_drop_enable = 0`
because a click whose pointer drifts a few pixels — constant on a touchpad — otherwise **moves a
window** instead of switching workspace.

Verified with a screenshot: a 3×3 grid, numbered tiles, workspace 1 showing its real windows.

### How to reverse
```bash
hyprpm disable hyprexpo && hyprpm remove https://github.com/sandwichfarm/hyprexpo
hyprpm disable borders-plus-plus && hyprpm disable hyprfocus
hyprpm reload
# then delete the plugin block + SUPER+G bind + submap from
# ~/.config/caelestia/hypr-user.lua, and the luminos-hyprpm-sync line in hyprland.start
```
A full-file backup sits at `~/.config/caelestia/hypr-user.lua.bak-preplugins`.

### Amendment, 2026-08-08 — the rebuild is no longer manual
# [CHANGE: claude-code | 2026-08-08]
This decision closed with a standing instruction to run `hyprpm update && hyprpm reload` by hand
after every Hyprland upgrade. That instruction was correct and it was still not enough: Hyprland
went 0.56.1 → 0.56.2 on 2026-08-05 and every plugin died again three days later (**BUG-111**).
A maintenance step that depends on a human remembering it, for a failure whose only symptom
points at the wrong file, is not a fix.

`hyprland.start` now calls **`scripts/luminos-hyprpm-sync`** instead of a bare `hyprpm reload -n`.
It compares hyprpm's stored build hash with the running compositor commit, rebuilds only on a
mismatch, and then reads the loaded-plugin count back out of `hyprctl` rather than trusting
hyprpm's own success output.

**Session start is the only correct trigger, and this is worth writing down because a pacman hook
looks obviously better and is obviously wrong:** hyprpm builds against the *running* compositor,
so during the pacman transaction it would rebuild against the version being uninstalled; and
pacman hooks run as root, whose hyprpm state is not Shawn's. Both problems disappear at login.

The manual command still works and is still the right thing to type if you are debugging. It just
should no longer be *needed*.

---

## DECISION 50 — Tiling is the default, floating is the exception, and the layout is dwindle again
**Date:** 2026-08-05
**Agent:** claude-code
**Supersedes:** the floating half of DECISION 45 and DECISION 46

Shawn asked for three things in one sentence: what the window-lock shortcut is, that windows stop
hanging off the edge of the screen, and that float-by-default be removed — *and to be told where the
switch is*, so he can flip it back himself.

### The switch
`~/.config/caelestia/hypr-locked.conf` now opens with a directive:

```
default = tiled       # or: default = floating
```

and `luminos-win default tile|float` (bare `luminos-win default` prints the current one) edits it and
reloads. The switch deliberately lives in the **text** file rather than `hypr-vars.lua`, for the same
reason the class list does: `luminos-win` rewrites this file on a keypress, and a bad write to a Lua
file is a syntax error, which is emergency mode, which is a black screen with no binds to escape with.

### The list now means "the opposite of the default"
It used to mean "force this app tiled", which becomes meaningless once tiled is the default. Every
class listed gets the **inverse** of the directive above it, so the same file keeps working when the
default is flipped. `luminos-win list` prints the default first and then the exceptions in those terms,
and the lock/unlock messages name the outcome ("will now open floating (default is tiled)") instead of
the bookkeeping.

The fallback — *anything that is not exactly `floating` means tiled* — is written **twice, verbatim**:
once in `luminos-win`, once in the Lua reader in `hypr-user.lua`. Both files parse the same directive,
so a typo like `default = floatng` has to fail the same way in both, or the script prints a message
that does not match what the compositor did.

### The real cause of "windows going out the area"
Not floating. `hyprctl getoption general:layout` read back **`scrolling`**, despite
`~/.config/hypr/hyprland/general.lua:5` declaring `dwindle`. The override was in
`~/.config/hypr/hyprland-gui.lua:9`, written by the HyprMod settings GUI — and that file is
`require`d **last** in `hyprland.lua`, after `hypr-user.lua`, so it beats every Luminos override.

A scrolling layout lays tiled windows out in an endless horizontal strip and keeps only the focused
column in view. Measured before the fix: three tiled windows at x = 72 / 1427 / 2102, spaced 1355
apart on a **1440**-wide screen. That is the symptom, exactly.

Set back to `dwindle` **in `hyprland-gui.lua` itself** rather than by overriding it elsewhere, so the
HyprMod GUI keeps showing the truth. Anything appended to `hypr-user.lua` would have been silently
re-overridden by the file loaded after it.

### Floating windows are clamped as well
A late `hl.window_rule({ match = { float = true }, max_size = "(monitor_w*0.9) (monitor_h*0.9)",
center = true })` catches the other half of the complaint: `antigravity` was floating at 1416x916 on a
1440x900 screen (over the right edge by 49 and the bottom by 59) and `Pdf4QtEditor` over the right by
11. Proven in a nested Hyprland first — control window 2000x1200 unclamped, `"600 400"` → 600x400,
`"(monitor_w*0.5) (monitor_h*0.5)"` → 640x400, and a **tiled** window under the same rule untouched at
1278x798, confirming the `float = true` match does not leak.

Note the spelling: `maxsize` is **not** a Lua-parser key. `max_size` is.

### `Hyprland --verify-config` — correcting a standing project note
Earlier decisions record that rule tables are "not validated". They are not validated **at runtime**,
which remains true and is why behaviour still has to be read back. But
`Hyprland --verify-config -c <file>` checks a config **without starting a compositor** and names every
unknown key. That is what caught `maxsize`.

Used it as a regression gate rather than a spot check: a `/tmp/verifybase` tree of symlinks to the real
config plus the *pre-edit* `hypr-user.lua`, run under `HOME=/tmp/verifybase`, line numbers normalized
and sorted. Before and after are **identical** — 21 findings, all of them pre-existing `plugin.*` keys
that are absent only because `--verify-config` does not load hyprpm plugins.

### Proven, not assumed
- Layout reads back `dwindle`; all six open windows now inside the 1370x880 work area (`0/6` overhanging, was `4/6`).
- A brand-new window: tiled **PASS**, inside the work area **PASS** (spawned, measured, closed).
- `togglelock` round-tripped on a live window: lock → "will now open floating (default is tiled)",
  `list` shows the exception; unlock → "goes back to opening tiled", `list` shows none. Window state
  followed in both directions.
- The immediate flip is guarded on the *current* state, because `hl.dsp.window.float()` is a **toggle** —
  calling it unconditionally would flip windows that were already correct.

### Keys (unchanged — this is the answer to the question asked)
| Key | Action |
|---|---|
| `SUPER + SHIFT + Space` | flip this **app** and remember it — writes `hypr-locked.conf` |
| `SUPER + ALT + Space` | flip just **this window**, until it closes |
| `SUPER + H` / `SUPER + SHIFT + H` | minimize / restore all |
| `SUPER + Q` / `SUPER + ALT + F` / `SUPER + P` | close / maximize / pin |

### Rollback
```bash
luminos-win default float
sed -i 's/layout = "dwindle"/layout = "scrolling"/' ~/.config/hypr/hyprland-gui.lua
hyprctl reload
```
Full-file backups: `~/.config/caelestia/hypr-user.lua.bak-prefloatoff` and
`~/.config/caelestia/hypr-locked.conf.bak-prefloatoff`.

---

## DECISION 52 — The dGPU gate must make the group **real**, not just effective; `dgpu-exec-v2` supersedes `dgpu-exec`
**[CHANGE: claude-code | 2026-08-05]** — Chrome only, for now. See BUG-102.

### The decision
`dgpu-exec` grants dGPU access by being setgid `dgpu`. That raises only the **effective** gid.
As of today the gate also calls `setresgid(g, g, g)`, making the `dgpu` gid **real** as well,
before it execs the target. Shipped as `dgpu-exec-v2`; source in `scripts/dgpu-gate/dgpu-exec-v2.c`.

### Why — effective-only was silently useless for most apps
A raised-egid-only process is "privileged", and that privilege breaks the very thing it grants:

| | consequence |
|---|---|
| `bash`/`sh` reset egid → rgid at startup as setgid protection (unless `-p`) | the group is **dropped at the first shell wrapper**, so any app launched by a shell script gets nothing |
| `access(2)` consults the **real** gid | `[ -r ]` / `[ -w ]` report DENIED on devices that open fine — health checks lie |
| a setgid exec sets `AT_SECURE=1` | Chrome's setuid-root `chrome-sandbox` refuses: *"Running as root without --no-sandbox is not supported"* |

Chrome goes through **two** bash wrappers before the real binary, so it hit the first and third at
once. `setresgid` removes all three, because real == effective means the process is not privileged.

This was never caught because the only test anyone ran was `dgpu-exec nvidia-smi` — a **direct ELF
exec**, the one case v1 handles correctly.

### Why this does not widen the gate
Access is still granted **only** to processes launched through the setgid binary; everything else
is denied by the `0660 root:dgpu` device nodes. The change is that the grant now *survives the exec
chain* instead of evaporating at the first shell. If anything the posture improves: v1's failure
mode was **silent and dishonest** — it announced NVIDIA and delivered the iGPU.

### Scope, deliberately narrow
`dgpu-exec-v2` is installed alongside v1 and wired into `chrome-luminos` **only**. `luminos-gpu-launch`
and every other gated app still call v1, and therefore still lose the group whenever the thing they
launch is a shell script. Chrome first, by explicit request; the rest once each is re-verified.

**Follow-ups this leaves open:**
- Promote v2 over `dgpu-exec` and retire the `-v2` name, after re-verifying the other gated apps.
- `luminos-gpu-launch:65` still points at `radeon_icd.x86_64.json`, which **does not exist** on Arch
  (BUG-061 established this for `chrome-luminos`; the sibling was never corrected). Latent.
- `--remote-debugging-port=9222` no longer works on Chrome's default profile and only emits a
  confusing error; candidate for removal.

### Operating notes
- Never build the binary in `/tmp` — it is mounted `nosuid`, the setgid bit is ignored, and the
  result reports `egid=1000` and looks broken for the wrong reason.
- Verify the gate with a **real `open(2)`**, never `[ -r ]`:
  `dgpu-exec-v2 sh -p -c 'exec 3<>/dev/nvidiactl; exec 4<>/dev/nvidia0'`
- Ask **Chrome** which GPU it got, don't trust the notification: launch with a non-default
  `--user-data-dir` plus a free `--remote-debugging-port`, then call DevTools `SystemInfo.getInfo`
  and read `auxAttributes.glRenderer`.

### Rollback
```bash
sudo sed -i 's/dgpu-exec-v2/dgpu-exec/g' /usr/local/bin/chrome-luminos   # back to v1 behaviour
sudo install -m0755 /usr/local/bin/chrome-luminos.bak-bug102-20260805 /usr/local/bin/chrome-luminos
sudo rm /usr/local/bin/dgpu-exec-v2
```

---

## DECISION 53 — a real policy for the dGPU gate, instead of one universal door
# [CHANGE: claude-code | 2026-08-05]
**Status:** PROPOSED — designed and researched, not built. Nothing in this section is installed.
**Supersedes nothing.** Builds on DECISION 25 (the gate) and DECISION 52 (`dgpu-exec-v2`).

### What is actually wrong with the gate we have
DECISION 25 gives us a **door, not a policy**. The device nodes are `0660 root:dgpu`, the `dgpu`
group is empty, and `dgpu-exec-v2` is a setgid binary that hands that group to whatever you point it
at. That is a genuine default-deny — an app that just enumerates GPUs gets nothing, which is the
whole reason Claude Desktop and antigravity stopped poking the card. But it has three gaps:

1. **It cannot tell apps apart.** `dgpu-exec-v2 chrome` and `dgpu-exec-v2 anything-else` are the
   same operation. Everything on this box runs as `shawn`, so there is no identity to check against.
2. **It keeps no record.** Grepped the whole gate — `install-dgpu-gate.sh`, `dgpu-exec*`,
   `luminos-gpu-launch`, `chrome-luminos` — and there is **not one line of logging anywhere.** This
   is precisely why BUG-102 hid for a month: a wrong answer and a right answer look identical from
   the outside. Silence was the bug's habitat.
3. **It has nowhere to put the "afterwards".** The launchers `exec`, so there is no point at which
   the card can be released — which is BUG-103.

So "smarter" here does not primarily mean "harder to break". It means: **decide per application,
remember the decision, and leave a trace.**

### The design: one choke point, one root-owned policy file, one log

Everything already funnels through a single setgid binary. Make that binary the decision point
rather than a rubber stamp.

```
/etc/luminos/dgpu-policy.conf        root:root 0644 — authoritative, system-wide
    allow  /opt/google/chrome/chrome
    deny   /usr/bin/antigravity
    ask    *
~/.config/luminos/dgpu-user.conf     shawn — remembered answers, consulted ONLY for `ask`
/var/log/luminos/dgpu.log            every decision, one line, append-only
```

`dgpu-exec-v3` then does, before `setresgid`:

1. Resolve `argv[1]` through `PATH`, then `realpath()` it. Compare the **resolved path**, never the
   string you were handed.
2. Look it up: `deny` → log, `notify-send`, exit 77. `allow` → log, grant. Unknown → `kdialog`
   *"X wants the RTX 4050 — Allow once / Always / Never"*, record the answer in the user file, log it.
3. Grant = `setresgid` + `exec` exactly as v2 does today.
4. On the way in, take the card up; register a release so BUG-103 stops happening — see below.

Why this shape and not something cleverer: it is ~80 lines of C on top of a binary that already
exists and is already proven, it needs no new packages, no kernel work, and no daemon. And it turns
the invisible into the visible, which is the failure mode that actually cost us a month.

### The release problem, solved in the same place
Because every grant now passes through one binary, that binary is the only sane place to own the
card's power state. Instead of `echo on` scattered across three launchers with no counterpart:
`dgpu-exec-v3` does **not** `exec` blindly — it `fork()`s, waits for the child, and on exit writes
`auto` back if it was the last grant outstanding (a counter/lockfile under `/run/luminos/`). Wake
and release finally live at the same address. This is the fix path for BUG-103 if the simpler
"just stop writing `on`" test fails.

### Be honest about what this does *not* buy
An allowlist keyed on the executable is a **usability and visibility** win. It is not a security
boundary, for one specific and unavoidable reason: several allowlisted programs will happily run
arbitrary code for you. Chrome's `--gpu-launcher='sh -c "…"'` is the textbook case — the moment
Chrome is on the allowlist, anything that can spawn Chrome with a flag is effectively on the
allowlist too. This is a classic confused deputy and no amount of path checking in userspace fixes
it. Anyone reading this later: do not oversell the allowlist.

It is also worth stating plainly that the current gate has the same ceiling. Anything running as
`shawn` can type `dgpu-exec-v2`. The gate stops **accidental** access — apps that probe every GPU
they can see — not a determined one.

### The version that *is* a boundary — BPF-LSM (later, deliberately)
Verified on this machine, today, that the kernel supports it:

```
/sys/kernel/security/lsm          = capability,landlock,lockdown,yama,bpf
CONFIG_BPF_LSM=y  CONFIG_BPF_SYSCALL=y  CONFIG_DEBUG_INFO_BTF=y  CONFIG_DEBUG_INFO_BTF_MODULES=y
/sys/kernel/btf/vmlinux           present, 6.4 MB
clang                             /usr/bin/clang
kernel                            7.0.5-arch1-1
MISSING: bpftool, bpftrace        (pacman package `bpf`)
```

A `BPF_PROG(file_open)` hook that checks the opening task's executable inode against a pinned BPF map
decides **at the kernel**, on the real process, regardless of how it got there. That is qualitatively
different from the setgid door in three ways:

- It sees the process that is *actually opening the device*. Chrome's GPU process is `chrome`; a
  `--gpu-launcher`'d `sh` is `sh` and gets denied. The confused deputy above closes.
- It removes the fragile part of DECISION 25. Today the whole gate rests on
  `NVreg_DeviceFileMode=0660`, needed only because setuid-root `nvidia-modprobe` resets the nodes to
  `0666` on every wake. With an LSM deciding, the nodes can go back to `0666`, the `dgpu` group and
  the modprobe param can both be retired, and a driver update can no longer quietly reopen the gate.
- It can log every denial with the exact binary, for free.

Cost: install `bpf`, write a CO-RE program, and a systemd unit to load and pin it. Real work, and a
real dependency on kernel internals that Arch will churn. Worth doing when the gate needs to be a
boundary; not worth doing to make Chrome's picker pleasant.

### Rejected: polkit
`pkexec` and `pkaction` are present and polkit could front the "may this app use the GPU" prompt.
Rejected because the only identity involved is `shawn`, so the prompt reduces to Shawn approving
Shawn — it adds a password dialog and no decision the user wasn't already making in `kdialog`.
Landlock is present too but only ever **self-restricts** a process; it cannot grant, so it is
irrelevant here.

### Recommended order
1. **Logging first, on its own.** Cheapest possible change to `dgpu-exec-v2` and it retires the
   condition that produced BUG-102. Also finally answers "what is holding my dGPU awake", which is
   the question that started all of this.
2. ~~Fix BUG-103 (test "stop writing `on`" first; fall back to fork-and-release).~~
   **DONE 2026-08-05 — and it removes a requirement from this design.** "Stop writing `on`" was
   tested and passed: with `control=auto` the driver takes a runtime-PM reference on device open, so
   the card wakes on demand and re-suspends itself ~20 s after the last fd closes. **So `dgpu-exec-v3`
   does NOT need to fork-and-wait in order to release the card** — the kernel already does it.
   Fork-and-wait is now justified only by *logging* (a "released at HH:MM:SS after Ns" line) and by
   nothing else; if that isn't worth a resident supervisor process per launch, keep `exec`.
3. Promote v2 over v1 everywhere, then the policy file + `ask` dialog.
   **Partly done 2026-08-05** — `luminos-gpu-launch` now calls `dgpu-exec-v2`, so the universal
   picker is covered. Still on v1 or ungated: **`luminos-wine-launcher`, which never called the gate
   at all** (bare `exec wine`, so Wine-on-NVIDIA is denied exactly as Chrome was in BUG-102), plus
   any `.desktop` entry or script invoking `dgpu-exec` directly.
4. BPF-LSM, if and when the gate needs to be a boundary rather than a filter.

## DECISION 55 — The jobhunt agent runs on the Claude Code **subscription** via `claude-cli`, not on an API key and not on the local 12B
# [CHANGE: claude-code | 2026-08-06]

**Status:** decided and proven up to the login step. Config written, not yet switched on —
the flip is one line and is blocked on Shawn re-authenticating `claude` (see below).

### The problem
The local model cannot host OpenClaw's agent loop. Two independent, measured blockers:
1. **Context.** Gemma 4 12B only loads at `ctx 8192` on the 6 GB card (16384 and 24576 both
   fail to allocate). OpenClaw's system prompt plus tool schemas tokenize to **19929** on an
   empty session — before you type anything. Note OpenClaw's own preflight estimate says
   9456, **less than half the truth**; trust the server's 400, not the estimate.
2. **Tool calls.** Gemma emits a non-JSON tool-call format. `toolcall-proxy.py`'s regex is
   Qwen-specific (`<tool_call>{...}</tool_call>`), so tools silently never fire — which
   presents as a stupid model and is actually a parsing gap.

Qwen3-4B parses correctly and fits 24576, but 24576 is still barely above the 19929 floor,
which leaves almost nothing for the actual conversation.

### The decision
Use **`claude-cli`** as the agent runtime. OpenClaw's bundled Anthropic plugin shells out to
the installed `claude` binary, so the **existing Claude Code subscription** drives the agent
and there is no per-token bill and no API key to store.

### Why not the alternatives
- **An Anthropic API key** — works, but it is a second bill for something already paid for.
  Kept documented in `scripts/jobhunt/openclaw-cloud.json5` as the option to use if the agent
  ever needs to run unattended with no Claude Code login present.
- **Gemini CLI (free)** — **dead as of 2026-08-06, not fixable locally.**
  `~/.gemini/oauth_creds.json` is still a valid login, but Google rejects the *client*:
  `IneligibleTierError` / `UNSUPPORTED_CLIENT`, "no longer supported for Gemini Code Assist
  for individuals". A Google **AI Studio** API key is a different product and still works —
  that stays as the free-tier fallback.
- **The local model** — stays configured as a fallback. PLAN.md's design rule is that the
  pipeline must remain usable with no cloud dependency, and that rule is not being relaxed;
  it just cannot be the *agent* driver.

### Correcting an earlier wrong call, on the record
A previous session concluded `claude-cli` was impossible because
`openclaw config patch` rejected `api: "claude-cli"`. **The rejection was real; the
conclusion was wrong.** `claude-cli` is not a provider *api* — it is an **agent runtime**,
selected by a `claude-cli/<model>` model ref or by `agentRuntime: { id: "claude-cli" }` on a
model. Right value, wrong field. The lesson: a schema rejection tells you a value is invalid
*there*, not that the capability is absent.

### Tools do work on this path
The docs frame CLI backends as a "text-only fallback", which undersells it. The gateway
stands up a **loopback MCP bridge** and hands Claude Code the OpenClaw toolset. Verified in
the gateway log: `mcp-loopback ... toolCount: 22`, and the child is launched with
`--allowedTools mcp__openclaw__*`. Claude Code also brings its own Bash/WebFetch tools,
mapped onto OpenClaw's exec policy.

### Two prerequisites, both hit for real
1. **Claude Code >= 2.1.206.** OpenClaw waits for the `msg_lifecycle_v1` capability in
   Claude's `system/init` record. On the installed 2.1.152 the turn did **not** error — it
   **hung** until a watchdog killed it after ~163 s, which reads like a network problem and
   is not one. Upgraded 2.1.152 -> 2.1.223.
   **npm here blocks postinstall scripts**, and the upgrade left a stub whose
   `claude --version` answered `Error: claude native binary not installed`. Repair:
   `node ~/.npm-global/lib/node_modules/@anthropic-ai/claude-code/install.cjs`.
   Rollback if ever needed: `npm install -g @anthropic-ai/claude-code@2.1.152`.
2. **A live login in `~/.claude/.credentials.json`** — **this is the open blocker.** The
   stored token expired **2026-05-27** and was never refreshed, because Shawn uses the
   desktop app and Cowork rather than the npm CLI. The turn now fails cleanly and honestly:
   `FailoverError: OAuth access token has expired. Re-authenticate to continue.`
   **Only Shawn can fix this** — run `claude` in a terminal and `/login`.
   An inherited `CLAUDE_CODE_OAUTH_TOKEN` in some other shell does **not** count: the gateway
   logs `cli env auth: host=none child=none`, so the child reads that file and nothing else.
   This is why `claude -p` can succeed from one shell while OpenClaw fails.

### How to switch it on, after logging in
```bash
openclaw config set agents.defaults.model.primary claude-cli/claude-sonnet-4-6
systemctl --user restart openclaw-gateway
openclaw agent --agent main --message "hi" --model claude-cli/claude-sonnet-4-6
```
Use `claude-cli/claude-haiku-4-5-20251001` instead if the loop turns out to be chatty enough
that Sonnet is wasteful — the job is tool calling and JSON, not prose.

---

## DECISION 56 — The jobhunt pipeline filters with regexes before it thinks, and the model reports facts rather than verdicts
**Date: 2026-08-06** · Supersedes nothing · Implements PLAN.md Phase 2

Shawn's brief was three things: *"i want to just look on progress"*, *"may in future add or
remove type of jobs that i am targeting for"*, and *"make sure to use cheapest model for bulk
applying"*. Three architectural choices follow from those, and each has a cheaper-looking
alternative that is wrong.

### 1. The cheapest model is not calling a model
Measured on the live database of 9,788 postings:

| approach | tokens read by an LLM |
|---|---|
| score every posting | ~18,220,000 |
| rule-filter first, then score survivors | ~367,000 |

**50x less work for the same answer.** Location eligibility, remote-or-not, and title
seniority are exact string questions; a language model adds nothing but latency and heat.
The free pass runs the whole database in **0.95 seconds** and cuts 9,788 to 192 distinct
roles. Only those reach the GPU.

Bulk scoring therefore runs on **Qwen3-4B locally**, not on any paid API — no key, no
per-token bill, no postings leaving the laptop. A cloud model is reserved for Phase 3, where
there are a handful of calls and the output is a document a human sends.

### 2. `targets.yaml` is the only file Shawn edits
Everything tunable lives in one commented YAML file: location buckets, the remote
requirement, exclude/include title lanes, seniority patterns, and the scoring knobs. Editing
it and running `score.py --rules-only` re-filters the entire database in about a second, for
free, as many times as he likes. The include lanes are kept as **separate regexes rather than
one fused pattern** specifically so the funnel report can name which lane admitted each job —
a fused regex would be marginally faster and would tell him nothing about why his shortlist
looks the way it does.

`status.py --rejects` samples what each rule threw away. An unaudited filter quietly stops
working, and this is the habit that catches it.

### 3. The model reads; Python judges
The first implementation asked the model for a 0-100 `fit`. Four of the first five jobs came
back at exactly **40** (BUG-109). Its prose was correct every time; it simply anchored on the
floor of a rubric band.

The schema now asks only for things a reader can extract — `years_required`,
`degree_required`, `hard_blocker`, `missing_skills`, and a coarse `fit_signal` enum — and
`compute_score()` does the arithmetic. Three consequences:

- **Scores spread.** 15 jobs produced nine distinct values across 20-88.
- **Contradictions become correctable.** One posting returned `fit_signal: strong` while
  listing 13 required technologies the candidate lacks. A reading now overrides a judgement.
- **Re-tuning is free.** `score.py --recompute` re-ranks the whole pool from stored answers
  in ~1 second. Raising `max_years_experience` as Shawn gains experience costs nothing;
  under the old design it meant another 25-minute GPU pass.

The output is grammar-constrained (`response_format.schema` -> GBNF), so malformed JSON is
not unlikely, it is unreachable. PLAN.md requires this and it is not an optimisation: "reply
with JSON only" is a request, and over 200 jobs a 4B model will decline it a few times.

### 4. The model service is on-demand, and that is a power decision
`jobhunt-llm.service` is installed but **deliberately not enabled**. `score.py` starts it,
uses it, and stops it — because an idle llama server pins ~4.6 GB of VRAM and holds the dGPU
out of runtime suspend indefinitely, which is precisely BUG-103. `status.py` reports
`inactive` for that unit **in green**, with the note "idle (correct — GPU asleep)", so the
correct state does not read as a fault.

`jobhunt-pipeline.timer` (03:30 daily) carries `Persistent=true`. On a laptop that is the
load-bearing line: without it, a machine asleep at 03:30 silently skips the run and Shawn
finds stale data with nothing in the log to explain it.

### What this does NOT decide
Scores remain **provisional** until `profile.yaml` exists. Today the model compares postings
against a placeholder ("recent CS/IT grad, 0-2 years, Python/Linux/SQL/Git"), and `score.py`
prints that caveat on every run rather than presenting invented rankings as final. The
resume is still the critical path for Phases 3-5.

---

## DECISION 57 — Screen-edge hover panels do not get to sit on top of window titlebars
# [CHANGE: claude-code | 2026-08-06]

**Context.** Caelestia's drawers are one full-screen layer surface per monitor, above every
window, and each panel opens when the pointer touches the screen edge it lives on. That is the
shell's signature interaction. It is also, structurally, a click sink: while a panel is open,
every pixel it covers belongs to the shell and not to the window underneath.

Under DECISION 50 every window is tiled at `y=20`. Its titlebar — buttons and the double-click
strip both — is therefore always directly beneath the top edge panel. BUG-110 is the result:
Claude Desktop's window controls appeared completely dead for days, and the actual cause was
that the dashboard had dropped over them. Nothing was wrong with the app, the compositor, or
Wayland.

**Decision.** An edge-hover panel is allowed only on an edge where nothing clickable lives.

- **Top edge — hover OFF.** `dashboard.showOnHover = false`. Titlebars own the top edge.
  Reached by `SUPER+B` (`caelestia:dashboard`), or `SUPER+K` for all panels at once.
- **Bottom edge — hover stays ON.** `launcher.showOnHover = true`. Windows put nothing
  clickable at their bottom edge, so there is no competition.
- **Right edge — hover stays OFF** (Caelestia's own default for `sidebar.showOnHover`). Close
  buttons live in the top-right corner; this must not be turned on.

**Why not the alternatives.** Narrowing the trigger band, or adding a delay, only makes the
collision rarer — and a control that works nine times in ten is worse than one that never
works, because you stop trusting it. Moving windows down to clear the panel gives up screen
height permanently to a panel that is usually not there. Turning the drawers off entirely
throws away the shell.

**The rule to apply going forward:** before enabling any `showOnHover`, ask what a *window*
puts at that edge. If the answer is anything the user clicks, the answer is no.

**Corollary — do not ship a button the compositor cannot honour.** Hyprland has no minimize.
An app's minimize button will always be dead, and no configuration fixes it. This is why
DECISION 50 removed hyprbars' three buttons rather than wiring them up: `SUPER+H` /
`SUPER+SHIFT+H` (`luminos-win min|restore`) is honest about what the system can actually do.

---

## DECISION 58 — The 4.6 GB VRAM budget governs background models; a foreground model gets the whole card
# [CHANGE: claude-code | 2026-08-07]

**Context.** "4.6 GB Safe VRAM (6 GB Total)" has been repeated in ~35 files since the project
started, and it has been read as a hardware limit. It is not. The RTX 4050 has 6,141 MiB and
will happily allocate all of it. The 4.6 GB figure was a *policy* number protecting against a
specific failure: a model server left **resident** pins its VRAM indefinitely, which starves the
compositor and — worse — holds the dGPU out of runtime suspend forever (the same class of
problem as BUG-103, and the reason `jobhunt-llm.service` is start-use-stop rather than a
long-running daemon).

That reasoning applies to a model nobody is looking at. It does not apply to a model the user
deliberately launched and is sitting in front of.

**Decision.** Split the rule by lifecycle rather than by number.

- **Background / resident / timer-driven** (HIVE swap targets, `jobhunt-llm.service`, anything a
  systemd unit starts): **4.6 GB cap stands, unchanged.** These must also still exit when idle.
- **Foreground / interactive / user-launched** (a big model run by hand for a session):
  **the full 6,141 MiB is available.** The desktop is allowed to give up headroom for something
  the user is actively using, because the user can see it and can close it.

**Measured, 2026-08-07** — `gemma-4-12b-it-qat-q4_0` at `n_gpu_layers=32`, ctx 4096, q8_0 KV:
**5,652 MiB of 6,141 used**, 677 tok/s prompt eval, 9.56 tok/s generation, no compositor stutter,
dGPU returned to `suspended` cleanly after exit. 33 layers fails with
`Failed to create llama_context` — that, not 4.6 GB, is the real ceiling.

**What this does NOT license.** Two models at once still does not fit and never will; the
one-model-at-a-time rule is untouched. And the exception is void the moment the process becomes
long-lived — if a foreground session is going to idle, it exits instead.

**Why this matters now.** The Gemma 4 26B A4B MoE plan depends on it: the non-expert tensors plus
the KV cache come to ~1.3 GB and want to sit on the card alongside as many attention layers as
fit. Sizing that split against 4.6 GB instead of 6.1 GB would throw away 1.5 GB for no reason.
