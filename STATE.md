# STATE.md — HIVE Project Current State
# FOR AI AGENTS ONLY — updated after every change
# Last Updated: 2026-03-06

---

## PROJECT
Name: HIVE — Multi-model local AI orchestrator
Root: C:\Users\vrati\VSCODE\New folder\LLMS\
Phase: PHASE 1 — Dataset Creation (in progress)

---

## FOLDER STRUCTURE
```
LLMS/
├── main.py                        # Entry point, wires everything, starts server
├── hive_orchestrator.py           # LIVE orchestrator v1.1 (32KB) — DO NOT TOUCH
├── config.yaml                    # Main config (8.7KB)
├── requirements.txt               # Dependencies
├── start_hive.bat                 # Startup script
├── .env                           # Credentials — DO NOT TOUCH
├── searxng_settings.yml           # SearXNG config — DO NOT TOUCH
├── HIVE_ARCHITECTURE.md           # Architecture reference
├── HIVE_README.md                 # Project readme
├── docs/
│   └── MASTER_PLAN.md             # Master plan tracker
├── agents/
│   ├── base.py                    # Base agent class
│   ├── chat.py                    # Chat agent (Nexus)
│   ├── coder.py                   # Coder agent (Bolt)
│   ├── planner.py                 # Planner agent (Nova)
│   └── vision.py                  # Vision agent (Eye)
├── orchestrator/
│   ├── brain.py                   # Core orchestrator logic (22KB) — CRITICAL
│   ├── ollama_client.py           # Ollama API client
│   ├── router.py                  # Routing logic
│   └── vram_manager.py            # VRAM management
├── memory/
│   ├── db.py                      # Database operations (16KB)
│   ├── embeddings.py              # Embedding generation
│   ├── retriever.py               # RAG retrieval
│   └── schema.sql                 # DB schema
├── proxy/
│   ├── server.py                  # Proxy server (12KB)
│   ├── middleware.py              # Middleware
│   └── openai_compat.py           # OpenAI compatibility layer
├── tools/
│   ├── file_tools.py              # File operations
│   ├── terminal.py                # Terminal tool (6KB)
│   ├── pdf_ingest.py              # PDF ingestion (15KB)
│   ├── ocr.py                     # OCR tool
│   └── screenshot.py              # Screenshot tool
├── telegram/
│   ├── bot.py                     # Telegram bot
│   └── monitor.py                 # Monitor
├── modelfiles/
│   ├── Nexus.modelfile            # Nexus model config (13KB)
│   ├── Nova.modelfile             # Nova model config
│   ├── Bolt.modelfile             # Bolt model config
│   └── Eye.modelfile              # Eye model config
├── training/
│   └── export_data.py             # Training data export script
├── training_dataset/              # ALL TRAINING DATA LIVES HERE
│   ├── nexus_routing.jsonl        # LOCKED ✅ (100 examples, 33KB)
│   ├── nexus_web_decision.jsonl   # LOCKED ✅ (150 examples, 123KB)
│   └── nexus_web_grounding.jsonl  # IN PROGRESS 🔥 (250 target, 237KB current)
└── data/
    └── hive.db                    # SQLite database — DO NOT TOUCH
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
| Model | Base         | Port  | Role                    |
|-------|-------------|-------|-------------------------|
| Nexus | dolphin3:8b  | 11434 | Router + chat + web     |
| Nova  | deepseek-r1:7b | 11435 | Deep reasoning, math  |
| Bolt  | qwen2.5-coder:7b | 11434 | Coding + debugging   |
| Eye   | llava:7b     | 11434 | Vision                  |

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
| nova_bookmarks.jsonl        | 150    | ⬜ NOT STARTED      |
| nova_calculator.jsonl       | 100    | ⬜ NOT STARTED      |
| nova_planning.jsonl         | 50     | ⬜ NOT STARTED      |
| nova_honesty.jsonl          | 50     | ⬜ NOT STARTED      |
| bolt_error_parsing.jsonl    | 150    | ⬜ NOT STARTED      |
| bolt_iterative.jsonl        | 100    | ⬜ NOT STARTED      |
| bolt_code_gen.jsonl         | 100    | ⬜ NOT STARTED      |
| bolt_planning.jsonl         | 50     | ⬜ NOT STARTED      |

---

## CRITICAL DO-NOT-TOUCH FILES
- hive_orchestrator.py — live orchestrator, only edit via Open WebUI
- .env — credentials
- data/hive.db — database
- searxng_settings.yml — SearXNG config
- Any LOCKED training_dataset files

---

## PENDING HOUSEKEEPING
- Docker image re-commit pending: `docker commit open-webui open-webui-custom:latest`
- hive_orchestrator.py on disk is OUTDATED — live version is in Open WebUI
