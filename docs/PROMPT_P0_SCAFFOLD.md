# PROMPT — P0: Project Scaffold
# Agent: Gemini 3.1 Pro (Low) or Firebase Studio Agent
# Task: Create full folder structure + base files
# Copy everything below the line and paste into your IDE agent

---

🔷 GEMINI LOW — P0 SCAFFOLD TASK

📨 AGENT MESSAGE (from Management):
- Context: Project Luminos has no code yet. Only docs exist.
- Goal: Create the full project folder structure and base files so we can start building.
- Watch out: Do NOT install anything that needs a running Linux system. We're on Windows dev machine. Just create files and folders.

Read AGENT_PROTOCOL.md first.
Read docs/MASTER_PLAN.md, specifically Phase 0 steps.

TASK: Create full Luminos project scaffold in C:\Users\vrati\VSCODE\Luminos\

DO NOT:
- Install system packages (we're on Windows)
- Create any AI model files (models/ folder just needs to exist, empty)
- Write any actual AI/ML code yet
- Modify AGENT_PROTOCOL.md or any docs/ files
- Create anything outside the Luminos folder

ONLY:
1. Create folder structure: src/daemon/ src/classifier/ src/sentinel/ src/zone1/ src/zone2/ src/zone3/ src/gpu_manager/ src/power_manager/ models/ config/ tests/
2. Create src/daemon/main.py — skeleton only (no logic yet):
   - Comment header explaining what this file will become
   - Empty main() function
   - if __name__ == "__main__" block
3. Create config/luminos.conf with these sections (comment-only skeleton):
   [daemon]     — socket path, log level
   [models]     — paths to classifier.onnx and sentinel.onnx
   [hardware]   — npu_enabled, igpu_enabled, nvidia_enabled
   [zones]      — zone1_threshold, zone2_threshold
   [power]      — default profile
4. Create requirements.txt with these packages:
   llama-cpp-python
   onnxruntime
   amd-quark
   psutil
   pytest
5. Create a .gitignore with: models/*.onnx, models/*.gguf, __pycache__, *.pyc, .env, config/luminos.conf.local

📨 BEFORE FINISHING:
Update docs/MASTER_PLAN.md:
- Mark P0-01 as complete ✅
- Add to Communication Log: date, "Agent", "Scaffold created — folder structure + base files"

Update docs/STATE.md:
- Update "WHAT EXISTS RIGHT NOW" to show folder structure exists
- Update "WHAT'S NEXT" to P0-02 (requirements.txt done in this task) → next is P0-06 verify installs

Update docs/CODE_REFERENCE.md:
- Change src/daemon/main.py from [NOT BUILT] to [EXISTS — skeleton]
- Change config/luminos.conf from [NOT BUILT] to [EXISTS — skeleton]

📨 REPLY TO MANAGEMENT (end of output):
- Step completed: [what you did]
- Result: [success / partial / failed]
- Files changed: [list]
- Docs updated: [list]
- Issues found: [any or "none"]
- Ready for: [next step]
