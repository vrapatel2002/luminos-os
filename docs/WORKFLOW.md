# WORKFLOW.md — Luminos OS 5-Tool Pipeline

> How Claude Chat, Claude Code, Gemini CLI, and Antigravity work together without stepping on each other.

---

## The Big Picture

```
You (Director)
    │
    ├── Claude Chat      → Think, plan, debug, review
    │        │
    │        └── Claude Code   → Execute on G14, apply precise fixes
    │
    ├── Gemini CLI       → Terminal tasks, scripts, fast file work
    │
    └── Antigravity      → Build full GUI components autonomously
             │
             └── (Hands off to Claude Code for final review + commit)
```

**Rule:** No agent starts work until they've read `AGENTS.md` and queried MemPalace.

---

## Phase 1: Planning (Claude Chat)

Before any code gets written, come here (Claude.ai) with the task.

**What to tell Claude Chat:**
```
Task: [what you want built or fixed]
Current state: [what's working, what's broken]
Relevant files: [paths if known]
Constraints: [don't break X, keep Y working]
```

Claude Chat will:
- Query MemPalace for relevant past context
- Identify which agent should handle it
- Write the exact prompt to hand to that agent
- Flag any risks or edge cases

---

## Phase 2: Execution

### Path A — Bug fix or small change → Claude Code

Use when:
- Something is broken and the fix is < ~50 lines
- Config changes (Hyprland, systemd, etc.)
- Applying a plan that Claude Chat already figured out

**Prompt template for Claude Code:**
```
Context: Read ~/luminos-os/AGENTS.md fully before starting.
Query MemPalace: python3 -m mempalace query "<topic>"

Task: <specific task>

Files to touch: <list exact paths>
Files NOT to touch: <list what must stay unchanged>

Definition of done:
- [ ] <specific testable outcome>
- [ ] hyprctl configerrors returns empty (if hyprland touched)
- [ ] LUMINOS_STATUS.md updated
- [ ] Committed with message: fix(<scope>): <description>
- [ ] MemPalace updated with outcome
```

---

### Path B — New component or large feature → Antigravity

Use when:
- Building something new from scratch (login screen, new widget, etc.)
- Task needs editor + terminal + browser verification together
- You want parallel agents working different parts simultaneously

**Prompt template for Antigravity:**
```
[LUMINOS OS — AGENT TASK]

Before starting:
1. Read ~/luminos-os/AGENTS.md completely
2. Run: python3 -m mempalace query "<feature name>"
3. Run: python3 -m codegraph show-deps <relevant file>

Task: <what to build>

Project context:
- Arch Linux + Hyprland 0.54.3
- GUI components use Python + GTK4 + gtk4-layer-shell
- Bar lives at /opt/luminos/src/gui/bar/
- Dock lives at /opt/luminos/src/gui/dock/
- Design system: see ~/luminos-os/LUMINOS_DESIGN_SYSTEM.md

Requirements:
- <requirement 1>
- <requirement 2>

Must NOT change:
- Bar app (currently working)
- Dock app (currently working)
- hyprland.conf (unless adding exec-once for new component)

Code standards (mandatory):
- Add docstrings with WHY to every class and function
- Add [CHANGE: antigravity | date] tag to every modified block
- Leave HANDOFF comment at top of new files

When done:
1. Update ~/luminos-os/LUMINOS_STATUS.md
2. Update MemPalace with what was built and any decisions made
3. Run: python3 -m codegraph update <new file paths>
4. Commit: feat(<scope>): <description> (see AGENTS.md §5.1)
5. Push to origin main
```

---

### Path C — Terminal/scripting task → Gemini CLI

Use when:
- Searching through files for something specific
- Writing bash scripts or automation
- Boot/systemd config tasks
- Quick one-off codebase questions

**Prompt template for Gemini CLI:**
```bash
gemini "
Context: This is Luminos OS, a custom Arch Linux distro using Hyprland.
Read ~/luminos-os/AGENTS.md for project rules.

Task: <task>

Constraints:
- Do not touch bar_app.py or dock_app.py
- Do not modify hyprland.conf unless the task requires it
- Follow commit format in AGENTS.md §5.1

When done:
- Update ~/luminos-os/LUMINOS_STATUS.md if component status changed
- Run: python3 -m mempalace add '<what you did>'
- Commit with meaningful message and push
"
```

---

## Phase 3: Review (Claude Chat or Claude Code)

After Antigravity or Gemini finishes a task:

1. Claude Code reads the diff: `git diff HEAD~1`
2. Checks for AGENTS.md compliance (comments, tags, doc updates)
3. Runs the component to verify it works
4. If something looks off → fixes it with a `fix()` commit
5. Reports back to you

---

## Standard Session Flow

```
1. You tell Claude Chat what you want
2. Claude Chat → checks MemPalace → makes a plan → writes the agent prompt
3. You paste that prompt into the right tool
4. Agent works → updates docs → commits → pushes
5. Claude Code reviews the result
6. You confirm it's working on G14
7. Claude Chat updates LUMINOS_STATUS.md if needed
```

---

## Anti-Patterns to Avoid

| ❌ Don't do this | ✅ Do this instead |
|---|---|
| Ask an agent to "clean up the code" | Give a specific task with specific files |
| Let Antigravity touch the bar/dock while fixing login | Lock bar/dock in "must NOT change" list |
| Commit everything with `git add .` | Use `git add -p` to stage only what you meant to change |
| Let Gemini CLI make architectural decisions | Use Claude Chat for anything that requires judgment |
| Skip MemPalace when starting a task | Always query first — past decisions matter |
| Update docs "later" | Docs are part of the task. Done = code + docs + commit |

---

## Token Budget Tips

You have limited tokens across all tools. Use them efficiently:

- **Don't paste the full codebase** into Claude Chat. Use file paths and let Claude Code read them.
- **Gemini CLI's 1M context** → use it for "read this entire folder and tell me X" tasks
- **Antigravity's 2M context** → give it the whole repo root and let it find what it needs
- **Claude Chat** → use for decisions, not file reading. Keep convos focused.
- **If a task takes 3+ back-and-forth rounds** → it probably belongs in Claude Code or Antigravity, not chat

---

*Last updated: 2026-04-19 | By: claude-chat*
