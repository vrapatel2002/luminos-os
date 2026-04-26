# CLAUDE.md — Agent Quickstart
# [CHANGE: claude-code | 2026-04-26]

## Project: Luminos OS
- **OS**: Arch Linux on ASUS ROG G14
- **Core**: Go daemons, KDE Plasma, Qt/QML
- **AI**: MobileLLM on NPU (Driver), HIVE on GPU/CPU (llama.cpp TurboQuant)
- **Constraint**: 4.6GB Safe VRAM (6GB Total)
- **Rules**: NO DOCKER, NO OLLAMA, IDENTITY TAGS MANDATORY.

## HIVE Models (llama.cpp GGUF — NOT Ollama)
- **Nexus**: Llama-3.1-8B-Instruct-Q4_K_M.gguf (GPU)
- **Bolt**: Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf (GPU)
- **Nova**: DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf (CPU)
- **Sentinel**: MobileLLM-R1-140M-INT8.onnx (NPU via HATS)

## Workflow
1. Read AGENTS.md fully
2. Search MemPalace: `source ~/.mempalace-venv/bin/activate && python3 -m mempalace search "<topic>"`
3. Execute surgical changes with `[CHANGE: claude-code | date]` tags
4. Update LUMINOS_STATUS.md if component status changed
5. Update LUMINOS_DECISIONS.md if architectural decision made
6. Mine MemPalace: `python3 -m mempalace mine ~/luminos-os/`
7. Commit and push

## Mandatory After Every Task
```bash
source ~/.mempalace-venv/bin/activate
python3 -m mempalace mine ~/luminos-os/
git add -A
git commit -m "type(scope): description

Agent: claude-code
Task: [what was asked]"
git push origin main
```

Rule: MemPalace Usage (mandatory)
BEFORE every task:
  source ~/.mempalace-venv/bin/activate
  python3 -m mempalace search "<task topic>"
  This searches existing project knowledge.

AFTER every task:
  python3 -m mempalace mine ~/luminos-os/
  This indexes new changes into MemPalace.

Rule: CodeGraph Usage (mandatory)
BEFORE modifying any Python or Go file:
  Use code-review-graph MCP tool to check dependencies.

AFTER adding new files or changing imports:
  Use code-review-graph MCP to update the graph.

Rule: Doc Updates (mandatory)
After EVERY task check these and update if relevant:
  LUMINOS_STATUS.md, LUMINOS_DECISIONS.md, docs/BUGS.md, docs/CODE_REFERENCE.md.
