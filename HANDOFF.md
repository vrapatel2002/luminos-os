# HANDOFF — 007 First Light: the black screen (BUG-138). FIXED, both halves.
# [CHANGE: claude-code | 2026-08-20] — Response 21
Last updated: 2026-08-20 — Response 21

**Read this whole file before touching anything.**

**The goal changed this turn.** Responses 18–19 were about whether the 007 method generalizes to
other games; that work is complete and its record is `docs/paper/GENERALIZATION.md`, with the
previous handoff at `git show 93a5c773:HANDOFF.md`. Per AGENTS.md §0.2 there is exactly **one**
HANDOFF.md and it is overwritten in place.

---

## Goal, in Shawn's words

> "Bro can you check whats wrong with 007 is just black screen with audio running of game but
> visual are just black? what is this and does this happen ?"

then, after the first fix landed:

> "hey but the game is still not fullscreen its windowed mode. and also its not running on nvidia
> gpu look why ?"

**He was right on the first count and the correction is the lesson of this turn: fixing the crash
is not the same as fixing the game.** I stopped at "0 swapchain failures" and called it done. The
game was still a window with a titlebar sitting next to the bar. Second count was a
misreading, but a completely reasonable one — see below.

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

### Then the correction — the second half of the fix

6. **KWin rule added**, `~/.config/kwinrulesrc` `[3]`: matched on the window **title**
   `Wine Desktop` (exact), `fullscreen=true fullscreenrule=2`, `noborder=true noborderrule=2`.
   Title, **not** `wmclass=steam_proton`, which would hit every Proton game. Old config saved as
   `~/.config/kwinrulesrc.bak-2026-08-20`. Reload: `qdbus org.kde.KWin /KWin reconfigure`.
7. **The launcher now DETECTS that rule** instead of assuming either size — `_NET_DESKTOP_GEOMETRY`
   (2880x1800) when it is in force, `_NET_WORKAREA` (2760x1800) when it is not. The two halves must
   agree or BUG-138 returns; this way **neither half can silently break the other**, and deleting
   the rule leaves a working-but-windowed game rather than a black screen.
8. **Verified by SCREENSHOT this time, not just by log counts** — full-bleed title screen, no
   titlebar, no bar, window `0,0 1440x900` logical = 2880x1800, swapchain 2880x1800, 0 failures,
   96% GPU.
9. **"Not running on NVIDIA" — measured, and it IS.** `nvidia-smi` lists `./007FirstLight.exe` at
   2074 MiB, 137 fds on `/dev/nvidia0`, `Gid: 948` (the DECISION 25 gate). What he actually saw was
   the game's own VRAM meter pegged **red at 2,059 MB**, because `jobhunt-llm.service` holds
   **3576 of the card's 6141 MiB** and the 4050's VRAM is *dedicated*. A game reporting 2 GB of
   VRAM looks exactly like an iGPU. **Open question for Shawn: stop `jobhunt-llm` while playing?**
   Not done — the launcher deliberately reports holders and does not act on them.

---

## IN PROGRESS

Nothing is mid-flight. Tree is consistent.

**Note:** a 007 process may still be running from the verification launch — `pkill -x
007FirstLight.e` if so. (The `comm` name truncates to 15 chars; `007FirstLight.exe` never matches.)

---

## Next steps

1. **Ask Shawn whether to stop `jobhunt-llm.service` while playing.** It holds 3576 of 6141 MiB and
   is why the game's VRAM meter is red. `sudo systemctl stop jobhunt-llm` frees it; it is a system
   unit, not `--user`. **His call, not mine** — the jobhunt pipeline is his actual goal.
2. **Re-verify `007 --igpu` once.** Not re-run since either change. It should now also come up
   fullscreen (the KWin rule is GPU-agnostic) at 2880x1800.
3. **Consider whether the KWin rule should be in the repo**, not just in `~/.config`. Right now it
   is live-only config with a `.bak` beside it and nothing in `scripts/` puts it there, so a
   fresh machine would get the windowed fallback silently.
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

- **"The error stopped" is not "the feature works." LOOK AT IT.** I reported this fixed on a log
  count of 0 without ever seeing the screen. The game was still windowed with a titlebar. One
  screenshot would have caught it before Shawn had to.
- **`spectacle` DOES work headless** — `spectacle -b -n -f -o out.png`. The earlier "spectacle
  produces nothing" note was wrong: it needs the live session's `WAYLAND_DISPLAY`,
  `XDG_RUNTIME_DIR` **and** `DBUS_SESSION_BUS_ADDRESS`, all three lifted out of
  `/proc/$(pgrep -x plasmashell)/environ`. `grim` still does not work (no wlr-screencopy).
- **`ffmpeg -f x11grab` gives a BLACK frame under KWin** — XWayland windows are redirected, so the
  X root is not composited. It looks precisely like the black-screen bug you are chasing. Do not
  use it to check for one.
- **A swapchain error is a window-size question first and a driver question last.** Six experiments
  went hunting a broken NVIDIA stack. One `xprop` call settled it.
- **A Wine virtual desktop is an ordinary window.** It gets a titlebar and honours the bar's
  exclusive zone. Fullscreen takes a KWin rule; nothing about `explorer /desktop=` implies it.
- **"It's not on the NVIDIA" was the VRAM meter, not the GPU.** The 4050's 6 GB is dedicated, so a
  resident LLM leaves the game ~2 GB and every in-game readout then looks like an iGPU. Check
  `nvidia-smi --query-compute-apps` and the fd count on `/dev/nvidia0` before believing the symptom.
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

- `~/re/tools/007-run.sh` — work-area/full-screen sizing with KWin-rule detection; `RES` block moved
  below session resolution; header comment and `--help` range updated. **Half 1 of the fix.**
- `~/.config/kwinrulesrc` — new rule `[3]`, fullscreen + noborder for `Wine Desktop`.
  **Half 2 of the fix.** Backup at `~/.config/kwinrulesrc.bak-2026-08-20`. **Not in the repo** —
  see Next Steps 3.
- `/usr/local/bin/007` — reinstalled from it, verified identical.
- `docs/BUGS.md` — BUG-138, full write-up + the same-day correction + the screenshot-tooling note.
- `HANDOFF.md` — this file, overwritten in place.
- `LUMINOS_STATUS.md` — bug line.
- Luminos Notes + brain log — one `[BUG]` entry.

### Untouched on purpose
- `docs/paper/*.tex` — blocked by standing instruction.
- `~/re/tools/007-try.sh` — it is a bisection harness for BUG-137 and is still correct for that.
- `~/.config/kwinrc`, Caelestia's bar config — the bar is not the bug, the assumption about it was.
