# AGENTS.md — Luminos OS Agent Constitution
> Read this file **completely** before touching any code. Every agent (Claude Code, Gemini CLI, Antigravity) must follow these rules without exception.

---

## 1. What Is Luminos OS?

Luminos OS is a custom Arch Linux distribution built on:
- **KDE Plasma** as the Wayland desktop shell (KWin compositor)
- **SDDM** for the login screen
- **Go daemons** for NPU/AI/compat router
- **Qt/QML** for custom Luminos widgets (zone indicators, etc.)
- **Triple-boot** setup on ASUS ROG G14 (Windows / Default Arch / Luminos)

**BANNED (retired April 2026):** Hyprland, GTK4, HyprPanel, PyGObject, Python UI, greetd, swww, Waybar, AGS. See Decision 12 in LUMINOS_DECISIONS.md.

**Design philosophy:** Clean, minimal, intentional. Every component should feel like it belongs. Don't import macOS. Don't import Windows. Build Luminos.

### Key file locations
```
/opt/luminos/src/                 → Luminos source (symlinked from ~/luminos-os/src)
~/luminos-os/                     → Repo root (all .md docs live here)
```

---

## 2. The Golden Rules (Non-Negotiable)

### 2.1 Minimal Changes Policy
> **Do not change what is not broken.**

- Only modify files directly related to the task you were given
- If you see something that looks wrong but is NOT part of your task → add a `# TODO(agent): noticed X, not touching it` comment and move on
- Never refactor code style, rename variables, or reorganize imports unless the task explicitly asks for it
- If a fix requires touching more files than expected → STOP, explain why, and ask before proceeding

### 2.2 Never Break the Running System
- KDE Plasma, SDDM, and KWin are the protected running components. Do not touch them unless your task involves them.
- Before editing any running component, check: *"Could this change crash the session?"*
- If yes → propose the change as a diff/comment first, don't apply it

### 2.3 Preserve Inter-Agent Context
- Every piece of code you write must be readable by the next agent (who may be a different AI with a different style)
- See Section 4 for commenting standards

---

## 3. Memory & Knowledge Tools

### 3.1 MemPalace — USE IT
> **[CHANGE: antigravity | 2026-04-19] MemPalace is fixed. Uses a dedicated Python 3.12 venv at `~/.mempalace-venv` to avoid Python 3.14 incompatibility with chromadb/pydantic. MCP also registered in `.mcp.json`.**

MemPalace is the project's persistent memory store. It holds decisions, architecture notes, and history from all past sessions.

**Query MemPalace BEFORE starting any task:**
```bash
cd ~/luminos-os
source ~/.mempalace-venv/bin/activate
python3 -m mempalace search "<your task topic>"
# Examples:
python3 -m mempalace search "dock alignment"
python3 -m mempalace search "login screen design"
python3 -m mempalace search "hyprland windowrule"
```

**Update MemPalace AFTER completing any task:**
```bash
source ~/.mempalace-venv/bin/activate
# Re-mine the project to index new/changed files:
python3 -m mempalace mine ~/luminos-os
```

MemPalace entries should be short (1-3 sentences), factual, and tagged. Don't store code — store decisions and outcomes.

### 3.2 CodeGraph — USE IT FOR STRUCTURE QUESTIONS
Before asking "where does X connect to Y", query CodeGraph:
```bash
cd ~/luminos-os
python3 -m codegraph query "DaemonClient"
python3 -m codegraph query "login_screen imports"
python3 -m codegraph show-deps /opt/luminos/src/gui/login/
```

**Update CodeGraph when you add new files or change imports:**
```bash
python3 -m codegraph update /opt/luminos/src/gui/login/
```

---

## 4. Code Style & Commenting Standards

Luminos uses Go for daemons, Qt/QML for GUI widgets, and bash for scripts. Different agents write differently — these standards make the code readable to all of them.

### 4.1 Go — Required Comment Style

Every non-obvious function or exported type needs a one-line doc comment:

```go
// LuminosDaemon manages the AI routing socket and NPU task queue.
type LuminosDaemon struct { ... }
```

Every non-obvious line of logic needs an inline comment:

```go
// Fallback to /tmp socket if /run/luminos/ai.sock not writable by current user.
if unix.Access(systemSock, unix.W_OK) == nil {
    socketPath = systemSock
} else {
    socketPath = fallbackSock
}
```

### 4.2 Agent Identity Tags
When you make a change, leave a tag so others know who touched it and why:

```go
// [CHANGE: claude-code | 2026-04-XX] Fixed PermissionError on socket connect.
```

```qml
// [CHANGE: claude-code | 2026-04-XX] Zone dot color bound to window property.
```

Format: `// [CHANGE: <agent> | <date>] <what> <why>`

Agents: `claude-code`, `claude-chat`, `gemini-cli`, `antigravity`

### 4.3 QML Style Notes
```qml
// WHY: Rectangle used instead of Item so color/border props are available directly.
Rectangle {
    id: zoneDot
    width: 12; height: 12
    radius: 6
    color: zoneColor  // bound from C++/Go backend via Plasma widget API
}
```

### 4.4 What NOT to Do
```go
// BAD — no context for the next agent
if client == nil {
    return
}

// GOOD
// If daemon unavailable (expected when not running), skip silently.
// Client is nil when connection fails in NewDaemonClient().
if client == nil {
    return
}
```

---

## 5. Git Discipline

### 5.1 Commit Message Format
```
<type>(<scope>): <short description>

<body — what changed and why, 2-4 sentences>

Agent: <claude-code|gemini-cli|antigravity>
Task: <one line description of what you were asked to do>
```

**Types:** `fix`, `feat`, `config`, `docs`, `refactor`, `chore`
**Scopes:** `bar`, `dock`, `login`, `hyprland`, `boot`, `daemon`, `docs`, `workflow`

**Examples:**
```
fix(dock): suppress PermissionError spam on daemon socket

DaemonClient was logging a warning on every poll when /run/luminos/ai.sock
existed but was not writable by the luminos user. Replaced os.path.exists()
with os.access(..., os.W_OK) and downgraded log level to debug.

Agent: claude-code
Task: Fix bar/dock permission error on socket connect
```

```
feat(login): add clock widget with Enter-to-auth flow

Adds a fullscreen login overlay with large time/date display.
Pressing Enter transitions to password input if account is locked,
or directly loads the session if no password is set.

Agent: antigravity
Task: Build login screen — big clock, Enter flow, no password bypass
```

### 5.2 Commit Rules
- One logical change per commit. Don't bundle unrelated fixes.
- Never commit broken code. If it's WIP, use a `chore(wip):` prefix.
- Push after every commit. Don't batch pushes.

### 5.3 Before Every Commit
```bash
# 1. Check you haven't accidentally touched unrelated files
git diff --name-only

# 2. Commit with proper message
git add -p   # Stage changes interactively, not git add .
git commit -m "type(scope): description"
git push origin main
```

---

## 6. Documentation Maintenance

> **Docs are part of the task. A task is not done until docs are updated.**

### Which doc to update for what:

| File | Update when... |
|------|---------------|
| `LUMINOS_STATUS.md` | Any component status changes (broken → working, WIP → done) |
| `LUMINOS_DECISIONS.md` | You make an architectural choice or pick one approach over another |
| `LUMINOS_DESIGN_SYSTEM.md` | You change colors, fonts, spacing, or visual behavior |
| `LUMINOS_PROJECT_SCOPE.md` | Scope changes — new feature added, feature cut, priority changed |
| `AGENTS.md` (this file) | Workflow changes, new tools added, new rules needed |

### Update format for LUMINOS_STATUS.md:
```markdown
## Component: Dock
- **Status:** ✅ Working
- **Last updated:** 2026-04-XX by claude-code
- **Notes:** Layer-shell anchor fixed. PermissionError on daemon socket resolved.
  Autostart via exec-once in hyprland.conf confirmed working.
```

### Update format for LUMINOS_DECISIONS.md:
```markdown
## Decision: Socket access check method
- **Date:** 2026-04-XX
- **Agent:** claude-code
- **Decision:** Use os.access(path, os.W_OK) instead of os.path.exists()
- **Why:** /run/luminos/ai.sock exists but is owned by root. exists() passes,
  connect() then throws PermissionError on every poll. os.access() checks
  actual write permission before attempting connection.
- **Alternatives considered:** Try/except only — rejected because it was still
  logging warnings at default level on every poll cycle.
```

---

## 7. Task Handoff Protocol

When you finish a task and another agent will continue:

1. **Leave a handoff comment** at the top of modified files:
```python
# HANDOFF [claude-code → antigravity | 2026-04-XX]
# Completed: Socket permission fix in DaemonClient
# Next task: Build login screen (see LUMINOS_STATUS.md → Login Screen section)
# Watch out for: GTK4 gl module issue with greetd — may need fallback renderer
```

2. **Update MemPalace** with what you did and what's next
3. **Update LUMINOS_STATUS.md** with current state
4. **Commit and push** before handing off

---

## 8. What Each Agent Is Best At

| Agent | Use for | Avoid using for |
|-------|---------|-----------------|
| **Claude (chat)** | Debugging weird edge cases, architecture decisions, planning, reviewing other agents' work | Large file writes, executing on G14 |
| **Claude Code** | Precise file edits, executing on G14, fixing bugs identified by Claude chat | Large new feature builds from scratch |
| **Gemini CLI** | Terminal automation, bash scripts, quick refactors, searching large codebases, KDE config tasks | Complex GUI component logic, edge-case debugging |
| **Antigravity** | Building entire new Qt/QML components end-to-end, visual GUI work, parallel multi-file features | Quick one-line fixes, anything MCP-dependent |

### Protected Components (Do Not Touch Unless Task Requires It)
- **KDE Plasma** — desktop shell configuration
- **SDDM** — login manager
- **KWin** — compositor and window manager rules

---

## 9. Current Open Tasks (as of last update)

See `LUMINOS_STATUS.md` for the full list. Top priorities:

1. **KDE Plasma install** — `sudo pacman -S plasma-desktop plasma-wayland-session sddm kde-gtk-config breeze breeze-gtk dolphin konsole kscreen powerdevil plasma-nm plasma-pa bluedevil` then `sudo systemctl enable sddm && sudo reboot`
2. **SDDM theme** — Luminos-branded login screen for SDDM
3. **Zone indicator widget** — Qt/QML KDE Plasma widget: colored dot on window corner per compatibility zone
4. **Go daemons** — NPU daemon, AI compat router, Sentinel
5. **Settings app** — Qt/QML + Go backend

---

*Last updated: 2026-04-19 | By: claude-chat*
*Next review: After login screen is complete*
