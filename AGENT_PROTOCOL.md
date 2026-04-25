# AGENT_PROTOCOL.md — Rules for All Agents
# FOR AI AGENTS ONLY — read before every task
# Last Updated: 2026-03-04

---

## BEFORE YOU START ANY TASK
1. Read STATE.md — know what exists and what's locked
2. Read your task prompt carefully
3. If anything contradicts STATE.md — STOP and report, do not proceed

---

## ABSOLUTE DO-NOTS (never touch these under any circumstance)
- hive_orchestrator.py — live orchestrator, changes only via Open WebUI
- .env — credentials file
- data/hive.db, data/hive.db-shm, data/hive.db-wal — database files
- searxng_settings.yml — SearXNG config
- Any training_dataset file marked LOCKED ✅ in STATE.md
- TAG SCHEMA — never modify [SAVE], [RECALL], [CALC] format

---

## SCOPE RULES
- Only touch files explicitly listed in your task prompt
- If you need to touch an unlisted file — STOP and report, do not proceed
- Never refactor, "improve", or reorganize code you weren't asked to touch
- Never add features that weren't requested
- Never change architecture decisions

---

## AFTER EVERY TASK — MANDATORY
1. Update STATE.md:
   - Change status of any file you created/modified/locked
   - Update folder structure if files were added or removed
   - Update any service or model status if changed
2. Delete all temp files, scripts, and output files you created during the task
3. List exactly what you changed and what you deleted in your reply

---

## CLEANUP RULE
After completing the task, delete any temporary files, scripts, or output files
you created during this task. The folder should contain ONLY the files that
existed before + any files explicitly requested. List what you deleted.

---

## REPLY FORMAT (always end your output with this)
```
📨 REPLY TO MANAGEMENT:
  - Task completed: [yes/no/partial]
  - What changed: [list files modified/created]
  - STATE.md updated: [yes/no — what was changed]
  - Issues encountered: [any problems]
  - Temp files deleted: [list]
  - Ready for: [what comes next]
```

---

## TRAINING DATA RULES (only relevant when working on training_dataset/)
- Never modify a LOCKED file
- Each example must be valid JSON on a single line
- Append new batches — never overwrite existing content
- Report exact line count after any additions

---

## IF SOMETHING IS UNCLEAR
Do not guess. Do not assume. Stop and report what is unclear in the REPLY section.
Better to ask than to break something.
