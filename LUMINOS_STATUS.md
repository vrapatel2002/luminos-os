# LUMINOS_STATUS.md — Current State of All Components

> Updated by every agent after every task. If you're an agent, update this before committing.
> Format: component name, status emoji, last updated, brief notes.

**Status key:** ✅ Working | 🔧 In Progress | ❌ Broken | 📋 Not Started | ⚠️ Working with caveats

---

## Core System

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| Arch Linux base | ✅ Working | — | Triple boot on G14 alongside Windows + default Arch |
| Hyprland 0.54.3 | ✅ Working | 2026-04-12 | Config errors fixed. windowrulev2 migrated to block-style windowrule {} |
| swww-daemon | ⚠️ Partial | 2026-04-12 | Autostart via exec-once works. Wallpaper not set on boot. |
| Triple boot | ✅ Working | — | GRUB boots all three. GPT mismatch warning on boot (cosmetic, auto-corrects) |

---

## GUI Components

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| Top bar (bar_app.py) | ✅ Working | 2026-04-12 | Layer-shell working. Daemon socket permission error resolved. Autostart via exec-once. |
| Dock (dock_app.py) | ✅ Working | 2026-04-12 | Same socket fix applied. Autostart working. Alignment still needs polish. |
| Login screen | 📋 Not Started | — | Design: fullscreen, big clock+date, Enter → password or desktop. greetd backend planned. GTK4 gl module issue with greetd noted. |
| App launcher | 📋 Not Started | — | No launcher implemented yet |
| Notification center | 📋 Not Started | — | Not yet scoped |

---

## Boot & System Issues

| Issue | Status | Notes |
|-------|--------|-------|
| GPT mismatch warning | ⚠️ Known/cosmetic | Auto-corrects on boot. Not urgent. Do not fix unless causing real problems. |
| Missing Casper user reference | ⚠️ Known/cosmetic | Expected in custom distro chroot. Ubuntu-ism, harmless on Arch. |
| greetd GTK4 gl module error | ❌ Blocking login screen | GTK4 renderer fails in greetd environment. Needs investigation before login screen work starts. |

---

## Daemon & Backend

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| Luminos AI daemon | 📋 Not running | — | /run/luminos/ai.sock exists but owned by root. Bar/dock degrade gracefully when daemon absent. |
| MemPalace | ✅ Available | — | Use before/after every task |
| CodeGraph | ✅ Available | — | Update when adding files or changing imports |

---

## Open Tasks (Priority Order)

1. **Login screen** — fullscreen clock, Enter-to-auth flow, greetd or fallback
2. **Dock alignment** — centering and position polish
3. **Boot warnings** — investigate GPT mismatch (low priority, cosmetic)
4. **Wallpaper on boot** — set default wallpaper via swww in exec-once
5. **File manager** — Dolphin installed (`sudo pacman -S dolphin`). Needs desktop shortcut/autostart option.

---

## Agent Activity Log

| Date | Agent | Task | Outcome |
|------|-------|------|---------|
| 2026-04-12 | claude-code | Fix socket PermissionError in bar/dock | ✅ os.access() fix applied, warnings downgraded to debug |
| 2026-04-12 | claude-code | Autostart bar + dock via exec-once | ✅ Working with env vars in hyprland.conf |
| 2026-04-12 | claude-chat | Debug Hyprland 0.54.3 windowrule syntax | ✅ Migrated to block-style windowrule {} format |
| 2026-04-19 | claude-chat | Design multi-agent workflow (AGENTS.md, WORKFLOW.md, PROMPTS.md) | ✅ Created — pending copy to repo |
| 2026-04-24 | gemini-cli | Wine DPI fix, Adobe entry attempt, Phase 4 docs update | ✅/❌ DPI & docs done, Adobe failed |

---

*Last updated: 2026-04-24 | By: gemini-cli*
*Next update due: After login screen task begins*

---

## HIVE / Phase 4 Status (April 2026)

| Component | Status | Last Updated | Notes |
|-----------|--------|-------------|-------|
| Wine DPI fix | ✅ Done | 2026-04-24 | Set to 192 DPI for G14 HiDPI screen |
| Adobe app menu | ❌ Failed | 2026-04-24 | No Adobe executables found in Wine prefix |
| TurboQuant | ✅ Working | 2026-04-24 | llama.cpp integration done |
| HIVE loading strategy | ✅ Documented | 2026-04-24 | On-demand GPU only, no Docker, no Ollama |

**Recent Confirmations:**
- NVIDIA driver (595.58.03): ✅ Working
- RTX 4050 VRAM: 6141MB confirmed
- llama.cpp TurboQuant build: ✅
- TurboQuant flags (turbo4): ✅
- llama-cpp-python CUDA: ✅
