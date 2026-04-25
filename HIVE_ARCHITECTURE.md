# HIVE Architecture

## 1. Directory Structure

The HIVE project is structured around a central orchestrator, specialized agents, and supporting tools. The root directory `C:\Users\vrati\VSCODE\New folder\LLMS\` contains the following key components:

```
LLMS/
├── agents/             # Agent definitions
│   ├── base.py
│   ├── chat.py
│   ├── coder.py
│   ├── planner.py
│   └── vision.py
├── data/               # Persistent storage (e.g., databases, uploads)
├── docs/               # Documentation (e.g., MASTER_PLAN.md)
├── memory/             # Implementation of memory structures
├── modelfiles/         # Ollama Modelfile configurations
│   ├── Bolt.modelfile
│   ├── Eye.modelfile
│   ├── Nexus.modelfile
│   └── Nova.modelfile
├── orchestrator/       # Core backend orchestration logic
│   ├── brain.py
│   ├── ollama_client.py
│   ├── router.py
│   └── vram_manager.py
├── proxy/              # Interception and compatibility layers
│   ├── middleware.py
│   ├── openai_compat.py
│   └── server.py
├── telegram/           # Telegram bot integration
├── tools/              # Actionable capabilities for agents
│   ├── file_tools.py
│   ├── ocr.py
│   ├── pdf_ingest.py
│   ├── screenshot.py
│   └── terminal.py
├── training/           # Scripts for model tuning/training
├── config.yaml         # Central configuration
├── hive_orchestrator.py # The Open WebUI Pipeline Function
├── main.py             # Main entry point for standalone backend
└── start_hive.bat      # Windows boot script for dual Ollama servers
```

## 2. Boot Sequence

When `start_hive.bat` is executed, the following sequence occurs to prepare the environment:

1. **Cleanup:** It aggressively kills any existing `ollama.exe` processes to ensure a clean slate.
2. **Server 1 (GPU):** Starts an Ollama instance on port `11434` bound to `0.0.0.0`. It configures `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_NUM_PARALLEL=1` to dedicate GPU resources.
3. **Server 2 (CPU):** Starts a secondary Ollama instance on port `11435` bound to `0.0.0.0`. It forces CPU usage via `CUDA_VISIBLE_DEVICES=-1` and sets the same parallel constraints.
4. **Pre-loading:**
   - It warms up Server 1 by triggering a silent run of the **Nexus** model (llama3.1:8b).
   - It warms up Server 2 by triggering a silent run of the **Nova** model (deepseek-r1:7b).
5. **Ready:** The system is now live, exposing the GPU server on `11434` and the CPU server on `11435`, ready to receive requests from Open WebUI.

## 3. Data Flow

Open WebUI integrates with this backend via the `Pipe` class defined in `hive_orchestrator.py`.

**Message Trajectory:**
1. **Input:** Open WebUI sends a chat payload to the `Pipe` function.
2. **Image Detection:** The orchestrator checks the RAW payload for images (handling both Data URIs and internal Open WebUI UUIDs). If an image is found, the request is hard-routed to the **Eye** model.
3. **Routing Decision:** For text, the user message is sent to the **Nexus** model via a prompt asking it to route the query to NEXUS, BOLT, NOVA, or EYE.
   - *Guardrail applied:* If Nexus hallucinates an "EYE" routing for a plain URL without an image extension, a programmatic override kicks the routing back to Nexus.
4. **Message Conversion:** Multimodal Open WebUI formats are transformed into standard Ollama compatible API payloads.
5. **Execution:** An HTTP POST request is sent to the appropriate server (`localhost:11434` for GPU/Nexus/Bolt/Eye or `localhost:11435` for CPU/Nova) using the `/api/chat` endpoint.
6. **Streaming:** The response streams back to Open WebUI, with custom injection lines indicating the chosen agent (e.g., `**🐝 HIVE → Nexus...**`). For Nova, internal `<thinking>` blocks are parsed and displayed visually in the UI.

## 4. Tool Pipeline

Tools are embedded into the prompt and intercepted on the return path:

1. **System Prompt Injection:** All models (except Eye) receive a system prompt explicitly defining available JSON-formatted tool calls:
   - `{"name": "read_url", "args": {"url": "THE_URL_HERE"}}`
   - `{"name": "search_web", "args": {"query": "YOUR_SEARCH_QUERY"}}`
2. **Output Interception:** As the LLM generates its response, the text is accumulated.
3. **Regex Extraction:** The `_extract_tool_call` function scans the output using regex patterns to find valid tool JSON blocks.
4. **Execution:**
   - `read_url` triggers `_scrape_url_with_playwright()` (headless Chromium).
   - `search_web` triggers `_search_web()` (`duckduckgo_search`).
5. **Follow-up:** If a tool was triggered, the result is appended to the message history as `[TOOL RESULT for ...]`, and a secondary automatic request is sent to the LLM to process the tool output and answer the original question. (Limited to 1 round of tool usage per user prompt).

## 5. Known Gaps & Bugs

During code review, the following potential issues were identified in the architecture:

- **Single Round Tool Limit:** The orchestrator only supports a single `_extract_tool_call` loop. If an LLM needs to use a tool, read the result, and then use another tool, the logic does not support recursive looping.
- **Concurrent Request Bottleneck:** The `.bat` script enforces `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_MAX_LOADED_MODELS=1`. This severely limits concurrent throughput to one user at a time per server.
- **Playwright DNS Masking:** `_scrape_url_with_playwright` simply returns the `innerText` of a page. It masks HTTP errors behind generic `[ERROR] Failed to scrape...` strings, which might not give the LLM enough context if a page requires a captcha or login, potentially leading to hallucinated text based on the URL name alone.
- **Regex Parsing Weakness:** `_extract_tool_call` uses strict regex extraction for JSON. If the LLM generates slightly malformed JSON (e.g., missing quotes, extra spaces inside keys), the tool call silently fails to trigger, and the malformed JSON is printed back to the user instead.
- **Image Fallback Brittle:** The `_fetch_image_by_id` function manually crawls `/app/backend/data/uploads`. If Open WebUI changes its internal directory structure, image handling will fail silently (as errors are caught and `None` is returned).
