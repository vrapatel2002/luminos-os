## LOCKED STACK: KDE Plasma, KWin, Qt/QML, Go
**BANNED: Hyprland, GTK4, PyGObject, Python UI, HyprPanel, Docker, Ollama**
Never write code for banned components. See LUMINOS_DECISIONS.md Decision 12.
# [CHANGE: claude-code | 2026-04-26]

---

## LUMINOS OS — GEMINI CLI AGENT RULES

### Mandatory — Before Every Task
- Read `LUMINOS_PROJECT_SCOPE.md` and `LUMINOS_STATUS.md` before every task
- Query Luminos Notes before starting: `~/luminos-os/scripts/luminos-notes.sh search "<topic>"`
  - **[CHANGE: gemini-cli | 2026-04-26] MemPalace retired. Use luminos-notes.sh instead.**
- Minimal changes only — do not touch working components
- Add `[CHANGE: gemini-cli | date]` tags to every modified block
- Update docs and commit after every task (see `docs/WORKFLOW.md`)
- Keep the existing MCP tools block at the bottom

---

## Gemini CLI — Session Start Prompt

```bash
gemini "
[LUMINOS OS — AGENT TASK]

Before doing anything:
1. Read ~/luminos-os/AGENTS.md (project rules)
2. Read ~/luminos-os/LUMINOS_STATUS.md (current component state)
3. Query Luminos Notes: ~/luminos-os/scripts/luminos-notes.sh search '<TOPIC>'

About this project:
Luminos OS is a custom Arch Linux distro on an ASUS ROG G14.
KDE Plasma 6.6.4 Wayland. Go daemons. llama.cpp TurboQuant for HIVE (NO Ollama).
Repo at ~/luminos-os/.

Your task:
<TASK>

Constraints:
- Do not touch KDE Plasma config unless the task explicitly requires it
- Only stage files you actually changed (git add -p, not git add .)
- Add # [CHANGE: gemini-cli | date] comments to anything you modify
- Never use Docker, Ollama, or any banned dep

When done:
- ~/luminos-os/scripts/luminos-notes.sh add [TAG] '[Summary of changes]'
- Update ~/luminos-os/LUMINOS_STATUS.md if a component status changed
- Update ~/luminos-os/LUMINOS_DECISIONS.md if an architectural decision was made
- git commit -m 'type(scope): description\n\nAgent: gemini-cli\nTask: <task>' and push
"
```

---

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.

Rule: Luminos Notes Usage (mandatory)
BEFORE every task:
  ~/luminos-os/scripts/luminos-notes.sh search "<task topic>"
  This searches existing project knowledge.

AFTER every task:
  ~/luminos-os/scripts/luminos-notes.sh add [TAG] "[Summary of changes]"
  This indexes new changes into Luminos Notes.

Rule: CodeGraph Usage (mandatory)
BEFORE modifying any Python or Go file:
  Use code-review-graph MCP tool to check dependencies.

AFTER adding new files or changing imports:
  Use code-review-graph MCP to update the graph.

Rule: Doc Updates (mandatory)
After EVERY task check these and update if relevant:
  LUMINOS_STATUS.md, LUMINOS_DECISIONS.md, docs/BUGS.md, docs/CODE_REFERENCE.md.
