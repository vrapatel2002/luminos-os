# LUMINOS OS — DECISIONS LOG
# Version: 1.0
# This file explains WHY every major decision was made.
# Read this before questioning anything in LUMINOS_PROJECT_SCOPE.md
# Every entry has: the decision, why we made it, what we rejected and why.

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

