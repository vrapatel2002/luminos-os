# LUMINOS OS — DECISIONS LOG
# Version: 1.0
# This file explains WHY every major decision was made.
# Read this before questioning anything in LUMINOS_PROJECT_SCOPE.md
# Every entry has: the decision, why we made it, what we rejected and why.

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
