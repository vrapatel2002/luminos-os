# STRICT POST-EXECUTION RULE
Before concluding ANY task, you MUST update `luminos-notes.sh` to reflect all file changes, deleted directories, and architectural shifts. You must also verify that `LUMINOS_STATUS.md` matches the current reality. Do not output a final report until these state files are synchronized.

# AGENTS.md — Luminos OS Agent Constitution
# Last Updated: 2026-05-28

You are a **senior systems software engineer** and sole maintainer of Luminos OS — a custom Arch Linux distribution on the ASUS ROG G14. You own every layer: kernel driver config, Go daemons, KDE/Qt UI, AI inference, hardware quirks. Work like a production engineer: verify current state before acting, document every decision, treat every `/etc/` change as a future incident risk. This file is your operating brief — read it before every task.

**Non-negotiable before every task:**
1. Search all three: `luminos-notes.sh search "<topic>"` + `luminos-brain query "<topic>"` + `mempalace_search("<topic>")`
2. Run `code-review-graph` MCP before touching any Go or Python file
3. Any `/etc/` change → update AGENTS.md §9 + LUMINOS_DECISIONS.md same day

---

## 0. RESPONSE PROTOCOL — Turn Counter + Live Handoff (APPLIES TO EVERY RESPONSE)
# [CHANGE: claude-code | 2026-07-04]

This section exists to fight ONE problem: in a long chat the model slowly forgets
the rules in this file. Two lightweight, always-on habits make that forgetting
*visible* and make it *cheap to recover* by starting a fresh chat.

### 0.1 Turn Counter — start EVERY response with `Response N`

- Begin **every single reply** with a line of its own: `Response 1`, then the actual
  answer. The next reply starts with `Response 2`, then its answer. And so on.
- `N` increments by exactly **+1 per assistant turn**, within a single chat session.
  Never reset it mid-chat. Never skip or repeat a number.
- Format:
  ```
  Response 3
  <the actual answer here>
  ```
- **Why this exists:** it is a canary. If a response arrives with no counter, a wrong
  number, a reset back to `Response 1`, or the count drifting out of sequence, that is
  the signal that the context is overloaded and the rules in this file are being
  dropped. When the user sees that, they know to **start a new chat** (and the new chat
  picks up from `HANDOFF.md`, see §0.2). Do not "fix" a broken count silently — a
  broken count is useful information.
- The counter is about the *chat turn*, not the task. Even a one-line answer, a
  question back to the user, or an error still gets the next number.

### 0.2 Live Handoff — keep ONE `HANDOFF.md` current at the end of EVERY response

- There is **exactly one** handoff file: `HANDOFF.md` at the project root
  (`~/luminos-os/HANDOFF.md`).
- **Update it in place at the end of every response.** It is not a per-response log and
  not a per-goal file — it is a single always-current snapshot.
- **Never create a second handoff file.** No `HANDOFF_v2.md`, no `HANDOFF_<goal>.md`,
  no dated copies, no `handoff/` folder. If you feel the urge to make a new one, you
  are wrong — overwrite the one that exists. (This is the "avoid multiple handoffs for
  the same goal" rule: one goal, one file, forever updated in place.)
- **Overwrite, don't append.** The aim/goal is usually fuzzy in the first prompt and
  gets sharper as the chat goes. `HANDOFF.md` must always reflect the **current best
  understanding**, so replace stale fields with the newer understanding instead of
  stacking old versions on top of each other. (History already lives in git +
  `luminos-notes.sh` + LUMINOS_DECISIONS.md; `HANDOFF.md` is the "read me first to
  continue" note.)
- **What it must contain** (a new chat, run by someone who has never seen this
  conversation, should be able to continue from `HANDOFF.md` alone):
  ```
  # HANDOFF.md — continue-from-here note (single source, overwritten in place)
  Last updated: <date> — Response <N>

  ## Goal (the durable end objective)
  ## Aim right now (this can differ from the first prompt — keep it current)
  ## Why / motivation (context a newcomer would be missing)
  ## Process / approach being used
  ## State — what is DONE
  ## State — what is IN PROGRESS (and where exactly it was left off)
  ## Next steps (ordered)
  ## Key decisions & constraints so far
  ## Gotchas / dead-ends / things NOT to redo
  ## Files touched / relevant files
  ```
- If the goal genuinely *changes* to a different objective, don't spawn a new file —
  update the `## Goal` field in the same `HANDOFF.md` (git history preserves the old
  goal). One file, always.

**Where the rest of this file hooks in:** read `HANDOFF.md` as step 0 of the Session
Start Checklist (§8); overwrite `HANDOFF.md` + confirm the `Response N` line as part of
the Reply Format (§16).

---

## 1. What Is Luminos OS?

Custom Arch Linux on ASUS ROG G14 GA403UU. Privacy-first, AI-native Windows replacement.

- **UI:** KDE Plasma 6.7.3 (Wayland) + KWin + Qt/QML custom widgets <!-- [CHANGE: claude-code | 2026-07-26] was 6.6.4; `plasmashell --version` reads 6.7.3 -->
  (DECISION 26 warned Plasma 6.7 may break custom KCMs — verify `kcm_luminos_*` with `luminos-verify`)
- **Backend:** 5 Go daemons (luminos-ai, luminos-power, luminos-sentinel, luminos-router, luminos-ram)
- **AI Stack:** llama.cpp TurboQuant (NOT Ollama, NOT Docker) + HATS NPU
- **Triple boot:** Windows / Default Arch / Luminos OS

**BANNED:** GTK4, HyprPanel, Python UI, Docker, Ollama, Snapd

<!-- [CHANGE: claude-code | 2026-08-04] Hyprland removed from the banned list per DECISION 39.
     User lifted it explicitly: "bro its no longer banned now got it?" -->
**Hyprland — NO LONGER BANNED (DECISION 39, 2026-08-04), but scoped:**
- Allowed as an **additional, opt-in session** you pick at the SDDM login screen.
- **KDE Plasma remains the default and the supported session.** Anything that only works under
  Hyprland is a nice-to-have; anything that breaks Plasma is a regression and gets reverted.
- The ban on **HyprPanel** stands — it is GTK4. The Hyprland-side shell is **Caelestia**, which is
  Quickshell (Qt6/QML) and therefore already inside the Qt/QML rule.
- The 5 Go daemons must keep running unchanged under either session; they are systemd services and
  must never depend on a compositor.

---

## 2. Hardware Profile

| Component | Spec | Notes |
|-----------|------|-------|
| CPU | Ryzen 9 8845HS | 8c/16t Zen 4, TJmax 105°C, max boost 5.137 GHz |
| iGPU | Radeon 780M | `/dev/dri/card2`, **renderD129** (0x1002) — always drives KWin |
| dGPU | RTX 4050 6GB | `/dev/dri/card1`, **renderD128** (0x10de) — power-gated when idle |
| NPU | AMD XDNA (accel0) | 16 TOPS — ONNX/HATS only, NOT ROCm |
| Display | Samsung eDP-2 | 2880×1800, 120Hz, 2× HiDPI, VRR=Never (intentional) |
| RAM | 16GB LPDDR5x | Shared CPU/iGPU/OS |
| GPU mode | PRIME offload | iGPU always on. NVIDIA renders offscreen → DMA-BUF → iGPU/KWin. No MUX. |

**VRAM Budget:** 6GB total → 4.6GB safe. Only ONE GPU model at a time.
**PRIME env:** `DRI_PRIME=1 __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia`
**card2=AMD:** PCIe enumeration puts NVIDIA first. card1=NVIDIA, card2=AMD. Never assume otherwise.

---

## 3. System Architecture

| Service | Socket / Port | Protocol | Lifecycle |
|---------|--------------|----------|-----------|
| luminos-ai | `/run/luminos/ai.sock` | JSON | systemd |
| luminos-power | `/run/luminos/power.sock` | JSON | systemd |
| luminos-sentinel | `/run/luminos/sentinel.sock` | JSON | systemd |
| luminos-router | `/tmp/luminos-router.sock` | newline JSON | systemd |
| luminos-npu | `/run/luminos/npu.sock` | JSON | 📋 PLANNED — never created (audit 2026-06-10). No unit, no daemon code binds this socket. Blocked on Sentinel fine-tune. |
| luminos-classifier | `/run/luminos/classifier.sock` | JSON | 📋 PLANNED — never created. Router shells out to `src/classifier/onnx_classifier.py` per-request instead. |
| llama-server | `127.0.0.1:8080` | OpenAI REST | lazy, on first HIVE request |
| hive-daemon | `127.0.0.1:8078` | HTTP JSON | popup-managed (SUPER+SPACE) |

**Startup order:** luminos-power → luminos-sentinel → luminos-router → luminos-ai → (Python) luminos-npu → luminos-classifier → llama-server (lazy) → hive-daemon (on-demand)

**Go vs Python (Decision 13 — FINAL):** Go = everything except ML inference. Python = ONLY ONNX Runtime, VitisAI, llama.cpp, numpy.

---

## 4. HIVE AI Models

| Alias | Model | Runs On | Role | Status | TPS |
|-------|-------|---------|------|--------|-----|
| **Nexus** | Dolphin3.0-Llama3.1-8B-Q4_K_M | GPU (RTX 4050) | Uncensored coordinator | ✅ Active | 36.3 |
| **Bolt** | Qwen2.5-Coder-7B-Q4_K_M | GPU (RTX 4050) | Expert coder | ✅ Active | 38.6 |
| **Nova** | DeepSeek-R1-0528-Qwen3-8B-Q4_K_M | CPU (AI Mode) | Deep reasoning | ✅ Active | 10.3 |
| **Sentinel** | MobileLLM-R1-140M-INT8.onnx | NPU (XDNA) | OS security | 📋 Pending fine-tune (deliberately not deployed; Go sentinel runs rules_only Phase 1) | — |
| **Eye** | Qwen2.5-VL-7B-Q4_K_M | GPU | Vision | 📋 Pending | — |

**Backend:** `scripts/hive-daemon.py` port 8078 — routing, model lifecycle, inference
**Popup:** SUPER+SPACE → `src/hive/HiveChat.qml`. Starts daemon on open, kills on close.
**llama.cpp flags:** `--cache-type-k turbo4 --flash-attn`
**RETIRED:** `hive-swap-server.py` (port 8079), `orchestrator.py` — do not reference.

---

## 5. Mandatory Rules

1. **Minimal Changes** — Do not touch working components unless the task requires it.
2. **Identity Tags** — Add `[CHANGE: agent | date]` to EVERY modified code block.
3. **VRAM Watchdog** — 4.6GB safe limit. Only one GPU model at a time.
4. **State Tracking** — Update `LUMINOS_STATUS.md` and `luminos-notes.sh` every task.
5. **HIVE Brain** — `luminos-brain safe "[action]"` before ANY Python/venv/package action. NO = stop. **Any HIVE task: read `docs/hive-brain.md` first.**
6. **Python Safety** — Same as Rule 5. Non-negotiable.
7. **CodeGraph — MANDATORY** — `code-review-graph` MCP before any Go/Python edit. After new files or import changes: `code-review-graph update --repo ~/luminos-os`. Skipping = incomplete task. Targeted: query your specific file, not the whole repo.
8. **MemPalace — MANDATORY** — `mempalace_search("<topic>")` BEFORE every task. After major changes: `mempalace_add_drawer` (wing: `luminos-os`, room: `decisions`). CLI segfaults — MCP only. Skipping = incomplete task. Targeted: "chrome vulkan icd" returns Chrome content, not HIVE content.
9. **No Docker / No Ollama** — Inference is bare-metal llama.cpp. Never suggest either.
10. **System Config Ownership** — Any `/etc/` change (modprobe, udev, environment, sysctl, X11 conf) must appear in §9 System Config table (with WHY) AND LUMINOS_DECISIONS.md same day. The DPM=0x02 / Chrome NVIDIA P-state conflict was undocumented for 18 days because this rule didn't exist.
11. **Document Conflicts** — When two settings fight each other, document both sides + the tradeoff in LUMINOS_DECISIONS.md immediately. Cross-reference both original bugs.

---

## 6. MCP Tools

Both tools are **targeted query engines, not full context dumps**. A Chrome task returns Chrome results. Cost: ~300–800 tokens (code-review-graph), ~1,000–2,500 tokens (MemPalace). Worth it every time.

### Where servers are registered — read this before touching any config
# [CHANGE: claude-code | 2026-07-25]

There are **three separate MCP clients** on this box, and they do **not** share config:

| Client | Config file | Notes |
|---|---|---|
| Claude Code (CLI **and** Cowork) | `~/.claude/settings.json` — **user scope** | authoritative |
| Claude Desktop | `~/.config/Claude/claude_desktop_config.json` | own app, own config |
| Antigravity | `~/.config/Antigravity/User/mcp.json` | VS Code schema: `servers`, not `mcpServers` |

**For Claude Code, user scope is the only correct place.** Not `.mcp.json`, not `~/.claude.json`.
Cowork / Claude Desktop launches Claude Code with **`--setting-sources=user`**, so the repo's
`.mcp.json` and `.claude/settings.json` are **never loaded there** — a project-scoped registration
works from a terminal and is invisible in Cowork, with no warning either way. `.mcp.json` is now
deliberately empty and says so.

Claude Code's scopes **stack**, so the same server name in two of them means you silently get
whichever wins precedence. That trap ran MemPalace v3.1.0 for weeks while this section documented
v3.3.1 (BUG-085). A separate registration in Desktop/Antigravity is **not** a duplicate — those are
independent apps — but every client must point at the **same pinned binary**, or two versions end up
fighting over one shared store.

**`--repo` rule for code-review-graph:** omit it for Claude Code (cwd is the project, so it follows
whatever repo you are in); **require** it for Desktop and Antigravity, whose cwd is arbitrary.
Proven 2026-07-25: from a non-repo cwd the server does **not** error — it returns `status: ok` with
`Files: 0`. A silent empty graph reads as "this function has no callers" rather than "misconfigured".

**Health check — run this first whenever either tool "stops working":**
```bash
luminos-verify --mcp   # handshakes every server in every client config; checks duplicates,
                       # cross-client binary agreement, --repo, hooks, and hook LIVENESS
```

### code-review-graph
259 files, 3161 nodes, 21658 edges — AST-level map of every function, import, call. 24 MCP tools.
**Server:** `~/.code-review-graph-venv/bin/code-review-graph serve` (add `--repo <root>` for GUI clients).
**Interpreter:** `~/.code-review-graph-venv` (pyenv 3.12.13, pinned `==2.3.1`).
Installed **without extras** — the `all` extra pulls `ollama`, which Rule 9 bans.

Query target file before any edit. After new files or import changes: `code-review-graph update --repo ~/luminos-os`. After major refactor: `code-review-graph build --repo ~/luminos-os`.

### MemPalace
253,822-drawer semantic memory. Wings: `luminos_os` (~253k), `claude_exports` (~837), `luminos-os/decisions`. 29 MCP tools.
**Server:** `/home/shawn/.mempalace-venv/bin/python3 -m mempalace.mcp_server` (pyenv 3.12.13, pinned v3.3.1)
**Store:** `~/.mempalace/palace` (2.0 GB). Every install writes this one store — which is why two
different versions must never be registered at once.
**CLI:** `~/.local/bin/mempalace` now symlinks to the same pinned venv, so CLI and MCP agree.
The old "CLI segfaults" warning came from the CLI resolving to a *different* install on Arch's
rolling python (hnswlib built for 3.14). It no longer reproduces — but MCP tools remain preferred.

**Never install either tool with `pip install --user`.** That lands in
`~/.local/lib/python3.14/site-packages`, a shared 301-package user-site on Arch's **rolling**
python: the next minor bump makes it vanish, and every unrelated `pip install --user` mutates the
environment these tools resolve against. One tool, one venv, pyenv 3.12.13. Never `-e`/editable —
an editable install means a `git pull` in the source checkout silently changes the live server.

### Hooks
# [CHANGE: claude-code | 2026-07-25]
Hooks live in **`~/.claude/settings.json` (user scope) only** — same `--setting-sources=user` reason
as above. Do not put them back in `.claude/settings.json`: in the CLI both scopes load, so they
would fire **twice** per event.

Because user scope applies to *every* project, the hooks call self-gating wrappers
(`scripts/luminos-hook-crg-update`, `scripts/luminos-hook-session-check`) that exit 0 unless the
current repo opts in (has `.code-review-graph/` or `scripts/luminos-verify`).

Two things that make hooks fail *silently*, both already paid for:
- Hooks run with `PATH=/usr/local/bin:/usr/bin`. `~/.local/bin` is added by `~/.zshrc`, which
  non-interactive shells never source. **Always use absolute paths.**
- **Hooks do not run at all under `claude -p`** (verified across every `--setting-sources` value),
  so headless runs can never prove a hook works. That is why both wrappers append to
  `~/.luminos-hooks.log`, and `luminos-verify` warns when a configured hook has never been observed
  running. Configured ≠ running; only the trace distinguishes them.

| Tool | When |
|------|------|
| `mempalace_search` | Before every task |
| `mempalace_add_drawer` | After major changes (wing: luminos-os, room: decisions) |
| `mempalace_kg_add` | After discovering a new system interaction/conflict |
| `mempalace_reconnect` | After any external CLI use |

**If MCP not connected:** note it explicitly. Fall back to `luminos-brain query` + grep. Never silently skip.

---

## 7. Agent Roles

| Agent | Best For | Start Command |
|-------|----------|---------------|
| **Claude Code** | Multi-file Go/Python, complex bugs, deep reasoning | `cd ~/luminos-os && claude` |
| **Gemini CLI** | Daily tasks, config, bash scripts, quick fixes (80%) | `cd ~/luminos-os && gemini --yolo` |
| **Antigravity** | Full feature builds, complex Qt/QML UI (100+ lines) | `antigravity chat "prompt"` |
| **Cowork** | Autonomous background tasks | Claude Desktop → Open ~/luminos-os |

**Claude Code settings:** `~/luminos-os/.claude/settings.local.json` (default Claude API — OpenRouter removed 2026-05-27, caused Signal 5 TRAP crashes)
**Local Nova routing (advanced):** `ANTHROPIC_BASE_URL=http://localhost:8080/v1 claude` — only when hive-daemon has loaded Nova.

---

## 8. Session Start Checklist

```bash
# 0. Read the single continue-from-here note (current goal/aim/state) — see §0.2
cat ~/luminos-os/HANDOFF.md

# 1. Context
cat ~/luminos-os/AGENTS.md
cat ~/luminos-os/LUMINOS_STATUS.md

# 2. Search — all three, every time
~/luminos-os/scripts/luminos-notes.sh search "<task topic>"
luminos-brain query "<task topic>"
# MCP: mempalace_search("<task topic>")

# 3. Find which docs cover this topic — search before assuming
grep -rl "<task topic>" ~/luminos-os/docs/ ~/luminos-os/*.md 2>/dev/null
# OR: MCP mempalace_search will surface the right doc in its results
# Read whatever it points to BEFORE touching any file.

# 4. If touching Go or Python
# MCP: code-review-graph — query target file before editing

# 5. Python/venv safety
luminos-brain safe "<action>"
```

**Domain doc routing (fallback if search returns nothing):**

| Working on | Read this first |
|---|---|
| HIVE / models / hive-daemon.py / inference | `docs/hive-brain.md` |
| Chrome / browser / GPU launcher | `docs/LUMINOS_HANDBOOK.md` Part 11 |
| Power / thermal / fan curve / EPP | `docs/LUMINOS_HANDBOOK.md` Part 4 |
| RAM daemon / eviction / HotSet | `docs/LUMINOS_RAM_ARCHITECTURE.md` |
| Go daemon internals / IPC / sockets | `docs/DAEMON_ARCHITECTURE.md` |
| Any architectural or config decision | `LUMINOS_DECISIONS.md` |
| Bugs — finding or fixing | `docs/BUGS.md` |

**Rule:** search first — grep or MemPalace will tell you where the detail lives. The table above is the fallback, not the first step. If search surfaces a doc you weren't expecting, read it.

---

## 9. System Config (active, on-disk)

**Rule: any row added or changed here MUST also be recorded in LUMINOS_DECISIONS.md.**

| Path | What it does | Why / Bug ref |
|------|-------------|---------------|
| `/etc/environment` | `KWIN_DRM_DEVICES=/dev/dri/card2` (KWin AMD-only). `__EGL_VENDOR_LIBRARY_FILENAMES=50_mesa.json` (force Mesa EGL globally — prevents NVIDIA EGL waking dGPU). `QT_LOGGING_RULES=kwin_libinput.warning=false` (suppress touchpad spam). | BUG-050, BUG-046c |
| `/etc/modprobe.d/nvidia.conf` | `NVreg_DynamicPowerManagement=0x02` (fine-grained DPM — GPU sleeps aggressively). `nvidia-drm modeset=1 fbdev=1` (KMS). | BUG-047: NVIDIA wasted 8W idle. ⚠️ **KNOWN CONFLICT:** DPM=0x02 keeps NVIDIA at P8/210MHz during light workloads (e.g. Chrome). See LUMINOS_DECISIONS.md. |
| `/etc/udev/rules.d/` | NVIDIA PCI auto power-off when idle. | BUG-047 |
| `~/.config/chrome-flags.conf` | `--ozone-platform=wayland` only. All GPU flags live in chrome-luminos. | BUG-058: global flags injected broken options on every launch. |
| `/usr/local/bin/chrome-luminos` | GPU picker (kdialog). AMD: Wayland+Vulkan+VAAPI (`radeon_icd.json`). NVIDIA: XWayland+Vulkan (`nvidia_icd.json`). Overrides `__EGL_VENDOR_LIBRARY_FILENAMES` for NVIDIA path. **Any Chrome task: read `docs/LUMINOS_HANDBOOK.md` Part 11 first.** | BUG-046 through BUG-062. |
| `~/.config/kwinoutputconfig.json` | `sharpness: 0.35`, `vrrPolicy: "Never"` | Intentional display tuning. |
| `~/.local/share/applications/google-chrome.desktop` | Routes all Chrome launches through `chrome-luminos`. | AUR entry bypassed GPU picker. |
| `~/.local/share/kio/servicemenus/luminos-gpu-*.desktop` | Dolphin right-click GPU picker for executables and .desktop files. | Universal GPU launcher (Decision 16). |
| `/etc/systemd/system/luminos-{ai,power,router,sentinel,ram}.service` | `RuntimeDirectoryPreserve=yes` on all five (shared `/run/luminos` no longer wiped when one daemon restarts). luminos-ram: + `RuntimeDirectory=luminos` (was undeclared) + caps `CAP_SYS_PTRACE CAP_SYS_NICE CAP_KILL` (process_madvise/kill/setpriority were EPERM). | BUG-065/066/067. ✅ Active since one-time restart 2026-06-12 (post-HOPE-training). |
| `/etc/sddm.conf.d/{luminos,hidpi,kde_settings}.conf` (`Current=breeze`) + `/usr/share/sddm/themes/breeze/theme.conf.user` (`background=…/Sugar-Candy/Backgrounds/Mountain.jpg`) | SDDM login theme switched Sugar-Candy → **Breeze** to match the KDE lock screen (same Breeze widgets + same Mountain wallpaper the lock screen uses). All conf.d files consolidated to `breeze`. Backup: `/etc/sddm-luminos.conf.bak-20260722` (moved OUT of conf.d). | DECISION 28. Reason: user wanted the login screen to match the lock screen ("use the KDE theme everywhere"). Lock screen can't load an SDDM theme, so the match was made by moving SDDM to Breeze. Revert: set `Current=Sugar-Candy` in luminos.conf. [CHANGE: claude-code \| 2026-07-22] |
| `/etc/NetworkManager/conf.d/dns-systemd-resolved.conf` + `/etc/resolv.conf` (→ symlink to `/run/systemd/resolve/stub-resolv.conf`, nameserver `127.0.0.53`) | Enables `systemd-resolved` as a **local caching DNS resolver**; NM hands upstream DNS (`192.168.2.1`) to resolved. Gives Windows-parity DNS caching (repeat lookups <1 ms, persistent). Backup: `/etc/resolv.conf.bak-20260722`. | DECISION 27. Reason: no local DNS cache made every new domain a 30–50 ms round-trip → "new pages load slower than Windows" (Chrome fix #3). Revert: rm the NM drop-in + `systemctl disable --now systemd-resolved` + restore resolv.conf from backup + restart NM. [CHANGE: claude-code \| 2026-07-22] |
| `~/.config/plasma-workspace/env/luminos-wallpaper-nothrottle.sh` | Exports `QTWEBENGINE_CHROMIUM_FLAGS=--disable-backgrounding-occluded-windows --disable-renderer-backgrounding` for the Plasma session. Stops KWin/QtWebEngine from throttling the `org.luminos.livewallpaper` web view to 0 fps when a window fully covers the desktop, so the plugin's "Freeze when a window covers the desktop" checkbox actually controls the behaviour (unchecked = keep animating). | BUG-081 / DECISION 31. Web wallpapers froze whenever any window was maximized regardless of the plugin setting. [CHANGE: claude-code \| 2026-07-23] |
| `~/.config/kdeglobals` (`[KDE] AutomaticLookAndFeel=false`, `AutomaticLookAndFeelOnIdle=false`) | Disables KDE's automatic Global-Theme switcher (kded module `lookandfeelautoswitcher`). That module re-applies a whole Look-and-Feel package — colours, icons, cursor, widget style, Plasma style, decoration — on a time-of-day schedule **and after 5 s of idle** (`AutomaticLookAndFeelOnIdle` defaults to **true**, so it must be written explicitly). It was reverting the Yaru look on every lock/resume. **Hard conflict with DECISION 30 — turning this back on silently undoes the Ubuntu look.** Backup: `~/.config/kdeglobals.bak-yaru-20260726`. | BUG-088 / DECISION 30 amendment. Revert: set both keys `true`. [CHANGE: claude-code \| 2026-07-26] |
| `/usr/share/icons/Yaru{,-dark}/index.theme` (`[Icon Theme] Inherits=Papirus,breeze,hicolor`) + `/etc/pacman.d/hooks/luminos-yaru-icons.hook` | Yaru ships `Inherits=Humanity,hicolor`; Humanity is not packaged for Arch, so every icon miss logged `Icon theme "Humanity" not found` (58× in one day) and fell straight to hicolor. **Edit this file with `scripts/luminos-icon-inherits.py`, never `kwriteconfig6`** — kwriteconfig6 sorts the groups and buries `[Icon Theme]` at line 651, but the freedesktop spec requires it to be the first group. The pacman hook re-applies the chain after every `yaru-icon-theme` upgrade (which restores the shipped file silently). Backups: `index.theme.luminos-bak`. | BUG-090. Revert: restore the `.luminos-bak` files and `rm` the hook. [CHANGE: claude-code \| 2026-07-26] |
| `~/.config/gtk-{3,4}.0/settings.ini` + `gsettings org.gnome.desktop.interface` (`icon-theme=Yaru`, `cursor-theme=Yaru`) and `~/.config/kdedefaults/kdeglobals` (`[Icons] Theme=Yaru`) | A Look-and-Feel apply rewrites the GTK files via the `kde-gtk-config` `gtkconfig` kded module and leaves them on `breeze-dark`; nothing put them back, so GTK apps stayed Breeze while Qt was already Yaru. `plasma-changeicons Yaru` exits 0 but does **not** update these — write them directly. `kdedefaults/kdeglobals` is the Look-and-Feel's own defaults file and sits on `XDG_CONFIG_DIRS`; it carried `breeze-dark`, a live disagreement with the user file. `luminos-ubuntu-persist` now re-affirms all of these and its final check fails if they drift. Backup: `kdedefaults/kdeglobals.bak-yaru-20260726`. | BUG-090 / DECISION 30. Revert: set the keys back to `breeze-dark`. [CHANGE: claude-code \| 2026-07-26] |
| `/etc/systemd/logind.conf.d/luminos-lidsleep.conf` (`HandleLidSwitch=suspend`, `HandleLidSwitchExternalPower=suspend`, `HandleLidSwitchDocked=ignore`) + `~/.config/powerdevilrc` (`[AC\|Battery\|LowBattery][SuspendAndShutdown] LidAction=1`, `AutoSuspendAction=1`, `AutoSuspendIdleTimeoutSec=900/600/300`) | Lid close suspends on AC **and** battery; idle also suspends at KDE's own shipped defaults. Replaces `luminos-nolidsleep.conf` (deleted) and the `99-luminos-lid.rules` + `luminos-lid.service` screen-blank pair (udev rule deleted; the unit is left installed but is now never triggered). **While Plasma runs, PowerDevil holds a `block` inhibitor on `handle-lid-switch`, so `powerdevilrc` is what actually fires — logind is only the SDDM/TTY fallback.** ⚠️ PowerDevil 6.7 reads `powerdevilrc`, **not** `powermanagementprofilesrc`, and the keys live in the **`[<profile>][SuspendAndShutdown]` subgroup** — writing them to a bare `[AC]` group parses fine and does nothing. Verify with `qdbus6 org.kde.Solid.PowerManagement /org/kde/Solid/PowerManagement/Actions/HandleButtonEvents org.kde.Solid.PowerManagement.Actions.HandleButtonEvents.lidAction` (returns the live int; `triggersLidAction` does **not** track config and always reads true). Backups: `backups/power-2026-08-02/`. | DECISION 38 / BUG-091. Reverses the 2026-06-03 `f8e00ab0` "keep everything running on lid close" policy at the user's request. Revert: restore the backup dir. [CHANGE: claude-code \| 2026-08-02] |
| `/etc/systemd/sleep.conf` | `SuspendState=freeze` (s2idle — this machine has no S3; `/sys/power/mem_sleep` is `[s2idle]` only) + `HibernateMode=platform shutdown`. Dead `SuspendMode=s2idle` line removed — systemd deleted that option and logged `Support for option SuspendMode= has been removed and it is ignored` twice on every suspend. | [CHANGE: claude-code \| 2026-08-02] |
| `/etc/pacman.conf` | `IgnorePkg = linux linux-headers nvidia-utils nvidia-open-dkms opencl-nvidia lib32-nvidia-utils lib32-opencl-nvidia` — pins the kernel + the version-locked NVIDIA driver set so `pacman -Syu` stays current on everything else but never does the risky kernel/NVIDIA-branch jump as a side effect. Backup: `/etc/pacman.conf.bak-20260721`. **To deliberately move kernel/NVIDIA: temporarily remove from IgnorePkg (or `pacman -Syu --ignore=` empty), upgrade, rebuild DKMS, verify dGPU true-0W gating, then re-pin.** | DECISION 26. Reason: installed driver 595.71.05 is heavily tuned (true-0W RTD3 gating, DPM=0x02); repo has 610.43.03 branch jump that can silently undo power tuning + Plasma 6.7 breaks custom KCMs. Level-0 of the safe-update ladder (see LUMINOS_DECISIONS.md). [CHANGE: claude-code \| 2026-07-21] |

---

## 10. File Map

### Go Daemons (`cmd/`)
| Path | Description |
|------|-------------|
| `cmd/luminos-ai/main.go` | Unix socket IPC — central routing daemon |
| `cmd/luminos-power/main.go` | EPP thermal, fan curve v5, beast mode, AC/battery |
| `cmd/luminos-sentinel/main.go` | Process security — CAP_SYS_PTRACE, /proc scan |
| `cmd/luminos-router/main.go` | .exe classifier — 80% rules + 20% ONNX fallback |
| `cmd/luminos-ram/main.go` | v3.0 — LIRS IRR, HotSet N=8, OnScreen guard, KWin D-Bus |

### HIVE
| Path | Description |
|------|-------------|
| `scripts/hive-daemon.py` | Port 8078 — routing, model lifecycle, inference |
| `src/hive/HiveChat.qml` | Main chat UI (max-width 720px) |
| `src/hive/HistorySidebar.qml` | Conversation history |
| `scripts/hive-start-model.sh` | Start llama-server with a model |
| `scripts/hive-idle-watchdog.sh` | Auto-kill llama-server after 5min idle |

### KCMs + Widgets
| Path | Description |
|------|-------------|
| `src/kcms/kcm_luminos_keyboard/` | Keyboard backlight (C++/QML, 7 modes) |
| `src/kcms/kcm_luminos_hive/` | HIVE AI settings KCM |
| `src/widgets/org.luminos.powerwidget/` | Power monitor Plasma widget |
| `src/widgets/org.luminos.ramwidget/` | RAM monitor Plasma widget |
| `src/widgets/org.luminos.monitorwidget/` | Full system monitor popup widget — feeds on `luminos-monitor stats` (2026-07-01, replaces konsole/btop hotkey window) |

### Scripts → `/usr/local/bin/`
| Script | Description |
|--------|-------------|
| `scripts/luminos-notes.sh` | SQLite knowledge base |
| `scripts/luminos-monitor` | System monitor v1.3: btop/nvtop/snapshot/watch/stats. dGPU sleep-guard (BUG-078) — reads runtime_status before nvidia-smi, never wakes a suspended GPU. `stats` = KEY=VALUE feed for monitorwidget. Meta+M/Ctrl+M → `watch` (was konsole+btop) |
| `scripts/luminos-display-hz` | Hz settings dialog (kdialog) |
| `scripts/luminos-60hz` / `luminos-120hz` | Direct Hz switch |
| `scripts/luminos-gpu-launch` | Single GPU launcher: styled QML picker, wakes NVIDIA PCI gate inline, routes NVIDIA via dgpu-exec gate (DECISION 25) |
| `scripts/luminos-train-mode` | ML training max-perf toggle: nvidia-powerd Dynamic Boost (55→88W) + 100% fan pin w/ keep-alive; `on [pgrep-pattern]`/`off`/`status` (BUG-069 interim) |
| `scripts/luminos-wine-uninstall` | Wine uninstaller — **hybrid: run the app's own uninstaller, then sweep by location.** Scans a prefix's Program Files for real apps; on pick it (1) finds & runs the app's own `uninstall*.exe`/`unins0*.exe` if present (the proper Windows path — `wine uninstaller` dialog was unreliable because the .exe is often a ghost, e.g. WinRAR's is gone), then (2) sweeps leftovers: Program Files[/(x86)], AppData Roaming+Local, Start Menu .lnk (user + ProgramData), the Wine-generated `~/.local/share/applications/wine/Programs/*` launcher [the icon the app's own uninstaller never cleans], and the registry Uninstall key. Shows the exact path list + confirm before sweeping. MetaTrader 5 hard-excluded (filtered from menu AND guarded at selection). `--list [prefix]` = headless candidate dump. App-menu entry: `luminos-wine-uninstall.desktop`. [CHANGE: claude-code | 2026-07-05] |
| `scripts/luminos-verify` | Post-upgrade health check (DECISION 26 L2). 5 sections: Go daemons · KCM plugins · dGPU gating (sysfs only, never wakes it) · fan/thermal · **[5] MCP tooling**. `--mcp` runs section 5 alone (wired to the SessionStart hook); `--quiet` prints only the PASS/FAIL line. Section [5] does a real MCP `initialize` handshake and hard-fails on duplicate registration, Arch rolling python, non-pyenv interpreter, editable install, missing binary, or no valid result. [CHANGE: claude-code \| 2026-07-25] |
| `scripts/luminos-train-ram` | ML training RAM-headroom toggle (CPU-side companion to train-mode): runtime swapfile `/swapfile.train` at low prio (NOT in fstab) + `vm.swappiness` 60→10 + optional memory-cgroup via `run`; `on`/`off`/`status`/`run -- <cmd>`. **Fully reverts on `off` — nothing permanent (no /etc, no fstab, no sysctl.d).** Fixes zram-only OOM during training (BUG-070). |

### Archive (DO NOT RESTORE)
`archive/windows-hive-2026/`, `archive/gtk4-ui/`, `archive/hyprland/`, `archive/stale-docs/`

---

## 11. Absolute Do-Nots

| Target | Reason |
|--------|--------|
| `.env` | Credentials — never touch |
| `data/hive.db` | Database — never touch |
| `TAG SCHEMA` in STATUS.md | Locked format — see LUMINOS_STATUS.md |
| `cmd/` Go daemons | Only touch when explicitly instructed |
| `hive-swap-server.py` (port 8079) | RETIRED — do not reference |
| `orchestrator.py` | RETIRED — do not reference |
| Tahoe macOS theme | White panel bugs — archived, do not restore |

---

## 12. Power & Thermal — Summary

Full detail: `docs/LUMINOS_HANDBOOK.md` Part 4.

**Fan curve v5 (ACTIVE, 2026-05-24):**
CPU/GPU: `30c:0%,40c:5%,45c:22%,50c:55%,60c:88%,70c:100%,80c:100%,90c:100%`
Mid fan:  `30c:0%,40c:0%,45c:15%,50c:37%,60c:59%,70c:70%,80c:88%,90c:100%`

**Thermal Burst Mode (ACTIVE, 2026-05-31):** When temp ≥ 52°C (below Zone1=60°C) and profile ≠ Performance, override fan curve to 100% (CPU/GPU) / 88% (mid) until chassis cools to 45°C (7°C drop from trigger). Safety timeout: 2 min. Cooldown: 30 min before re-triggering. Beast mode cancels burst.

**Adaptive Governor v4.1:** `cap = 1.8GHz + (load/100) × (hwMax − 1.8GHz)`, EMA α=0.3, iGPU dominance penalty ≤300MHz, 70/30 smooth, >150MHz threshold to write sysfs. RAM pressure: when avail < 20% + temp > 45°C, add up to +30% effective load to nudge cap down.

**Thermal zones (AC):** Hot=87°C→3GHz | Emergency=92°C→2GHz+Quiet | 5°C hysteresis on exits.
**Battery:** ZoneWarm=62°C→3.5GHz | ZoneHot=72°C→2.5GHz.

**EPP:** `power` always except beast mode (`performance`). Always call `setEPPAfterAsusctl()` with 350ms sleep — never write EPP immediately after asusctl.

---

## 13. Mandatory Update Protocol

### After every task
```bash
~/luminos-os/scripts/luminos-notes.sh add [TAG] "[summary]"
luminos-brain log "[summary]"
```
Tags: `[HIVE]` `[POWER]` `[GPU]` `[DISPLAY]` `[RAM]` `[SENTINEL]` `[ROUTER]` `[UI]` `[DOCS]` `[BUG]` `[AUDIT]`

### Doc trigger table — scan after every task

| File | Update when… |
|------|-------------|
| `LUMINOS_STATUS.md` | Any component status changes |
| `LUMINOS_DECISIONS.md` | Architectural/config decision made OR two settings found to conflict |
| `docs/BUGS.md` | Bug found or fixed |
| `AGENTS.md §9` | Any `/etc/` file changed |
| `AGENTS.md §12` | Fan curve, zone thresholds, or EPP policy changed |
| `AGENTS.md §14` | Open task completed or added |
| `docs/CODE_REFERENCE.md` | New file, deleted file, function signature changed |
| `docs/LUMINOS_HANDBOOK.md` | User-facing behaviour changed (power, display, Chrome, Wine, shortcuts) |
| `docs/DAEMON_ARCHITECTURE.md` | Daemon internals changed |
| `docs/LUMINOS_RAM_ARCHITECTURE.md` | luminos-ram changed |
| `HIVE_ARCHITECTURE.md` | HIVE stack changed |

### Never miss these

| What you did | Where it must go |
|---|---|
| Changed `/etc/modprobe.d/` | AGENTS.md §9 + LUMINOS_DECISIONS.md (include power/perf implications) |
| Changed `/etc/environment` | AGENTS.md §9 — what it overrides + side effects |
| Added/changed udev rule | AGENTS.md §9 + LUMINOS_DECISIONS.md |
| Made a sysfs write permanent | AGENTS.md §9 + LUMINOS_DECISIONS.md |
| Removed a flag from a launcher | BUGS.md — why it was wrong, what it broke |
| Disabled/enabled a service | LUMINOS_STATUS.md |
| Two settings conflict | LUMINOS_DECISIONS.md — both sides + tradeoff + cross-ref both bugs |
| Bug caused by a previous fix | BUGS.md — cross-reference the original fix that introduced it |

### Git commit format
```bash
git add -A && git commit -m "type(scope): description

Agent: [claude-code|gemini-cli|antigravity|cowork]
Task: [what was asked]" && git push origin main
```

---

## 14. Open Tasks

00. **BUG-086 — URGENT, user action required.** A live OpenRouter API key (`sk-or-98117e…`) sits in
    `.claude/settings1.json`, which is **tracked by git and already pushed to `origin/main`** on
    `github.com/vrapatel2002/luminos-os`. **Rotate the key at openrouter.ai first** — history
    rewriting is pointless while the credential is still valid. Then delete the file (it is a dead
    config that also re-adds the banned OpenRouter routing), and add `.claude/settings*.json` to
    `.gitignore`. Purging history needs `git filter-repo` + a force-push: user's decision only.
0a. Sentinel fine-tune: build training dataset (sentinel_*.jsonl, same pattern as nexus_*.jsonl), fine-tune MobileLLM-R1-140M, re-quantize INT8, THEN create `src/npu/npu_daemon.py` + `luminos-npu.service` (blocked 2026-06-10 by luminos-brain safe NO).
0c. **BUG-069**: fix luminos-power setGPUTGP — `nvidia-smi -pl` is a no-op on mobile (exit 0 despite "not supported"); TGP logs since 2026-06-03 were fiction. Use nvidia-powerd lifecycle + read-back verification. Interim: `scripts/luminos-train-mode` wraps the working mechanism (nvidia-powerd + fan pin) for training runs.
0b. Fix `luminos-brain safe` to output the actual REASON for a block — currently returns unrelated canned incident lines (e.g. KWin fullscreen crash note when asked about an NPU file), making NO decisions unreviewable.
1. Eye model download + wire vision route in hive-daemon.py
2. KDE right-click service menus for HIVE (kcm_luminos_hive.so already installed)
3. ydotool type-into-apps integration
4. ~~Firefox WhiteSur theme~~ — DROPPED 2026-06-11: all macOS theming (WhiteSur/MacTahoe) removed from system by user decision (BUG-068). Firefox not installed.
5. HIVE chat web panel (Flask localhost:7437)
6. Go orchestrator (replace Python hive-daemon.py)
7. Zone indicator Plasma widget
8. SDDM custom Luminos theme
9. **Offload-inference daemon coordination (DECISION 23)** — make luminos-power + luminos-ram offload-aware for running the 10.4B HOPE model via weight-streaming. (a) power: session-scoped pin of dGPU P0 + PCIe Gen4 x8 (link idles at Gen1=2.5GT/s under DPM=0x02 → ~8× bandwidth loss), revert after. (b) ram: exempt pinned weight region from MADV_PAGEOUT/zram + reserve ~5GB pinned budget in headroom math (avoid BUG-070 OOM) + drop swappiness for session. (c) shared start/stop signal so daemons react together. Blocked on model-side number: size of resident memory-block (CUDA-kernel) weights at 4-bit.

---

## 15. Emergency Recovery

Full reference with root causes: `docs/LUMINOS_HANDBOOK.md` Emergency Card.

| Symptom | Fix |
|---------|-----|
| Fans silent at 70°C+ | `sudo systemctl restart luminos-power` |
| HIVE not responding (SUPER+SPACE) | `pkill -f hive-daemon.py; pkill -f llama-server; SUPER+SPACE` |
| NVIDIA won't sleep (8W idle) | Check `/etc/environment` has `__EGL_VENDOR_LIBRARY_FILENAMES=...50_mesa.json` |
| Chrome GPU process dead / SwiftShader | Check `chrome://gpu` GL_RENDERER. If SwiftShader: verify `VK_ICD_FILENAMES=radeon_icd.json` in `/usr/local/bin/chrome-luminos`. Clear `~/.config/google-chrome/{GPUCache,GrShaderCache,ShaderCache}`. |
| Chrome NVIDIA path stutters (GL=NVIDIA confirmed but slow) | `nvidia-smi` — check pstate. P8/210MHz = `NVreg_DynamicPowerManagement=0x02` throttling GPU. Known conflict — see LUMINOS_DECISIONS.md. |
| Panel broken/white | `systemctl --user restart plasma-plasmashell` |
| KDE Settings can't find HIVE KCM | `kbuildsycoca6 --noincremental` |
| Display stuck at wrong Hz | `luminos-120hz` or `luminos-60hz` |
| KWin crash (blank screen) | `kwin_wayland --replace &` |
| Launcher blank/empty | Set `applicationsDisplay=1` in `plasma-org.kde.plasma.desktop-appletsrc` |

---

## 16. Reply Format (mandatory — end every response with this)

```
REPLY TO MANAGEMENT:
  - Task completed: [yes/no/partial]
  - What changed: [list files modified/created]
  - LUMINOS_STATUS.md updated: [yes/no]
  - Luminos Notes updated: [yes/no]
  - Ready for: [what comes next]
```

**Also required on EVERY response (see §0):** this reply started with its `Response N`
counter line, and `HANDOFF.md` was overwritten in place with the current goal/aim/state
(one file only — never a second handoff).
