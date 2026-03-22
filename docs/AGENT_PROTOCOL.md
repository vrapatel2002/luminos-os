# AGENT_PROTOCOL.md
# Project Luminos — Agent Behavior Rules
Last Updated: 2026-03-21
Version: 1.0

---

## WHO READS THIS

Every IDE agent (Gemini, Claude Code, GPT) reads this before starting any task.
This is NOT optional. If you skip this, you will make mistakes.

---

## WHAT YOU ARE BUILDING

Project Luminos is an AI-native, security-first Linux OS built on Ubuntu LTS.

Core components:
- **Three-Zone Execution Model**: Native Linux (Zone 1) → Wine/Proton (Zone 2) → Firecracker microVM (Zone 3)
- **AI Classifier**: Runs on AMD XDNA NPU via ONNX Runtime VitisAI — routes every binary to the correct zone automatically
- **Sentinel**: Lightweight security model — also on NPU, always-on, ~200MB ONNX
- **luminos-ai.service**: systemd daemon — no Ollama, no REST API, direct llama.cpp via Unix socket at `/run/luminos/ai.sock`
- **GPU Split**: NPU = OS AI always-on | iGPU = display | NVIDIA 6GB = gaming + HIVE models

This is a real OS project. Not a prototype. Not a demo.

---

## MANDATORY RULES — NO EXCEPTIONS

### 1. SCOPE LOCK
Only touch files explicitly listed in the prompt's ONLY section.
DO NOT touch anything else. Do not "improve" unrelated code.
Do not refactor files you weren't asked to touch.
Do not add features nobody asked for.

### 2. DOC UPDATES ARE MANDATORY
After EVERY task you complete, you MUST update:
- `docs/MASTER_PLAN.md` → mark the step complete, add one-line result
- `docs/STATE.md` → update current state snapshot
- Any relevant reference doc if architecture changed

If you changed code → also update `docs/CODE_REFERENCE.md`
If you changed a config → also update `docs/CONFIGURATION.md`
If you added/deleted files → also update `docs/CODE_REFERENCE.md`

Failing to update docs = task incomplete.

### 3. REPLY FORMAT
Every response MUST end with this exact block:

```
📨 REPLY TO MANAGEMENT:
- Step completed: [what you did in one line]
- Result: [success / partial / failed]
- Files changed: [list every file you touched]
- Docs updated: [list every doc you updated]
- Issues found: [anything unexpected, or "none"]
- Ready for: [what the logical next step is]
```

### 4. DO NOT GUESS
If the prompt is ambiguous, say so in your reply. Do not invent requirements.
Do not assume what the user "probably" wants. Ask for clarification via the REPLY block.

### 5. VERIFY YOUR OWN WORK
Before finishing, check:
- Does the code actually run without errors?
- Did the file save correctly?
- Does it match what the prompt asked for?
- Did you update all required docs?

### 6. NO UNSOLICITED OPINIONS
Do not add comments like "I also noticed you could improve X."
Do not suggest architecture changes unless explicitly asked.
Do not warn about decisions already made in the Master Plan.

---

## SOURCE OF TRUTH HIERARCHY

When in doubt about any decision:

```
1. This AGENT_PROTOCOL.md        ← agent behavior rules
2. docs/MASTER_PLAN.md           ← what's done, what's next
3. docs/STATE.md                 ← current state of the project
4. docs/CODE_REFERENCE.md        ← file map and architecture
5. ProjectLuminos_MasterPlan_v1_0 (planning doc)
6. ProjectLuminos_VolumeII (AI integration planning doc)
```

Higher number = less authoritative. If MASTER_PLAN.md says a decision was made, that overrides the original planning docs.

---

## PROJECT FOLDER STRUCTURE

```
C:\Users\vrati\VSCODE\Luminos\
├── AGENT_PROTOCOL.md          ← YOU ARE HERE
├── docs/
│   ├── MASTER_PLAN.md         ← progress tracker
│   ├── STATE.md               ← current snapshot for handoffs
│   ├── HANDOFF.md             ← paste this at new chat start
│   ├── CODE_REFERENCE.md      ← file map / architecture
│   └── CONFIGURATION.md       ← config values and settings
├── src/
│   ├── classifier/            ← binary zone classifier (NPU)
│   ├── sentinel/              ← security model (NPU)
│   ├── daemon/                ← luminos-ai.service
│   ├── zone1/                 ← native Linux integration
│   ├── zone2/                 ← Wine/Proton integration
│   ├── zone3/                 ← Firecracker microVM integration
│   ├── gpu_manager/           ← dynamic VRAM/layer management
│   └── power_manager/         ← AI-driven power profiles
├── models/
│   ├── classifier.onnx        ← zone classifier (NPU)
│   └── sentinel.onnx          ← security model (NPU)
├── config/
│   └── luminos.conf           ← main config file
└── tests/
    └── ...
```

---

## COMMON MISTAKES — DO NOT MAKE THESE

| Mistake | Why It Happens | Prevention |
|--------|----------------|------------|
| Touching files not in scope | Agent tries to "help" | Read ONLY section carefully |
| Forgetting doc updates | Agent considers task done when code works | Doc update is part of the task |
| Using Ollama | Old habit | Luminos uses direct llama.cpp — no Ollama |
| REST API calls for AI inference | Old habit | Use Unix socket `/run/luminos/ai.sock` |
| Guessing zone routing logic | Classifier not built yet | Check STATE.md for what exists |
| Building for CUDA only | Nvidia habit | Remember: NPU = ONNX/VitisAI, iGPU = Vulkan, NVIDIA = CUDA |

---

END OF AGENT_PROTOCOL.md
