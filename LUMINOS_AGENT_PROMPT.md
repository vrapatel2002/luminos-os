# LUMINOS OS — AGENT STARTING PROMPT
# Copy and paste this ENTIRE block at the start of every Claude Code or Antigravity session.
# Do not skip any part of it.

---

## PASTE THIS AT THE START OF EVERY SESSION:

```
You are working on Luminos OS. Before writing a single line of code, do the following:

1. Read LUMINOS_PROJECT_SCOPE.md fully
2. Read LUMINOS_DECISIONS.md fully
3. Confirm you understand both by summarizing the current task in the context of the scope

Rules you must never break:
- Base OS is Arch Linux. Never write apt, snap, or Ubuntu-specific code.
- Use pacman and AUR only. Helper: yay or paru.
- supergfxctl must always be set to Hybrid. Never change this.
- Never expose GPU mode switching to the user.
- Never add more than two power modes (battery and performance).
- Compatibility router runs on CPU only — never GPU or NPU.
- AI is infrastructure. Never make it a visible product or feature.
- Fix bugs listed in ACTIVE BUGS section before adding anything new.
- If a decision is not covered in LUMINOS_PROJECT_SCOPE.md — stop and ask Sam.
- When in doubt: simpler is always better.

Current task: [REPLACE THIS WITH YOUR ACTUAL TASK]
```

---

## SESSION TYPES — USE THE RIGHT ONE

### For Bug Fixes
```
You are working on Luminos OS.
Read LUMINOS_PROJECT_SCOPE.md and LUMINOS_DECISIONS.md first.

Today's task is a bug fix:
Bug: [DESCRIBE THE BUG]
Where it happens: [FILE OR COMPONENT]
Expected behavior: [WHAT SHOULD HAPPEN]
Actual behavior: [WHAT IS HAPPENING]

Fix only this bug. Do not refactor anything else.
Do not add new features while fixing.
After fixing, update the ACTIVE BUGS section in LUMINOS_PROJECT_SCOPE.md.
```

### For New Features
```
You are working on Luminos OS.
Read LUMINOS_PROJECT_SCOPE.md and LUMINOS_DECISIONS.md first.

Today's task is building: [FEATURE NAME]
This feature is listed in the scope document under: [SECTION NAME]

Before writing code:
1. Confirm ACTIVE BUGS list is empty or that Sam approved skipping it
2. State how this feature fits the scope
3. State which hardware it uses (CPU/NPU/GPU)
4. State whether the user ever sees or touches this feature directly

Then build it.
```

### For Cleanup / Migration Sessions
```
You are working on Luminos OS.
Read LUMINOS_PROJECT_SCOPE.md and LUMINOS_DECISIONS.md first.

Today's task is cleanup. You are migrating from Ubuntu base to Arch Linux base.

Rules for this session:
- Remove all Ubuntu/Debian specific code (apt, casper, dpkg, snap references)
- Replace with Arch equivalents (pacman, AUR, systemd units)
- Do not change any feature logic — only the package management and system calls
- Flag anything you cannot cleanly migrate — do not guess
- After each file cleaned, note what changed
```

---

## QUICK REFERENCE (For Agents)

```
Base OS:        Arch Linux
Compositor:     Hyprland  
Login:          greetd (custom theme)
Packages:       pacman + AUR (yay/paru)
GPU:            supergfxctl Hybrid (LOCKED, never change)
Fan/Power:      asusctl
AI Runtime:     llama.cpp via Unix socket
Security:       Sentinel on NPU (SmolLM2-360M)
Router model:   Sub 1GB quantized, runs on CPU
Power modes:    2 only — battery (auto) and performance (auto)
```
