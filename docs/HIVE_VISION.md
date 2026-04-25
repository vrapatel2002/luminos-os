# HIVE Vision — Luminos OS Integrated AI Experience
# Version: 2.0 — Full Integration Plan
# Date: April 2026
# Status: PLANNING — Build after this doc is complete

---

## What HIVE Is

HIVE is not a chatbot. It is an AI layer woven into 
every part of Luminos OS. The user never thinks 
"let me open my AI app." They just right-click, 
select text, press a shortcut, and AI is there.

---

## Model Stack (Updated April 2026)

### Current Models (to be replaced/upgraded)
| Agent | Current | Problem |
|-------|---------|---------|
| Nova | DeepSeek-R1-Distill-Qwen-7B | Old distill, outdated |
| Bolt | Qwen2.5-Coder-7B | Good but newer exists |
| Nexus | Llama-3.1-8B | Replaced by Dolphin |
| Eye | None | Not yet added |

### New Model Stack (locked)

#### Nexus — General Coordinator
- Model: Dolphin3-Llama3.1-8B Q4_K_M
- Why Dolphin: Uncensored, follows instructions 
  precisely, no refusals, excellent for OS tasks
- Device: GPU (RTX 4050)
- VRAM: ~4.6GB
- Role: Route requests, general chat, OS awareness,
  coordinate other agents

#### Bolt — Coding Specialist  
- Model: Qwen2.5-Coder-7B Q4_K_M (keep — still best 7B coder)
- Why: Still the FIM king at 7B, 88.4% HumanEval,
  128K context, 92+ languages. Nothing displaced it.
- Device: GPU (RTX 4050, swaps with Nexus)
- VRAM: ~4.7GB
- Role: Write code, debug, explain code, automate

#### Nova — Deep Reasoning
- Model: DeepSeek-R1-0528-Qwen3-8B Q4_K_M
- Why upgrade: R1-0528 distilled into Qwen3-8B.
  Surpasses Qwen3-235B-thinking on AIME 2024.
  Matches O3 and Gemini 2.5 Pro on reasoning.
  Same size as current but massively better.
- Device: CPU (ai_mode) or GPU (normal_mode)
- RAM: ~4.7GB (CPU) or VRAM ~4.7GB (GPU)
- Role: Deep analysis, planning, complex decisions

#### Eye — Vision Specialist
- Model: Qwen2.5-VL-7B Q4_K_M
- Why: Fastest vision-language at 7B, multimodal,
  reads images + screenshots + PDFs + UI elements
- Device: GPU (RTX 4050, swaps with others)
- VRAM: ~4.7GB
- Role: Screen reading, image analysis, OCR,
  PDF understanding, explain what's on screen

#### Embeddings — Memory/Search
- Model: nomic-embed-text-v1.5 Q4_K_M (keep)
- Device: CPU always
- RAM: ~81MB
- Role: Vector search, RAG, memory retrieval

### VRAM Strategy
```
6GB VRAM — ONE model at a time, swap on demand:
- Nexus loaded by default (coordinator)
- Request comes in → router detects type
- If different model needed → evict → load new one
- Swap time: ~10-15 seconds (acceptable)
- TurboQuant turbo4 on ALL GPU models

Gaming mode → ALL models evicted immediately
AI mode → Nova can run on CPU simultaneously with GPU model
Normal mode → All models GPU, swap as needed
```

---

## Integration Points (The Real Product)

### 1. Right-Click Context Menu (KDE Service Menu)

Right-click ANY file or folder → HIVE submenu:

**Files:**
- Summarize this file
- Explain this code (auto-detects language)
- Find bugs in this code
- Write tests for this
- Rename intelligently (suggests better name)
- Translate this document

**Folders:**
- Summarize this project
- Find duplicate files
- Explain folder structure
- Generate README

**Images:**
- Describe this image (Eye)
- Extract text from image (Eye + OCR)
- Ask about this image

**PDFs:**
- Summarize this PDF (Eye)
- Extract key points
- Answer questions about this PDF

Implementation: KDE Service Menu .desktop files
calls luminos-hive-cli with file path as argument.

### 2. Text Selection → Global Shortcut

Select any text anywhere (browser, terminal, editor):
Press SUPER+H → HIVE popup appears with options:
- Explain this
- Summarize
- Improve/rewrite
- Translate
- Continue writing from here
- Search for this

Implementation:
- KDE global shortcut reads clipboard
- Passes to HIVE orchestrator
- Shows result in KDialog popup or notification
- Option to copy result or type it directly

### 3. Type Directly Into Apps (The Magic Feature)

After HIVE generates text, user can:
- Copy to clipboard (default)
- TYPE it directly into focused window
  via xdotool type --clearmodifiers

This works for:
- Chrome/Firefox (emails, forms, search)
- Terminal
- Any text input anywhere on screen

Example flow:
1. User opens Gmail in Chrome
2. Selects some text or puts cursor in compose
3. Presses SUPER+H
4. Selects "Write email reply"
5. HIVE generates reply
6. User clicks "Type here" 
7. xdotool types text directly into Gmail

Implementation:
- xdotool for typing into any window
- ydotool as fallback for Wayland
- KDE klipper for clipboard integration

### 4. Screen Understanding

SUPER+SHIFT+H → Eye takes screenshot → analyzes:
- "What is on my screen right now?"
- "Explain this error message"
- "What does this UI do?"
- "Read the text in this image"

Result shown in floating HIVE panel.

### 5. Dedicated HIVE Chat Panel

A persistent panel (KDE Plasma widget or 
standalone window) for longer conversations:

Features:
- Chat history with all agents
- Switch between Nexus/Bolt/Nova/Eye
- File drag-and-drop for analysis
- Code blocks with syntax highlighting
- Copy/type any response
- Conversation memory via SQLite RAG
- Shows which model is responding
- Shows tokens/sec and VRAM usage

Implementation: Python Flask (localhost:7437) 
served as lightweight web app. No Docker.
Open in browser or KDE webview widget.

### 6. Gaming Mode Integration

When a game launches:
- luminos-power detects high GPU load
- Signals HIVE to evict all models
- HIVE panel shows "Gaming mode — AI suspended"
- When game closes → models reload on demand

### 7. Automation & Terminal Integration

From terminal:
```bash
hive "explain this error: [paste error]"
hive --bolt "write a bash script that..."
hive --eye screenshot  # analyze current screen
hive --nova "analyze pros and cons of..."
echo "code here" | hive --bolt "review this"
```

---

## Architecture

```
User Action (right-click/shortcut/terminal)
         ↓
luminos-hive-cli (Go binary — fast startup)
         ↓
HIVE Socket (/run/luminos/hive.sock)
         ↓
HIVEOrchestrator (Python — src/hive/orchestrator.py)
         ↓
Router → detects model needed
         ↓
VRAMManager → evict current, load needed model
         ↓
llama.cpp (TurboQuant turbo4 GPU inference)
         ↓
Response → 
  clipboard | xdotool type | notification | panel
```

---

## Build Order (Phase 4)

### Step 1 — Upgrade models (immediate)
- Download Dolphin3-Llama3.1-8B (replace Nexus)
- Download DeepSeek-R1-0528-Qwen3-8B (replace Nova)
- Download Qwen2.5-VL-7B (new Eye agent)
- Keep Bolt and embed as-is

### Step 2 — Eye agent implementation
- Wire Qwen2.5-VL-7B to orchestrator
- Screenshot capture tool
- PDF ingestion pipeline
- Image analysis pipeline

### Step 3 — CLI tool (luminos-hive-cli)
- Go binary for fast startup
- Connects to HIVE socket
- Supports all agents via flags
- Reads stdin for piped input

### Step 4 — KDE right-click service menus
- File/folder/image/PDF actions
- Calls luminos-hive-cli with context
- Shows result in KDialog

### Step 5 — Text selection + type into apps
- Global shortcut SUPER+H
- xdotool/ydotool integration
- KDialog result popup with "Type here" button
- Chrome/Firefox email integration

### Step 6 — Screen reading (SUPER+SHIFT+H)
- Screenshot via spectacle/scrot
- Pass to Eye agent
- Show result in notification/panel

### Step 7 — HIVE Chat Panel
- Python Flask web UI (localhost:7437)
- No Docker, minimal resources
- Full conversation history
- File drag-and-drop

### Step 8 — Gaming mode integration
- luminos-power signals HIVE
- Auto-evict on game detection
- Auto-restore when game closes

---

## What Makes This Different From Everything Else

| Feature | ChatGPT | Copilot | Luminos HIVE |
|---------|---------|---------|--------------|
| Right-click files | ❌ | ❌ | ✅ |
| Type into any app | ❌ | Partial | ✅ |
| Read your screen | ❌ | ❌ | ✅ |
| Works offline | ❌ | ❌ | ✅ |
| Your data stays local | ❌ | ❌ | ✅ |
| No subscription | ❌ | ❌ | ✅ |
| Uncensored (Dolphin) | ❌ | ❌ | ✅ |
| Integrated with OS | ❌ | Partial | ✅ |
| Gaming mode aware | ❌ | ❌ | ✅ |

---

## Open Questions (Decide Before Building)

1. HIVE panel — browser tab or KDE widget?
   Recommendation: browser tab first (simpler),
   KDE widget later as enhancement

2. Notification style — KDE native or custom?
   Recommendation: KDE native (notify-send)

3. Eye model — Qwen2.5-VL-7B or LLaVA-7B?
   Recommendation: Qwen2.5-VL-7B (faster, newer)

4. Type-into-app — xdotool or ydotool?
   Recommendation: ydotool (native Wayland)
   xdotool as XWayland fallback

---
Last updated: 2026-04-25
Status: APPROVED — ready to build Step 1
