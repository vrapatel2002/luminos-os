# STATE.md — HIVE Project Current State
# FOR AI AGENTS ONLY — updated after every change
# Last Updated: 2026-04-25 (Fixes applied)

---

## PROJECT
Name: HIVE — Multi-model local AI orchestrator
Root: /home/shawn/luminos-os/
Phase: PHASE 1 — Dataset Creation (in progress)
UX: macOS visual transformation applied ✅

---

## FOLDER STRUCTURE
```
luminos-os/
├── hive_orchestrator.py           # LIVE orchestrator v1.1 (32KB) — DO NOT TOUCH
├── config.yaml                    # Main config
├── requirements.txt               # Dependencies
├── AGENT_PROTOCOL.md              # Rules for agents
├── FOCUS.md                       # Focus areas
├── HIVE_ARCHITECTURE.md           # Architecture reference
├── HIVE_README.md                 # Project readme
├── LUMINOS_STATUS.md              # Luminos OS status
├── STATE.md                       # THIS FILE
├── agents/                        # Agent implementations
│   ├── base.py
│   ├── chat.py
│   ├── coder.py
│   ├── planner.py
│   └── vision.py
├── config/                        # System configurations (NEW)
│   ├── starship.toml              # macOS style prompt config
│   ├── zshrc                      # ZSH configuration
│   └── hyprland/                  # Hyprland configs
├── docs/                          # Documentation
├── memory/                        # Database and RAG memory
├── modelfiles/                    # Ollama model files
├── orchestrator/                  # Core orchestrator logic
├── src/                           # Source code (various modules)
├── tools/                         # Tool implementations
└── training_dataset/              # ALL TRAINING DATA LIVES HERE
```

---

## SERVICES (Docker)
| Service    | Port | Status  | Notes                          |
|------------|------|---------|--------------------------------|
| Open WebUI | 3000 | RUNNING | hosts live orchestrator        |
| SearXNG    | 8888 | RUNNING | self-hosted search             |
| n8n        | 5678 | RUNNING | workflow automation            |
| Ollama GPU | 11434 | RUNNING | Nexus, Bolt, Eye              |
| Ollama CPU | 11435 | RUNNING | Nova                          |

---

## MODELS
| Model | Base         | Port  | Role                    | Status              |
|-------|-------------|-------|-------------------------|---------------------|
| Nexus | llama3.1:8b | 11434 | Router + chat + web     | ✅ Available (4.6GB) |
| Nova  | deepseek-r1:7b | 11435 | Deep reasoning, math  | ✅ Available (4.4GB) |
| Bolt  | qwen2.5-coder:7b | 11434 | Coding + debugging   | ✅ Available (4.4GB) |
| Eye   | llava:7b     | 11434 | Vision                  | 📋 Not Started      |
| Embed | nomic-embed | CPU   | Embeddings              | ✅ Available (81MB) |

---

## TAG SCHEMA (LOCKED — DO NOT MODIFY)
```
[SAVE: TOPIC-NN | description]    — bookmark result
[RECALL: ID or search phrase]     — retrieve bookmark
[CALC: python expression]         — compute arithmetic
[RESULT: value]                   — injected after [CALC]
[BOOKMARK FOUND: ID | content]    — injected after [RECALL]
[BOOKMARK NOT FOUND: message]     — injected after [RECALL]

ID FORMAT: 2-8 uppercase letters + dash + 2 digits (e.g., IBP-01)
Nova: uses all 3 tags
Bolt: uses [SAVE] + [RECALL] only
Nexus: uses none — uses WEB_SEARCH/WEB_NONE instead
```

---

## TRAINING DATASET STATUS
| File                        | Target | Status              |
|-----------------------------|--------|---------------------|
| nexus_routing.jsonl         | 100    | ✅ LOCKED (audited) |
| nexus_web_decision.jsonl    | 150    | ✅ LOCKED (audited) |
| nexus_web_grounding.jsonl   | 250    | 🔥 IN PROGRESS      |
| nova_reasoning.jsonl        | 200    | ⬜ NOT STARTED      |
...
```
