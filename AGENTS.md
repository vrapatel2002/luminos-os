# STRICT POST-EXECUTION RULE
Before concluding ANY task, you MUST update `luminos-notes.sh` to reflect all file changes, deleted directories, and architectural shifts. You must also verify that `LUMINOS_STATUS.md` matches the current reality. Do not output a final report until these state files are synchronized.

# AGENTS.md — Luminos OS Agent Constitution
# Last Updated: 2026-04-26 (Global Sync + Cleanup)

---

## 1. What Is Luminos OS?

Luminos OS is a custom Arch Linux distribution on ASUS ROG G14.
- **UI**: KDE Plasma (Wayland) + Qt/QML custom widgets.
- **Control**: Go-based daemon stack (`luminos-ai`).
- **AI Core**: Native `MobileLLM` on XDNA NPU (HATS architecture).
- **HIVE**: Bare-metal Linux multi-agent cluster (Dolphin, Qwen, DeepSeek).

**BANNED**: Hyprland, GTK4, HyprPanel, Python UI, Docker, Ollama.

---

## 2. Mandatory Rules

- **Minimal Changes**: Do not touch working OS components.
- **Identity Tags**: Add `[CHANGE: agent | date]` to every modified block.
- **VRAM Watchdog**: Respect the 4.6GB safe limit. HIVE models swap on dGPU.
- **State Tracking**: Update `LUMINOS_STATUS.md` and `luminos-notes.sh` every turn.

---

## 3. Agent Strengths

| Agent | Use for |
|-------|---------|
| Claude | Planning, C++, QML architecture |
| Gemini CLI | Terminal automation, HIVE routing, state maintenance |
| Antigravity | Visual Qt/QML implementation |

## 3.1 Local DeepSeek Routing (Advanced)
For complex reasoning tasks where local inference is preferred over Claude API:
```bash
ANTHROPIC_BASE_URL=http://localhost:8080/v1 claude
```
This routes Claude Code sessions through llama-server (port 8080 = active HIVE model).
**Only use when hive-daemon has loaded Nova (DeepSeek R1).** Default sessions use Claude API normally.

---

## 4. Bare-Metal Architecture Rules

- **OS Core**: `MobileLLM-R1-140M` runs on the NPU via HATS. It is a native OS system driver, completely separate from HIVE.
- **HIVE Cluster**: Bare-metal Linux. Uses `llama.cpp` directly managed by Go daemons. **NO DOCKER. NO OLLAMA.**
- **Routing**: Dolphin 3.0 / Nexus (GPU) is the front-end. Routes to Qwen2.5-Coder-7B / Bolt (GPU), DeepSeek-R1-0528 / Nova (CPU), Qwen-VL / Eye (GPU, pending).
- **Orchestration**: `scripts/hive-daemon.py` on port 8078. Owns model lifecycle, routing, inference. Started by popup launcher. `hive-swap-server.py` (8079) is RETIRED.
- **VRAM Constraint**: 6GB Total, 4.6GB Safe. Only ONE GPU model loads at a time. VRAM manager handles eviction (`SIGUSR1` to llama-server).

---

## 5. Absolute Do-Nots

- `.env` — credentials file, never touch
- `data/hive.db` — database files, never touch
- `TAG SCHEMA` — never modify [SAVE], [RECALL], [CALC] format
- Native Go daemons (`cmd/`) unless specifically instructed

---

## 6. Mandatory Update Protocol (Every Task)

After EVERY task, ALL agents must:

### 6.1 Update Luminos Notes:
```bash
~/luminos-os/scripts/luminos-notes.sh add [TAG] "[Detailed summary of changes]"
```

### 6.2 Update relevant .md files:
- `LUMINOS_STATUS.md` → if any component status changed
- `LUMINOS_DECISIONS.md` → if any architectural decision was made
- `docs/BUGS.md` → if a bug was found or fixed
- `docs/CODE_REFERENCE.md` → if new files were added or removed

### 6.3 Commit format (mandatory):
```bash
git add -A
git commit -m "type(scope): description

Agent: [claude-code|gemini-cli|antigravity]
Task: [what was asked]"
git push origin main
```

NEVER complete a task without updating Luminos Notes.
NEVER complete a task without updating relevant docs.
NEVER commit without the Agent and Task fields.

---

## 7. Reply Format (always end output with):
```
REPLY TO MANAGEMENT:
  - Task completed: [yes/no/partial]
  - What changed: [list files modified/created]
  - LUMINOS_STATUS.md updated: [yes/no]
  - Luminos Notes updated: [yes/no]
  - Ready for: [what comes next]
```

Rule: Luminos Notes Usage (mandatory)
BEFORE every task:
  ~/luminos-os/scripts/luminos-notes.sh search "<task topic>"
  This searches existing project knowledge.
  Never start a task without checking Luminos Notes first.

AFTER every task:
  ~/luminos-os/scripts/luminos-notes.sh add [TAG] "[Summary of changes]"
  This indexes new changes into Luminos Notes.
  Never complete a task without updating Luminos Notes.

Rule: Doc Updates (mandatory)
After EVERY task check these and update if relevant:
  LUMINOS_STATUS.md — component status changes
  LUMINOS_DECISIONS.md — any architectural decisions
  docs/BUGS.md — bugs found or fixed
  docs/CODE_REFERENCE.md — new files added
