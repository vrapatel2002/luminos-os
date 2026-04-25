## HIVE Architecture Audit

### Models Used
- **Nexus**: `dolphin3:8b` (or `llama3.1:8b`). Coordinator for general chat, routing, and web search results. Served via GPU.
- **Bolt**: `qwen2.5-coder:7b`. Expert coder for complex programming tasks and debugging. Served via GPU.
- **Nova**: `deepseek-r1:7b`. Deep reasoning and planning specialist. Served via CPU permanently to avoid VRAM overhead.
- **Eye**: `llava:7b`. Vision specialist for image analysis. Served via GPU.
- **Embeddings**: `nomic-embed-text`. Used for vector generation in the memory system.

**Serving Method:** Ollama is used exclusively. In the Windows environment, it ran as two separate processes (Server 1 on GPU, Server 2 on CPU) to handle the 6GB VRAM constraint.
**Loading Strategy:** 
- **GPU (Server 1):** Only one 7B-8B model is loaded at a time. Switching takes approximately 10-15 seconds.
- **CPU (Server 2):** Nova is kept loaded permanently on CPU to provide reasoning without blocking the GPU for faster chat/code tasks.

### Orchestrator Logic
- **Regex Routing:** The `Brain` coordinator uses regex tags `[ROUTE:MODEL]` and `[REQUEST:MODEL]` injected into LLM outputs.
- **Manual Routing:** Supports prefix commands like `!route terminal` for direct execution.
- **Terminal Intent:** A `detect_terminal_intent` method identifies commands like `pip install` or `git status` automatically.
- **Handoffs:** When swapping models, the orchestrator injects a "SYSTEM HANDOFF" note containing the task description and recent conversation summary to maintain context.
- **Stickiness:** The `Router` defaults to the current model for follow-up questions to minimize unnecessary VRAM swaps.

### VRAM Management
- **Hardware:** ASUS ROG G14 with RTX 4050 (6GB VRAM) and 16GB RAM.
- **Swapping:** `VRAMManager` unloads models by calling `/api/generate` with `keep_alive: "0"`, then loads the target model.
- **Budgeting:** 
  - Nova (CPU): ~4.7GB RAM.
  - Nexus/Bolt/Eye (GPU): ~4.6GB VRAM + ~1GB RAM.
  - Total RAM usage: ~11-12GB (leaving ~4GB for OS/Apps).
- **Docker Usage:** Docker was used to host Open WebUI, SearXNG, and n8n, consuming an additional 1-2GB RAM.

### Tools Available
- **terminal:** Executes whitelisted commands (`pip`, `git`, `python`, `mkdir`, etc.) with user confirmation and risk assessment. Blacklists dangerous patterns like `rm -rf` and `sudo`.
- **file_tools:** Sandboxed `file_read` and `file_write` restricted to specific project directories with path traversal protection.
- **ocr:** Tesseract-based text extraction from images or screenshots.
- **pdf_ingest:** Complex pipeline that extracts text, renders pages as images for vision/OCR analysis, chunks text with overlap, generates embeddings, and stores them in RAG.
- **screenshot:** Pillow-based full-screen or region-specific capture.

### Memory System
- **SQLite + WAL:** Persistent storage in `hive.db` using WAL mode for concurrency.
- **RAG Architecture:** 
  - **Chunks:** Split document text for semantic search.
  - **Memories:** User preferences, facts from conversations, and high-importance "instincts".
- **Retrieval:** Uses `nomic-embed-text` for cosine similarity search. It prioritizes "instincts" (importance > 0.9) by injecting them into every prompt.

### What Changes for Luminos
- **Ollama → llama.cpp:** Transition from Ollama to `llama.cpp` for direct GPU management and better control over VRAM eviction.
- **Docker Removal:** All services (SearXNG, etc.) should run natively or as lightweight Go/Python daemons to save the 2GB Docker overhead.
- **Go Daemon Integration:** The orchestrator must move from a Python `Brain` class to a Go service (`luminos-ai`) communicating with Python inference services via Unix sockets.
- **VRAM Budget for RTX 4050:**
  - Mandatory swapping for GPU models.
  - Use the AMD NPU (XDNA) for the Router/Sentinel models to free up CPU/GPU cycles.
  - Keep reasoning (Nova) on CPU if VRAM is tight, or use aggressive 4-bit quantization.

### Migration Priority
1. **Core Orchestrator (Go):** Implement the `[ROUTE:...]` logic in Go.
2. **Memory System (Go/SQLite):** Port the RAG retrieval logic to Go.
3. **Tools (Go/Python):** Port `terminal` and `file_tools` to Go (for safety); keep `ocr` and `pdf_ingest` in Python.
4. **VRAM Manager (Go):** Implement the swapping logic in the Go `luminos-ai` daemon.

### Recommended Phase 4 Build Order
1. **Socket Interface:** Establish the Unix socket protocol between `luminos-ai` (Go) and `llama-server` (Python).
2. **Basic Routing:** Implement Nexus-based routing for chat vs. code.
3. **VRAM Eviction:** Implement the logic to unload LLMs when "Gaming Mode" is detected.
4. **Tool Integration:** Connect the Go terminal/file tools to the AI routing logic.
5. **Memory Port:** Move the SQLite memory retrieval to the Go layer.

Agent: gemini-cli
Task: HIVE architecture audit
## Corrected Memory Architecture (April 2026)

### Loading Strategy: On-Demand GPU Only
IDLE: dGPU off, NPU=Sentinel, iGPU=desktop, RAM=OS only
AI MODE: dGPU loads one model on demand (~4.6GB VRAM)
NOVA MODE: explicit user request only → CPU/RAM load
GAMING: dGPU fully evicted, HIVE suspended

### TurboQuant Integration (Planned)
Google TurboQuant (ICLR 2026) compresses KV cache 6x.
Use --ctk q8_0 --ctv turbo4 flags in llama.cpp when stable.
Benefit: longer conversations before VRAM exhausted.
Status: llama.cpp implementation in review, add when merged.

### Models — No Docker, No Ollama
All models as GGUF via llama.cpp direct.
No Docker. No Ollama. No separate server processes.
Each model loaded on demand, evicted when not needed.
