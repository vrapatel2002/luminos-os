# Luminos OS — Agent Handoff Protocol
# [CHANGE: gemini-cli | 2026-05-09]

This document defines how agents hand off tasks to each other and interact with the HIVE Brain.

## 1. Antigravity CLI Integration

The Antigravity CLI is integrated into the Luminos workflow for headless task execution and QML/Qt work.

### Headless Mode
Use `antigravity chat` for direct prompts:
```bash
antigravity chat "your prompt here"
```

### Context-Aware Tasks
Use the `luminos-antigravity` wrapper to inject HIVE Brain context automatically:
```bash
luminos-antigravity "your task description"
```

### Capabilities
- **Native MCP**: `hive-brain` is available as a native tool.
- **Headless Execution**: Can be called by other agents (e.g., Cowork) for complex sub-tasks.
- **HIVE Context**: Always aware of current system state and safety rules.

## 2. Agent Roles

| Agent | Core Strength |
|-------|---------------|
| **Claude Code** | Architectural planning, complex C++/Go logic. |
| **Gemini CLI** | Automation, state maintenance, daemon orchestration. |
| **Antigravity** | Visual QML implementation, Qt widgets, UI polish. |

## 3. Handoff Commands

Agents can trigger each other via their respective CLIs:
- Trigger Claude: `claude "task"` (if available in path)
- Trigger Gemini: `gemini "task"`
- Trigger Antigravity: `luminos-antigravity "task"`
