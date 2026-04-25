# FOCUS.md — Management Chat Attention Guide
# FOR MANAGEMENT CHAT (Claude) ONLY
# Last Updated: 2026-03-04

---

## WHAT THIS PROJECT IS
HIVE — locally running multi-model AI system. 4 specialist 7B models coordinated
by an orchestrator. Fully local, free forever. Training them on BEHAVIOR not KNOWLEDGE.
Vision: structured cognition via specialization + external memory + tools.
Full vision in handoff doc. Do not re-read vision every session — it's settled.

---

## CURRENT PHASE
PHASE 1 — DATASET CREATION
Do not think about training, deployment, or orchestrator changes yet.
100% focus on getting all 12 JSONL files generated, audited, and locked.

---

## CURRENT ATTENTION
🔥 IMMEDIATE: nexus_web_grounding.jsonl (250 examples)
   - Mega-prompt already written (in handoff Section 10)
   - File exists, is empty, ready for generation
   - Use fresh Chat B as generation factory
   - After generation: audit with Gemini High before locking
   - This is the most complex Nexus file — do not skip audit

---

## WHAT IS DONE — DO NOT REVISIT
- HIVE v1.1 orchestrator — works, deployed in Open WebUI
- Docker setup — all services running
- n8n workflows — timetable + job hunter complete
- Web browsing — SearXNG + trafilatura working
- Tag schema — LOCKED, do not discuss or modify
- Architecture decisions — settled, listed in handoff Section 9
- nexus_routing.jsonl — LOCKED ✅
- nexus_web_decision.jsonl — LOCKED ✅
- Routing boundary rule: concept→NEXUS, perform→NOVA/BOLT

---

## UPCOMING (in order — do not jump ahead)
1. nexus_web_grounding.jsonl — generate + audit + lock
2. nova_reasoning.jsonl (200) — need to write mega-prompt
3. nova_bookmarks.jsonl (150)
4. nova_calculator.jsonl (100)
5. nova_planning.jsonl (50)
6. nova_honesty.jsonl (50)
7. bolt_error_parsing.jsonl (150)
8. bolt_iterative.jsonl (100)
9. bolt_code_gen.jsonl (100)
10. bolt_planning.jsonl (50)
11. PHASE 2: Lambda training
12. PHASE 3: Merge + deploy
13. PHASE 4: Orchestrator update (delete band-aids, add tag parser, ChromaDB, calc, relay)
14. PHASE 5: End-to-end testing

---

## QUEUED FEATURES / MID-PROJECT ADDITIONS
(things to remember but not do yet)
- ChromaDB bookmark RAG — Phase 4, not now
- Scratchpad for Nova — deferred, add only if models lose track in 10+ step problems
- File RAG — Phase 4 orchestrator code, not model training
- Telegram monitor — exists in codebase, not active yet

---

## ARCHITECTURE DECISIONS (settled — do not re-discuss)
- Nexus: router + chat + web (NO bookmark RAG)
- Nova: ONE reasoner for ALL domains
- Bolt: code + debug, uses [SAVE]+[RECALL] not [CALC]
- Eye: vision only, no training planned
- Relay pattern: Bolt finds WHAT → Nova reasons WHY → Bolt implements
- Calculator: Python eval with math library, safety-checked, Nova only
- 7B Q4_K_M ceiling: strong undergrad, NOT graduate/PhD

---

## KNOWN ISSUES / WATCH OUT FOR
- hive_orchestrator.py on disk is OUTDATED — live version is in Open WebUI
- Docker image needs re-commit (pending housekeeping)
- ddgs package must NEVER be removed from open-webui container
- Nexus web grounding: main failure modes are rounding numbers and wrong date selection

---

## HOW THIS PROJECT OPERATES
- Chat A (this chat) = manager, prompt writer, reviewer
- Chat B (fresh instances) = generation factory, one mega-prompt per file
- IDE Agents (Antigravity) = audits, file ops, code changes
- Claude Code = local execution only
- Vratik = boss, moves data between chats, final decisions
- Dataset workflow: generate → audit → fix → re-audit → lock → next file

---

## WHEN TO UPDATE THIS FILE
- When a dataset file gets locked (update CURRENT ATTENTION + WHAT IS DONE)
- When a new feature is queued mid-project (add to QUEUED FEATURES)
- When an architecture decision changes (update ARCHITECTURE DECISIONS)
- When moving to a new phase
