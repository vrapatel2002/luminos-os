# HANDOFF — 007 First Light: the black screen (BUG-138). FIXED.
# [CHANGE: claude-code | 2026-08-20] — Response 20
Last updated: 2026-08-20 — Response 20

**Read this whole file before touching anything.**

**The goal changed this turn.** Responses 18–19 were about whether the 007 method generalizes to
other games; that work is complete and its record is `docs/paper/GENERALIZATION.md`, with the
previous handoff at `git show 93a5c773:HANDOFF.md`. Per AGENTS.md §0.2 there is exactly **one**
HANDOFF.md and it is overwritten in place.

---

## Goal, in Shawn's words

> "Bro can you check whats wrong with 007 is just black screen with audio running of game but
> visual are just black? what is this and does this happen ?"

Two questions: what is it, and is it a recurring thing. Both are answered, and it is fixed.

---

## The short version

**The window was 120 pixels too small, and NVIDIA does not round.**

The launcher asked for a **2880x1800** virtual desktop — the panel's native mode. KWin can only
ever hand out **2760x1800**, because Caelestia's left bar reserves an exclusive zone of 60 logical
(= 120 physical) px. NVIDIA reports `minImageExtent == maxImageExtent == currentExtent` for a
surface, so the swapchain must match the window **exactly**; it rejected the request with
`VK_ERROR_UNKNOWN` and vkd3d-proton retried forever. Audio played, the GPU sat at 100%, and not a
single frame was ever presented.

`2880 − 2760 = 120`. That is the bar.

**"Does this happen?"** — yes, to any NVIDIA D3D12 title that asks for a window size the
compositor will not give it. It is **not** a relapse of BUG-137 (that was `assert=9 gpu=0%`, a
shader-compiler segfault; this is `assert=0 gpu=100%`).

---

## DONE this turn

1. **Root-caused by measurement.** One distinct error in a 42,599-line log, 894 times in 68 s:
   `dxgi_vk_swap_chain_recreate_swapchain_in_present_task: Failed to create swapchain, vr -13`.
   `vulkaninfo` proved the NVIDIA min==max==current extent behaviour; `xprop -root _NET_WORKAREA`
   returned `120, 0, 2760, 1800` against `_NET_DESKTOP_GEOMETRY` of `2880, 1800`.
2. **Fixed `~/re/tools/007-run.sh`** — `RES` now comes from `_NET_WORKAREA`, with the old sysfs
   `drm/modes` read kept as the fallback (Hyprland, bare TTY, no `xprop`). **The block had to move
   below the session-resolution code**, because `xprop` needs `DISPLAY` and the launcher may be
   started with no session in its environment.
3. **Installed to `/usr/local/bin/007`** and verified byte-identical.
4. **Verified end to end by running the real launcher**, not the harness: swapchain created at
   `2760 x 1800`, **0** `Failed to create swapchain` in 892k log lines, 98% GPU, 5800 MiB VRAM,
   and KWin reporting the window as `steam_proton 60,0 1380x900 'Wine Desktop'` — logical 1380x900
   = physical 2760x1800, matching the swapchain exactly.
5. **`docs/BUGS.md` — BUG-138 written up in full**, including the do-not-re-chase list.

---

## IN PROGRESS

Nothing is mid-flight. Tree is consistent.

**Note:** a 007 process may still be running from the verification launch — `pkill -x
007FirstLight.e` if so. (The `comm` name truncates to 15 chars; `007FirstLight.exe` never matches.)

---

## Next steps

1. **Ask Shawn whether the 60px strip of bar at the left edge bothers him.** The fix sizes the game
   to the work area, so the bar stays visible beside it. The upgrade, if he wants it, is a KWin
   window rule forcing the Wine Desktop window fullscreen — deliberately not done, see BUG-138's
   "alternative fix" section for the trade-off.
2. **Re-verify `007 --igpu` once.** It is expected to be unaffected (RADV clamps, and 2760x1800 is
   if anything more correct), but it was not re-run after the change.
3. Paper work — **still blocked on Shawn: "do not continue to write the old paper now."**
   Corrections for §4, §5, §6 and a new §13 are staged in `docs/paper/GENERALIZATION.md`.
4. Cheap: `drmcheck.py` over more clean PEs under `/mnt/win-os/Program Files`.
5. Rename `~/re/tools/007-mkproton.sh` → `mkproton.sh`. Verified game-agnostic.
6. Root-cause the Mia installer spin. Characterised, not fixed. Low priority — §6 gets the game.
7. Push. `fd8a82e0` and everything after is local only. **Never authorized — ask.**

---

## Key decisions & constraints

- **Do not write new `.tex` prose.** Standing instruction.
- **Do not push** without asking. Nothing in this line of work has ever been pushed.
- `docs/BUGS.md` BUG-138 is the record for this turn; this handoff is a pointer. Do not duplicate
  it here — there is one handoff and it gets overwritten.
- **Keep `/mnt/win-os/Games/ReturningToMia`** (3.0 MB, 0-byte `.rpa`). It is the evidence for the
  §5 installer failure, not junk.

---

## Gotchas & things NOT to redo

### From this turn (BUG-138)

- **A swapchain error is a window-size question first and a driver question last.** Six experiments
  went hunting a broken NVIDIA stack. One `xprop` call settled it.
- **A working second GPU is misleading here.** AMD rendered fine, which felt like proof the request
  was reasonable. It only proved RADV clamps and NVIDIA does not.
- **`007-try.sh` cannot test this fix.** The harness *reads* the prefix registry and never sets it;
  only the launcher writes `HKCU\Software\Wine\Explorer\Desktops`. Test with the installed `007`.
- **`vkcube --xcb` just prints usage** — the flag is `--wsi xcb`.
- Do NOT re-chase: driver mismatch (both 610.57.04), Xid/NVRM faults (none), VRAM pressure (freeing
  3.5 GB made it *worse*, 5362 failures), NVIDIA Reflex (586), PRIME offload vars (546), Lutris (it
  uses the `linux` runner and just execs `007`), `kwinrc` (dated Aug 14, predates the working runs).

### Carried forward, still true

- **Do NOT copy 007's `__EGL_VENDOR_LIBRARY_FILENAMES` pin to a native Linux game.** It removes
  Mesa's EGL and SDL can then create no window at all — even the *software* renderer dies. Use
  `SDL_VIDEODRIVER=x11 __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia` instead.
- **`pkill -f "…/ReturningToMia"` kills your own shell** — the pattern is in the agent shell's own
  command line. Use a bracket class or `pgrep | xargs kill`.
- **Lutris game configs are FLAT** (`game:`/`system:` at top level). The installer-script shape
  gives "This game has no executable set." Lutris must not be running when you write `pga.db`.
- **Try the paper's §6 before its §5.** §5 is 25 minutes to a zero-byte failure; §6 is 5 minutes to
  a working game.
- **Check for a shipped native Linux build before doing any graphics work.** Cheapest step in the
  whole method.
- **Output file size is a useless progress signal for unarc.** Use the read offset on the *input*:
  `/proc/<pid>/fdinfo/<fd>`. Flat RSS + `wchan` of `0` distinguishes a spin from slow work.
- **`eu-stack`/`gdb` need `sudo` here** — `ptrace_scope` is `1`.
- **`xwininfo`, `xdotool`, `wmctrl` are NOT installed.** `xprop` **is**, and it is how you read the
  work area. `spectacle` produces nothing headless and `grim` needs wlr-screencopy, which KWin has
  no — use `/opt/claude-desktop-legacy/resources/locales/kwin-portal-bridge windows` for geometry.
- **`clspatch.py` must run concurrently**, never statically.
- **SDL ignores `DISPLAY=:77`** and will use the Wayland session, so a test launch appears on
  Shawn's real desktop. Warn him first.
- **"Signature valid" does not mean "unprotected"**; **entropy does not find Denuvo**; **a string
  match is not a finding until you read the bytes around it.**
- **Do not say the Linux crack is "impossible."** Accurate: hard and unbuilt.
- **Answer the question that was asked.** Depth on request, not by default.
- `\verb` inside `\textbf{}` is fatal in LaTeX.

---

## Files touched

- `~/re/tools/007-run.sh` — work-area sizing; `RES` block moved below session resolution; header
  comment and `--help` range updated. **The fix.**
- `/usr/local/bin/007` — reinstalled from it, verified identical.
- `docs/BUGS.md` — BUG-138, full write-up.
- `HANDOFF.md` — this file, overwritten in place.
- `LUMINOS_STATUS.md` — bug line.
- Luminos Notes + brain log — one `[BUG]` entry.

### Untouched on purpose
- `docs/paper/*.tex` — blocked by standing instruction.
- `~/re/tools/007-try.sh` — it is a bisection harness for BUG-137 and is still correct for that.
- `~/.config/kwinrc`, Caelestia's bar config — the bar is not the bug, the assumption about it was.
