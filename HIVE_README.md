# 🐝 HIVE — Complete Documentation

> **H**eterogeneous **I**ntelligent **V**irtual **E**ngine  
> A 100% local multi-AI agent system running on a single laptop.  
> Created by **Vratik Patel** — B.Sc Computer Science, Algoma University (2021–2025)  
> 📧 vratik.patel2002@gmail.com

---

## Table of Contents

1. [What is HIVE](#1-what-is-hive)
2. [The Team](#2-the-team)
3. [Architecture](#3-architecture)
4. [Prerequisites](#4-prerequisites)
5. [How to Start HIVE](#5-how-to-start-hive)
6. [How to Stop HIVE](#6-how-to-stop-hive)
7. [File Locations](#7-file-locations)
8. [Dual Server Setup](#8-dual-server-setup)
9. [Open WebUI Configuration](#9-open-webui-configuration)
10. [How to Rebuild Models](#10-how-to-rebuild-models)
11. [How to Edit the Orchestrator](#11-how-to-edit-the-orchestrator)
12. [Image Handling](#12-image-handling)
13. [IDE Agent Usage Guide](#13-ide-agent-usage-guide)
14. [Troubleshooting](#14-troubleshooting)
15. [Quick Reference Commands](#15-quick-reference-commands)
16. [Project History](#16-project-history)

---

## 1. What is HIVE

HIVE is a **100% local** AI system that runs **four specialized language models** as a coordinated team on a single laptop. No cloud. No API keys. No subscriptions. Everything runs offline using [Ollama](https://ollama.com) for model serving, [Open WebUI](https://github.com/open-webui/open-webui) for the chat interface, and a custom Python orchestrator that routes messages to the right model.

**The core idea:** Instead of one general-purpose AI, HIVE uses a *team* of specialists — a coordinator, a coder, a deep thinker, and a vision model — that know about each other and can suggest handoffs. The orchestrator (`hive_orchestrator.py`) runs inside Open WebUI as a Function and handles all routing, image detection, and model coordination automatically.

---

## 2. The Team

| Model | Name | Role | Base Model | Server | Port |
|-------|------|------|------------|--------|------|
| 🧠 | **Nexus** | Coordinator — handles ~80% of messages. General conversation, simple math, simple code explanations, routing decisions. | `llama3.1:8b` | Server 1 (GPU) | 11434 |
| ⚡ | **Bolt** | Expert coder — complex algorithms, full applications, debugging, computational math. | `qwen2.5-coder:7b` | Server 1 (GPU) | 11434 |
| 💭 | **Nova** | Deep thinker — multi-step reasoning, theoretical math, strategic analysis, new topic research. Shows thinking process with 💭 bubbles. | `deepseek-r1:7b` | Server 2 (CPU) | 11435 |
| 👁️ | **Eye** | Vision specialist — image description, visual analysis, text in images. | `llava:7b` | Server 1 (GPU) | 11434 |

### Personalities

- **Nexus** knows when to handle something vs. when to suggest a teammate. If a coding question is complex enough, Nexus will suggest Bolt. If reasoning is deep enough, Nexus will suggest Nova.
- **Bolt** writes complete, runnable code with comments and complexity analysis. Suggests Nova for architectural thinking.
- **Nova** shows step-by-step reasoning. The `deepseek-r1` model outputs `<think>` blocks, which the orchestrator converts to collapsible 💭 displays. Suggests Bolt for implementation.
- **Eye** is the only model that can see images. Describes what it sees with precision and suggests teammates for follow-up work.

All four models know they are part of HIVE and were built by Vratik.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                           │
│                    http://localhost:3000                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Open WebUI  │  (Docker, port 3000)
                    │              │
                    │  HIVE Orch.  │  ← hive_orchestrator.py
                    │  (Function)  │     runs INSIDE Open WebUI
                    └──┬───────┬──┘
                       │       │
          ┌────────────▼─┐   ┌─▼────────────┐
          │  Server 1    │   │  Server 2     │
          │  GPU (11434) │   │  CPU (11435)  │
          │              │   │               │
          │  Nexus  ┐    │   │  Nova         │
          │  Bolt   ├ 1  │   │  (permanent)  │
          │  Eye    ┘    │   │               │
          │  (swap ~15s) │   │  num_thread:10│
          └──────────────┘   └───────────────┘

          ┌──────────────┐
          │  n8n         │  (Docker, port 5678)
          │  Automation  │  Job timetable workflows
          └──────────────┘
```

**Key points:**
- Server 1 runs on GPU but can only load **one model at a time**. Swapping takes ~15 seconds.
- Server 2 runs on CPU with `CUDA_VISIBLE_DEVICES=-1`. Nova stays loaded permanently.
- The orchestrator runs as an Open WebUI Function — it's Python code pasted into the admin panel.
- Open WebUI connects to both Ollama servers via `host.docker.internal`.

---

## 4. Prerequisites

| Component | Purpose | Install |
|-----------|---------|---------|
| **Ollama** | Serves AI models locally | [ollama.com/download](https://ollama.com/download) |
| **Docker Desktop** | Runs Open WebUI and n8n containers | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| **Open WebUI** | Chat interface (runs in Docker) | See [Docker containers](#docker-containers) below |
| **n8n** | Workflow automation (runs in Docker) | See [Docker containers](#docker-containers) below |

### Hardware (Current Setup)

| Component | Spec |
|-----------|------|
| CPU | AMD Ryzen 7 8845HS — 8 cores / 16 threads, Zen 4 |
| GPU | NVIDIA RTX 4050 Laptop — **6 GB VRAM** |
| RAM | 16 GB total |
| NPU | AMD XDNA 16 TOPS (Ollama can't use it yet) |

### Memory Budget

| Component | RAM Usage |
|-----------|-----------|
| Nova (CPU, 10 threads) | ~4.7 GB |
| Nexus (GPU) | ~1 GB RAM + ~4.6 GB VRAM |
| Docker (Open WebUI + n8n) | ~1–2 GB |
| Windows OS | ~4 GB |
| **Free headroom** | **~3–5 GB** |

---

## 5. How to Start HIVE

### Quick Start (Normal Use)

```
1.  Open Docker Desktop → wait for "Engine running"
2.  Double-click start_hive.bat
3.  In any terminal:
      docker start open-webui
      docker start n8n
4.  Open browser → http://localhost:3000 (select "HIVE" model)
5.  Automation → http://localhost:5678
```

### What `start_hive.bat` Does

1. Kills any existing Ollama processes
2. Starts **Server 1** (GPU, port 11434) with `OLLAMA_KEEP_ALIVE=-1` and `OLLAMA_MAX_LOADED_MODELS=1`
3. Waits 8 seconds
4. Starts **Server 2** (CPU, port 11435) with `CUDA_VISIBLE_DEVICES=-1`
5. Waits 8 seconds
6. Pre-loads Nexus on Server 1 and Nova on Server 2
7. Prints "HIVE IS LIVE"

**Important:** The two server windows that open must stay open. The startup window can be closed after it finishes.

### Docker Containers

If the containers don't exist yet, create them:

```powershell
# Open WebUI (first time only)
docker run -d -p 3000:8080 --name open-webui --add-host=host.docker.internal:host-gateway -v open-webui:/app/backend/data --restart always ghcr.io/open-webui/open-webui:main

# n8n (first time only)
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n
```

After initial creation, just use `docker start open-webui` and `docker start n8n`.

---

## 6. How to Stop HIVE

```powershell
# Stop Docker containers
docker stop open-webui
docker stop n8n

# Close the two Ollama server windows (HIVE-GPU-11434 and HIVE-CPU-11435)
# Or kill all Ollama processes:
taskkill /F /IM ollama.exe
```

---

## 7. File Locations

```
LLMS/
├── start_hive.bat              # Dual-server startup script
├── hive_orchestrator.py        # Orchestrator code (local copy for editing)
├── HIVE_README.md              # This file
├── config.yaml                 # All system configuration
├── requirements.txt            # Python dependencies
├── main.py                     # Entry point (FastAPI proxy server)
├── .env                        # Secrets (Telegram tokens, etc.)
├── .gitignore
├── __init__.py
│
├── modelfiles/                 # Ollama model definitions
│   ├── Nexus.modelfile         # llama3.1:8b + coordinator personality
│   ├── Bolt.modelfile          # qwen2.5-coder:7b + coder personality
│   ├── Nova.modelfile          # deepseek-r1:7b + thinker personality (CPU-only params)
│   └── Eye.modelfile           # llava:7b + vision personality
│
├── orchestrator/               # Brain logic
│   ├── brain.py                # Main loop: plan → route → respond → remember
│   ├── router.py               # Which model for which task
│   ├── ollama_client.py        # Unified Ollama HTTP client
│   └── vram_manager.py         # Model loading/unloading strategy
│
├── agents/                     # Model agent classes
│   ├── base.py                 # OllamaAgent base class
│   ├── chat.py                 # Nexus (Llama 3.1) agent
│   ├── coder.py                # Bolt (Qwen 2.5) agent
│   ├── planner.py              # Nova (DeepSeek-R1) agent
│   └── vision.py               # Eye (LLaVA) agent
│
├── memory/                     # Persistent memory system
│   ├── schema.sql              # SQLite table definitions
│   ├── db.py                   # Database CRUD operations
│   ├── embeddings.py           # nomic-embed-text vector operations
│   └── retriever.py            # Global-first search + ranking
│
├── tools/                      # Plugin tools
│   ├── base.py                 # Tool base class
│   ├── terminal.py             # Safe terminal execution
│   ├── file_tools.py           # Sandboxed file read/write
│   ├── ocr.py                  # Tesseract OCR
│   ├── screenshot.py           # Screen capture
│   └── pdf_ingest.py           # PDF processing pipeline
│
├── proxy/                      # API layer
│   ├── server.py               # FastAPI + OpenAI-compatible endpoints
│   ├── openai_compat.py        # Request/response format translation
│   └── middleware.py           # Memory injection, routing, logging
│
├── telegram/                   # Monitoring
│   ├── bot.py                  # Start/stop/crash notifications
│   └── monitor.py              # Watchdog heartbeat
│
├── training/                   # Future fine-tuning
│   ├── export_data.py          # Export conversations for training
│   └── README.md               # Training instructions
│
├── data/                       # Data storage
│   └── hive.db                 # SQLite database (auto-created)
│
└── logs/                       # Runtime logs
    └── hive.log                # Application log
```

---

## 8. Dual Server Setup

HIVE runs **two separate Ollama instances** to maximize the laptop's resources.

### Server 1 — GPU (Port 11434)

- Runs Nexus, Bolt, and Eye — **one at a time**
- Uses the RTX 4050 (6 GB VRAM)
- Swapping between models takes ~15 seconds
- Startup command:

```powershell
$env:OLLAMA_HOST = "0.0.0.0:11434"
ollama serve
```

### Server 2 — CPU (Port 11435)

- Runs **Nova permanently** — never unloaded
- Uses CPU only (`CUDA_VISIBLE_DEVICES=-1`)
- 10 threads allocated (`num_thread 10` in Nova's modelfile)
- Nova is slower (30–90 seconds per response) — this is normal
- Startup command:

```powershell
$env:OLLAMA_HOST = "0.0.0.0:11435"
$env:CUDA_VISIBLE_DEVICES = "-1"
ollama serve
```

### Why Two Servers?

With only 6 GB VRAM, only one 7B model fits on GPU at a time. Nova (deepseek-r1) works well on CPU and benefits from long uninterrupted thinking time — so it gets its own dedicated CPU server while the GPU server handles the faster conversational models.

---

## 9. Open WebUI Configuration

Open WebUI is the chat interface. Configuration is done through the admin panel at `http://localhost:3000`.

### Ollama Connections

Go to **Admin → Settings → Connections → Ollama API** and add both servers:

| Connection | URL |
|------------|-----|
| Connection 1 | `http://host.docker.internal:11434` |
| Connection 2 | `http://host.docker.internal:11435` |

> **Note:** Use `host.docker.internal` (not `localhost`) because Open WebUI runs inside Docker.

### HIVE Orchestrator Function

Go to **Admin → Functions** → Create/edit the **HIVE Orchestrator** function:

1. Open `hive_orchestrator.py` from the project folder
2. Copy the entire file contents
3. Paste into the Function code editor in Open WebUI
4. Save

> **Important:** The code running in Open WebUI is the **LIVE version**. The local `hive_orchestrator.py` file is just for editing in your IDE. After making changes locally, you must paste the updated code into Open WebUI.

---

## 10. How to Rebuild Models

If you modify a modelfile, you need to rebuild the model on the correct server.

### Server 1 Models (Nexus, Bolt, Eye)

```powershell
$env:OLLAMA_HOST = "localhost:11434"
ollama create nexus -f modelfiles/Nexus.modelfile
ollama create bolt -f modelfiles/Bolt.modelfile
ollama create eye -f modelfiles/Eye.modelfile
```

### Server 2 Models (Nova)

```powershell
$env:OLLAMA_HOST = "localhost:11435"
ollama create nova -f modelfiles/Nova.modelfile
```

### Modelfile Reference

| File | Base Model | Key Parameters |
|------|-----------|----------------|
| `Nexus.modelfile` | `llama3.1:8b` | `num_ctx 2048` |
| `Bolt.modelfile` | `qwen2.5-coder:7b` | `num_ctx 2048` |
| `Nova.modelfile` | `deepseek-r1:7b` | `temperature 0.6`, `num_thread 10`, `num_predict 2048`, `num_ctx 2048`, `num_gpu 0` |
| `Eye.modelfile` | `llava:7b` | `num_ctx 2048`, `temperature 0.5` |

---

## 11. How to Edit the Orchestrator

The orchestrator (`hive_orchestrator.py`) is the brain of HIVE. It runs **inside Open WebUI** as a Function.

### Editing Workflow

```
1.  Open hive_orchestrator.py in your IDE (VS Code, etc.)
2.  Make changes and save locally
3.  Open http://localhost:3000 → Admin → Functions
4.  Open the HIVE Orchestrator function
5.  Select all → Paste the updated code
6.  Save
7.  Changes take effect immediately (no restart needed)
```

### What the Orchestrator Does

- **Routing:** Detects the user's intent and routes to the right model (Nexus, Bolt, Nova, or Eye)
- **Image detection:** Detects image attachments and routes to Eye automatically
- **Nova thinking:** Parses `<think>` blocks from deepseek-r1 and converts them to collapsible 💭 displays
- **Model swapping:** Handles GPU model loading/unloading on Server 1
- **Error handling:** Eye is forced to non-streaming for cleaner error handling

---

## 12. Image Handling

### How It Works

1. User sends an image in Open WebUI
2. Open WebUI stores the file on disk with a UUID filename
3. The orchestrator detects image content in the message
4. It uses `Files.get_file_by_id()` to read the file directly from disk
5. The image is sent to Eye (llava:7b) for analysis

### Key Technical Details

```python
# Critical import — reads files from Open WebUI's storage
from open_webui.models.files import Files

# File storage path inside the Docker container
/app/backend/data/uploads/{uuid}_{filename}.ext
```

> **⚠️ NEVER use HTTP self-fetch** (e.g., requesting `localhost:3000/api/files/...` from within the orchestrator). This causes a **deadlock** because Open WebUI is single-threaded — the request would wait for itself to respond. Always use `Files.get_file_by_id()` for direct disk access.

---

## 13. IDE Agent Usage Guide

When using IDE agents (like Antigravity/Gemini/Claude) to edit HIVE code:

### Agent Rankings

| Agent | Strength | Token Usage |
|-------|----------|-------------|
| 🟠 **Opus 4.6** | Best coder | LEAST tokens ← **primary choice** |
| 🔷 **Gemini 3 Pro** | Good coder | Medium tokens |
| 🟢 **GPT o3s 120B** | Decent | MOST tokens |

### Rules for IDE Agents

1. **ALWAYS include a DO NOT block** in your prompts — list files and behaviors the agent must not touch
2. **ALWAYS have agents create `task.md` first** before making changes
3. **After editing locally, PASTE into Open WebUI** → Admin → Functions (for orchestrator changes)
4. **Never let agents modify:**
   - `hive_orchestrator.py` code logic (unless specifically asked)
   - Modelfile content
   - `start_hive.bat`
   - Any working code without explicit instruction

### DO NOT Block Template

```
## DO NOT:
- Modify hive_orchestrator.py code
- Modify any modelfile content
- Modify start_hive.bat
- Delete the modelfiles folder
- Change any working code
- Make assumptions about file contents — READ them first
```

---

## 14. Troubleshooting

### Check if Servers Are Running

```powershell
# Check Server 1 (GPU) — should list available models
curl http://localhost:11434/api/tags

# Check Server 2 (CPU) — should list available models
curl http://localhost:11435/api/tags
```

### Check Which Models Are Loaded

```powershell
# Server 1 — shows currently loaded model (Nexus, Bolt, or Eye)
curl http://localhost:11434/api/ps

# Server 2 — should always show Nova
curl http://localhost:11435/api/ps
```

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| Eye returns 400 error | UUID sent instead of base64 image data | Uncomment debug lines in `hive_orchestrator.py` to inspect payload |
| Nova is slow (30–90 sec) | Normal — runs on CPU | This is expected behavior, not a bug |
| GPU swap takes ~15 sec | Normal — loading/unloading 7B models | Expected when switching between Nexus/Bolt/Eye |
| Open WebUI can't connect | Docker not running or wrong URL | Check Docker Desktop is running; use `host.docker.internal` not `localhost` |
| Models not found | Models not created on correct server | Rebuild models using correct `$env:OLLAMA_HOST` (see [Section 10](#10-how-to-rebuild-models)) |
| n8n container missing | Never created | Run the `docker run` command from [Section 5](#docker-containers) |

---

## 15. Quick Reference Commands

### Startup

```powershell
# Full startup sequence
# 1. Open Docker Desktop
# 2. Double-click start_hive.bat
# 3. Then:
docker start open-webui
docker start n8n
```

### Server Management

```powershell
# Start Server 1 (GPU) manually
$env:OLLAMA_HOST = "0.0.0.0:11434"; ollama serve

# Start Server 2 (CPU) manually
$env:OLLAMA_HOST = "0.0.0.0:11435"; $env:CUDA_VISIBLE_DEVICES = "-1"; ollama serve

# Check servers
curl http://localhost:11434/api/tags
curl http://localhost:11435/api/tags

# Check loaded models
curl http://localhost:11434/api/ps
curl http://localhost:11435/api/ps
```

### Model Management

```powershell
# Rebuild all models (Server 1)
$env:OLLAMA_HOST = "localhost:11434"
ollama create nexus -f modelfiles/Nexus.modelfile
ollama create bolt -f modelfiles/Bolt.modelfile
ollama create eye -f modelfiles/Eye.modelfile

# Rebuild Nova (Server 2)
$env:OLLAMA_HOST = "localhost:11435"
ollama create nova -f modelfiles/Nova.modelfile
```

### Docker

```powershell
# Start/stop containers
docker start open-webui && docker start n8n
docker stop open-webui && docker stop n8n

# View logs
docker logs open-webui --tail 50
docker logs n8n --tail 50

# Create containers (first time only)
docker run -d -p 3000:8080 --name open-webui --add-host=host.docker.internal:host-gateway -v open-webui:/app/backend/data --restart always ghcr.io/open-webui/open-webui:main
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n
```

### URLs

| Service | URL |
|---------|-----|
| Open WebUI (Chat) | http://localhost:3000 |
| n8n (Automation) | http://localhost:5678 |
| Ollama Server 1 (GPU) | http://localhost:11434 |
| Ollama Server 2 (CPU) | http://localhost:11435 |

---

## 16. Project History

### Development Sessions

| Session | What Was Done |
|---------|---------------|
| **Session 13** | Dual Ollama servers + `start_hive.bat` + Open WebUI integration + basic routing |
| **Session 14** | Image detection + model personalities (modelfiles) + Nova thinking (💭 display) |
| **Session 15** | Eye image fix (direct file read via `Files.get_file_by_id()`) + HIVE feature-complete |
| **Session 16** | n8n job timetable automation (in progress) |

### Build History (Detailed)

| Date | Task | Agent Used |
|------|------|------------|
| 2026-02-14 | Project setup, config, DB, Ollama client, VRAM manager | Gemini |
| 2026-02-14 | Embeddings, memory retriever, brain, router | Opus 4.5 |
| 2026-02-14 | Agent classes, tool system, PDF pipeline | Gemini + Opus 4.5 |
| 2026-02-14 | FastAPI proxy, Telegram monitor, main entry point | Gemini |
| 2026-02-15 | Bug fixes, terminal tool, aider setup, environment guards | Gemini |
| 2026-02-16 | Brain-terminal connection, secrets migration, smart coordinator | Gemini |
| 2026-02-16 | HIVE model migration (Nexus/Bolt/Nova/Eye identities) | Gemini |
| 2026-02-16 | HIVE rebranding (sambot → hive naming) | Gemini |
| 2026-02-17 | Environment setup verification, dependency hardening | Gemini |
| 2026-02-19 | Debug logging disabled, documentation + cleanup | Opus 4.6 |

### Creator

**Vratik Patel**  
📧 vratik.patel2002@gmail.com  
🎓 B.Sc Computer Science — Algoma University (2021–2025)

---

*Last updated: 2026-02-19*
