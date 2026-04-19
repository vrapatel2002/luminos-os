# PROMPTS.md — Copy-Paste Agent Prompts for Luminos OS

> Pre-built prompts for each tool. Fill in the blanks and go.
> Always start a session by pasting the **Session Start Prompt** for that tool.

---

## Claude Code — Session Start Prompt

Paste this at the beginning of every Claude Code session:

```
You are working on Luminos OS — a custom Arch Linux distribution on an ASUS ROG G14.

MANDATORY first steps:
1. Read ~/luminos-os/AGENTS.md completely
2. Read ~/luminos-os/LUMINOS_STATUS.md to understand current state
3. Query MemPalace for context on this task:
   python3 -m mempalace query "<TOPIC>"

Project structure:
- Repo: ~/luminos-os/
- GUI components: /opt/luminos/src/gui/
- Hyprland config: ~/.config/hypr/hyprland.conf
- SSH to G14: shawn@192.168.2.16

Rules (from AGENTS.md — follow all of them):
- Minimal changes: only touch what's needed for this task
- Add [CHANGE: claude-code | date] tags to every modified block
- Add docstrings with WHY to any new functions/classes
- Update LUMINOS_STATUS.md when component status changes
- Update MemPalace when done
- Commit format: type(scope): description (see AGENTS.md §5.1)
- Use git add -p, never git add .
- Push after every commit

Current task:
<DESCRIBE TASK HERE>

Files to modify: <LIST>
Files NOT to touch: <LIST>

Done when:
- [ ] <specific outcome>
- [ ] Docs updated
- [ ] Committed and pushed
```

---

## Antigravity — Session Start Prompt

Paste into Antigravity's agent chat before describing the task:

```
[LUMINOS OS PROJECT — READ BEFORE STARTING]

Step 1 — Read these files completely:
- ~/luminos-os/AGENTS.md          (rules all agents must follow)
- ~/luminos-os/LUMINOS_STATUS.md  (current state of all components)
- ~/luminos-os/LUMINOS_DESIGN_SYSTEM.md  (colors, fonts, spacing)

Step 2 — Query project memory:
  python3 -m mempalace query "<TOPIC>"
  python3 -m codegraph show-deps <RELEVANT_FILE>

Step 3 — Understand the stack:
- OS: Arch Linux, Wayland compositor: Hyprland 0.54.3
- GUI: Python 3 + GTK4 + gtk4-layer-shell
- Bar: /opt/luminos/src/gui/bar/bar_app.py  [WORKING — do not break]
- Dock: /opt/luminos/src/gui/dock/dock_app.py  [WORKING — do not break]
- Env vars needed: WAYLAND_DISPLAY=wayland-1, XDG_RUNTIME_DIR=/run/user/1000, GDK_BACKEND=wayland

Mandatory code standards (non-negotiable):
- Every class and function needs a docstring: what it does + WHY it exists
- Every non-obvious line needs an inline comment
- Every modified block gets: # [CHANGE: antigravity | date] reason
- Leave a HANDOFF comment at the top of new files

After completing the task:
1. python3 -m codegraph update <new/modified paths>
2. python3 -m mempalace add --tag "component:<name>" "<what was done>"
3. Update ~/luminos-os/LUMINOS_STATUS.md
4. Update ~/luminos-os/LUMINOS_DECISIONS.md if any architectural choices were made
5. git add -p && git commit -m "feat(<scope>): <description>" && git push origin main

---
TASK:
<DESCRIBE WHAT TO BUILD>

Must NOT change:
- /opt/luminos/src/gui/bar/ (bar is working)
- /opt/luminos/src/gui/dock/ (dock is working)
- <ANY OTHER OFF-LIMITS FILES>

Definition of done:
- [ ] <outcome 1>
- [ ] <outcome 2>
- [ ] All docs updated
- [ ] Committed and pushed
```

---

## Gemini CLI — Session Start Prompt

```bash
gemini "
[LUMINOS OS — AGENT TASK]

Before doing anything:
1. Read ~/luminos-os/AGENTS.md (project rules)
2. Read ~/luminos-os/LUMINOS_STATUS.md (current component state)
3. Query MemPalace: python3 -m mempalace query '<TOPIC>'

About this project:
Luminos OS is a custom Arch Linux distro on an ASUS ROG G14.
Hyprland 0.54.3 compositor. Python/GTK4 for GUI. greetd for login (WIP).
Repo at ~/luminos-os/. GUI at /opt/luminos/src/gui/.

Your task:
<TASK>

Constraints:
- Do not touch bar_app.py or dock_app.py (they are working)
- Do not touch hyprland.conf unless the task explicitly requires it
- Only stage files you actually changed (git add -p, not git add .)
- Add # [CHANGE: gemini-cli | date] comments to anything you modify

When done:
- python3 -m mempalace add '<summary of what was done>'
- Update ~/luminos-os/LUMINOS_STATUS.md if a component status changed
- git commit -m 'type(scope): description' and push
"
```

---

## Common Task Prompts (Fill in and Use)

### Fix a specific bug
```
Task: Fix <DESCRIBE BUG>

Symptoms: <what the error says or what wrong behavior you see>
File where the bug is: <path>
When it happens: <trigger condition>

Do NOT change anything else. Minimal fix only.
```

### Build a new GUI component
```
Task: Build <COMPONENT NAME>

Description:
<what it looks like and what it does>

Placement: <where on screen, which layer>
Behavior: <how user interacts with it>
Design: Follow LUMINOS_DESIGN_SYSTEM.md for colors and fonts

It should launch via exec-once in hyprland.conf (add the line).
It should fail gracefully if the daemon is not running.
```

### Fix a config error
```
Task: Fix Hyprland config error

Error message: <paste exact error from hyprctl configerrors>
Config file: ~/.config/hypr/hyprland.conf
Hyprland version: 0.54.3

After fixing, run: hyprctl reload && hyprctl configerrors
Confirm the error is gone before committing.
```

### Update documentation
```
Task: Update project docs to reflect current state

Read the current code in <PATHS> and update:
- LUMINOS_STATUS.md → set component status to <status>
- LUMINOS_DECISIONS.md → add entry for <decision made>

Do not change any code. Docs only.
```

---

*Last updated: 2026-04-19 | By: claude-chat*
