# AGENTS.md — Luminos OS Agent Constitution
> Read this file **completely** before touching any code. Every agent (Claude Code, Gemini CLI, Antigravity) must follow these rules without exception.

---

## 1. What Is Luminos OS?

Luminos OS is a custom Arch Linux distribution built on:
- **Hyprland 0.54.3** as the Wayland compositor/desktop
- **HyprPanel** for the bar and dock (runs via `hyprpanel` + `hyprpanel-client`)
- **greetd** (planned) for the login screen
- **swww** for wallpaper
- **Triple-boot** setup on ASUS ROG G14 (Windows / Default Arch / Luminos)

**Design philosophy:** Clean, minimal, intentional. Every component should feel like it belongs. Don't import macOS. Don't import Windows. Build Luminos.

### Key file locations
```
~/.config/hypr/hyprpanel/         → HyprPanel config (bar+dock — do NOT touch unless task requires it)
/opt/luminos/src/gui/login/       → Login screen (WIP)
~/.config/hypr/hyprland.conf      → Hyprland config
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
- HyprPanel (bar+dock) and Hyprland config are currently working. Do not touch them unless your task involves them.
- Before editing any running component, check: *"Could this change crash the session?"*
- If yes → propose the change as a diff/comment first, don't apply it

### 2.3 Preserve Inter-Agent Context
- Every piece of code you write must be readable by the next agent (who may be a different AI with a different style)
- See Section 4 for commenting standards

---

## 3. Memory & Knowledge Tools

### 3.1 MemPalace — USE IT
MemPalace is the project's persistent memory store. It holds decisions, architecture notes, and history from all past sessions.

**Query MemPalace BEFORE starting any task:**
```bash
cd ~/luminos-os
python3 -m mempalace query "<your task topic>"
# Examples:
python3 -m mempalace query "dock alignment"
python3 -m mempalace query "login screen design"
python3 -m mempalace query "hyprland windowrule"
```

**Update MemPalace AFTER completing any task:**
```bash
python3 -m mempalace add --tag "component:dock" "Fixed dock alignment by setting gravity=SOUTH in layer-shell anchor"
python3 -m mempalace add --tag "decision" "Chose greetd over SDDM because lighter, better Wayland support"
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

Luminos uses Python for GUI components and bash/ini for config. Different agents write differently — these standards make the code readable to all of them.

### 4.1 Python — Required Comment Blocks

Every new function or class must have a docstring explaining **what it does AND why it exists**:

```python
class DockWindow(Gtk.ApplicationWindow):
    """
    The main dock window rendered at the bottom of the screen.

    WHY: Uses gtk4-layer-shell to anchor to SOUTH edge of the display.
    Hyprland treats layer-shell windows differently from normal windows —
    they bypass window rules and stay above regular app windows.

    AGENT NOTE: Do not change the layer or anchor without checking
    hyprland.conf layer rules first. Last touched: [date] by [agent-id].
    """
```

Every non-obvious line of logic needs an inline comment:

```python
# Fallback to /tmp socket if /run/luminos/ai.sock is not writable by current user.
# /run/luminos/ is owned by root; using os.access() prevents silent PermissionError spam.
if os.access(SYSTEM_SOCK, os.W_OK):
    self.socket_path = SYSTEM_SOCK
else:
    self.socket_path = FALLBACK_SOCK
```

### 4.2 Agent Identity Tags
When you make a change, leave a tag so others know who touched it and why:

```python
# [CHANGE: claude-code | 2026-04-XX] Fixed PermissionError on socket connect.
# Root cause: /run/luminos/ai.sock owned by root. os.path.exists() passed but
# connect() failed. Replaced with os.access(..., os.W_OK) check.
```

Format: `# [CHANGE: <agent> | <date>] <what> <why>`

Agents: `claude-code`, `claude-chat`, `gemini-cli`, `antigravity`

### 4.3 Hyprland Config Comments
```ini
# WHY: Firefox opens in floating mode by default because it ignores tiling hints.
# Hyprland 0.54.3+ requires block-style windowrule syntax (flat syntax removed).
windowrule {
    match:class = firefox
    float = true
}
```

### 4.4 What NOT to Do
```python
# BAD — no context for the next agent
if not self.client:
    return

# GOOD
# If daemon is unavailable (expected when not running), skip silently.
# DaemonClient sets self.client = None on connection failure.
if not self.client:
    return
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
- Always run `hyprctl configerrors` before committing Hyprland config changes.
- Push after every commit. Don't batch pushes.

### 5.3 Before Every Commit
```bash
# 1. Check you haven't accidentally touched unrelated files
git diff --name-only

# 2. Verify Hyprland config if you touched it
hyprctl reload && hyprctl configerrors

# 3. Commit with proper message
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
| **Gemini CLI** | Terminal automation, bash scripts, quick refactors, searching large codebases, boot/config tasks | Complex GUI component logic, edge-case debugging |
| **Antigravity** | Building entire new components end-to-end, visual GUI work, parallel multi-file features | Quick one-line fixes, anything MCP-dependent |

---

## 9. Current Open Tasks (as of last update)

See `LUMINOS_STATUS.md` for the full list. Top priorities:

1. **Login screen** — Go + GTK4 + libadwaita, fullscreen clock, Enter → password or desktop
2. **HyprPanel right-side layout** — Audio+battery systray grouping, clock time-over-date — needs reboot verify
3. **Settings app** — Go + GTK4 + libadwaita (Python settings code deprecated)
4. **Boot errors** — GPT mismatch warning (cosmetic, auto-corrects)

---

*Last updated: 2026-04-19 | By: claude-chat*
*Next review: After login screen is complete*
