# HANDOFF — BUG-141 FIXED: the GPU is arbitrated, 007 takes the card and gives it back
# [CHANGE: claude-code | 2026-08-25] — Response 3
Last updated: 2026-08-25 — Response 3

**Read this whole file before touching anything.**

Per AGENTS.md §0.2 there is exactly **one** HANDOFF.md, overwritten in place. The previous version
(Response 1, the BUG-141 *diagnosis*) is at `git show HEAD:HANDOFF.md` once this is committed;
the BUG-138 handoff before it is at `git show 73395885:HANDOFF.md`.

---

## Goal, in Shawn's words

Turn 1:

> "the game 007 is not launching right now dont know the problem i think it with vram things we have
> done many things like server the dolphin in mobile phone things and lot more so can you find out
> what the problme is and why is it not launching?"

Turn 2, after I made the mistake of handing him a menu of three options instead of a fix:

> "hey it should be simple i want to use game free the vram for game. i am done with game give it
> back to dolphin. and also solve the 007 bug asap bro. and make it run on vram just as i said."

That is a complete specification: **automatic both ways, on the dGPU, no extra command to remember.**
It is now built and it works.

---

## The short version

`llama-server` — Dolphin-8B at `--ctx-size 16384`, the model that answers his phone — held **5718 of
the RTX 4050's 6141 MiB**. The 4050's memory is *dedicated*; unlike the 780M it does not borrow from
system RAM, so what the LLM takes is simply gone. Vulkan offered the game a device-local heap
`budget` of **61.75 MiB** against the ~2100 MiB it needs, and it died during device setup.

**`scripts/luminos-gpu-yield` now arbitrates the card.** `007` parks the model before Proton and
gives it back when the game exits. Nothing else to type.

---

## DONE this turn

1. **`scripts/luminos-gpu-yield`** — new, installed to `/usr/local/bin/luminos-gpu-yield`.
   `status` / `yield` / `restore` / `run -- CMD…`.
2. **`~/re/tools/007-run.sh`** — NVIDIA branch yields + `trap`s restore; `--keep-model` opts out;
   low-VRAM warning promoted from stdout to `notify-send`. Installed to `/usr/local/bin/007`.
3. **Verified live, both directions.** Numbers in Next-steps-free detail below.
4. **`docs/BUGS.md` BUG-141 → FIXED**, with the full design rationale and measurements.
5. **`LUMINOS_DECISIONS.md` DECISION 81** — why an arbiter, and why the two obvious alternatives lose.
6. **`AGENTS.md`** — §9 rows for both `/usr/local/bin` entries, §10 File Map row for the new script.

### The measurements (do not re-run these to confirm; they are the record)

| | |
|---|---|
| yield | 73 MiB → **5799 MiB free in ~1 s** |
| game on card | **3303 MiB**, **99% GPU**, **54.56 W**, **0 swapchain failures** |
| looked at it | screenshot = full-bleed 007 title screen, no titlebar, no bar. BUG-138 intact |
| restore | Dolphin answering `/health` **~3 s** after exit |
| restore fidelity | argv **byte-identical** (`cmp` clean), same model, same `--ctx-size 16384` |
| phone path | live `/v1/chat/completions` returned `back online` |

---

## IN PROGRESS

Nothing is mid-flight. The feature is complete and verified.

---

## Next steps

1. **Notes + brain entries** if they did not land this turn — check before re-adding, do not double-log.
2. **Push. Nothing in this line of work has ever been pushed — never authorized, ask first.**
3. `007 --igpu` is still **unverified since the BUG-138 fullscreen work**. Carried from two handoffs
   ago. It is now the documented fallback in DECISION 81, so it should actually be tested once.
4. Consider whether the BUG-138 KWin rule belongs in the repo rather than living only in
   `~/.config/kwinrulesrc`, where a profile reset would silently delete it.
5. Carried over, still true: paper work **blocked on Shawn** ("do not continue to write the old paper
   now"); corrections staged in `docs/paper/GENERALIZATION.md`.

---

## Key decisions & constraints

- **Do not write new `.tex` prose.** Standing instruction.
- **Do not push** without asking.
- **The arbiter's one rule: never fail to give the card back.** If you touch `luminos-gpu-yield` or
  the launcher's yield block, that is the property to preserve. A model that never returns is a worse
  failure than a game that never starts, because the first one is silent.
- `docs/BUGS.md` BUG-141 and `LUMINOS_DECISIONS.md` DECISION 81 are the records for this turn; this
  handoff is a pointer, not a copy.

---

## Gotchas & things NOT to redo

### From this turn (BUG-141 / DECISION 81)

- **Restore must replay the saved argv, not a model alias.** Calling `hive-start-model.sh nexus`
  would restore whatever that script hardcodes *today*, at the context it hardcodes *today* — a
  session running a different model or a different `--ctx-size` would come back as something else
  with nothing to indicate a substitution happened. `/proc/<pid>/cmdline` is the only honest record.
  Save it NUL-separated, read it with `mapfile -t -d ''` so arguments with spaces survive.
- **A dead process is not freed VRAM.** The pid leaving the process table and the driver reclaiming
  its allocations are two separate events. Poll the card; do not sleep a magic number.
- **`pkill -f llama-server` matches the arbiter itself** — the string is in its own argv and in its
  state file path. Always `-x` on the exact comm.
- **comm truncates at 15 characters**, so `pgrep -x 007FirstLight.exe` never matches and
  `007FirstLight.e` does. This one costs an hour if you do not know it.
- **`proton run` can return while the game is still running** — hence the `pgrep` wait loop. And the
  launcher **must not `exec`**, or there is no process left alive to run the restore trap.
- **`nvidia-smi` free memory and the Vulkan heap budget are different numbers, and only the second
  one decides whether an app starts.** Read `budget` under `memoryHeaps[0]` in `vulkaninfo`.
- **A 3-line `last-run.log` is a signal, not a missing log.** A working run is tens of thousands of
  lines; stopping right after `wineserver: NTSync up and running!` locates the failure *before* the
  renderer, which is what separates an allocation failure from BUG-137/138.
- **Check the commit log of the last five days before theorising.** `38e9c794`'s message named this
  outcome in advance — faster than any measurement, and it pointed straight at the cause.
- **He said "I think it's the VRAM" and he was right.** Verify the user's own hypothesis first; it
  costs one command and he knows his machine.
- **`nvidia-smi` needs `dgpu-exec` / `dgpu-exec-v2`** or it returns `Failed to initialize NVML:
  Insufficient Permissions` (DECISION 25 gate, gid 948). v2 for shell wrappers (BUG-102).
- **Do not tune `--ctx-size` to fix VRAM contention with a game.** Dolphin-8B's weights alone are
  ~4.6 GB — no context value leaves 2 GB. Disproved once, in BUG-141; do not spend a session on it.
- **When he has already stated the outcome he wants, build it — do not present three options.**
  Response 1 offered a menu and the reply was "hey it should be simple". The diagnosis was right and
  the delivery was wrong.

### Carried forward, still true

- **"The error stopped" is not "the feature works." LOOK AT IT.** Screenshot before claiming a fix.
- **A swapchain error is a window-size question first and a driver question last** (BUG-138).
- **Do NOT copy 007's `__EGL_VENDOR_LIBRARY_FILENAMES` pin to a native Linux game** — it removes
  Mesa's EGL and SDL can then create no window at all. Use
  `SDL_VIDEODRIVER=x11 __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia`.
- **`007-try.sh` cannot test launcher fixes** — the harness reads the prefix registry and never
  writes it. Test with the installed `/usr/local/bin/007`.
- **`spectacle` works headless** (`spectacle -b -n -f -o out.png`) only with `WAYLAND_DISPLAY`,
  `XDG_RUNTIME_DIR` **and** `DBUS_SESSION_BUS_ADDRESS` lifted from `plasmashell`'s environ. `grim`
  does not work (no wlr-screencopy). **`ffmpeg -f x11grab` returns a BLACK frame** under KWin — it
  looks exactly like the black-screen bug you would be chasing.
- **`xwininfo`, `xdotool`, `wmctrl` are NOT installed.** `xprop` is.
- **`eu-stack`/`gdb` need `sudo` here** — `ptrace_scope` is `1`.
- **Answer the question that was asked.** Depth on request, not by default.

---

## Files touched

- `scripts/luminos-gpu-yield` — **new**, the arbiter. Installed to `/usr/local/bin/`.
- `~/re/tools/007-run.sh` — yield/restore wiring, `--keep-model`, `notify-send` warning.
  Installed to `/usr/local/bin/007`.
- `docs/BUGS.md` — BUG-141 flipped to FIXED, full write-up + header summary.
- `LUMINOS_DECISIONS.md` — DECISION 81.
- `AGENTS.md` — §9 System Config (2 rows), §10 File Map (1 row).
- `HANDOFF.md` — this file, overwritten in place.

### Untouched on purpose
- `scripts/hive-start-model.sh` — lowering `--ctx-size` does not fix this and the phone service works.
  The arbiter deliberately does **not** go through it (see the argv gotcha above).
- The `--igpu` branch of the launcher — the 780M uses shared system RAM and has never contended.
- `docs/paper/*.tex` — blocked by standing instruction.
