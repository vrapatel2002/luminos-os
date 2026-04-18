## MANDATORY RULES — READ BEFORE EVERY TASK

### Memory Tools — Use Every Session
1. **START every session**: search mempalace for current task topic
2. **BEFORE editing code**: run `code-review-graph get_minimal_context`
3. **BEFORE finishing**: save key decisions to mempalace
4. **NEVER** repeat something mempalace says already failed

### Tech Stack (LOCKED)
- **Bar/Dock**: HyprPanel (Go-based, built for Hyprland)
- **Apps/Settings/Login**: Go + GTK4 + libadwaita + CSS
- **Daemons**: Go
- **Window manager**: Hyprland
- **NO new Python UI code**

### Persistence Rule
`/opt/luminos/src` must always be symlinked to `~/luminos-os/src`.
If not symlinked, fix it before any other work:
```bash
sudo rm -rf /opt/luminos/src && sudo ln -sf /home/shawn/luminos-os/src /opt/luminos/src
```

### Git Rule
Commit and push after every completed task.

---

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
