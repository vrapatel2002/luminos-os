# HANDOFF — does the 007 method work on other games?
# [CHANGE: claude-code | 2026-08-20] — Response 19
Last updated: 2026-08-20 — Response 19

**Read this whole file before touching anything.**

Same goal as Response 18. What changed: the deferred test **ran**, and it moved the answer from
"reasoned" to "measured." The Caelestia desktop handoff is still intact at
`git show b4a9e48c:HANDOFF.md`. Per AGENTS.md §0.2 there is exactly **one** HANDOFF.md and it is
overwritten in place.

---

## Goal, in Shawn's words

> "WELL GREAT BUT ABOUT THE 007 CAN WE MAKE SURE IT DOES WORK FOR OTHER GAMES TOO ?"

The 007 First Light project produced a 19-page IEEE paper describing a method: triage a repack
for malware, prove whether it has DRM, fix the installer, reassemble the game by hand, fix the
graphics. It was demonstrated once, on one game. The question is whether it is a method or an
anecdote.

---

## Aim this turn

> "read AGENTS.md / read HANDOFF.md / and start testing the mia"

That was the go-ahead for the test deferred last turn. **It is done.** The answer is now
partly measured instead of entirely reasoned, and it is not the answer the paper predicts.

---

## The short version

**It is a method — but not the method the paper describes.**

Three titles now. Across them the paper's "normal path" (§5, fix the installer and let it run)
has worked **zero** times. The "fallback" (§6, bypass `setup.exe` and drive `unarc.dll` directly)
has worked **twice**. Returning to Mia was the clean A/B — the only title where both paths were
actually available — and the normal path lost.

---

## DONE this turn — the Mia test, in order

1. **§3 malware triage — PASSES, and generalizes better than claimed.** 11 of 11 comparable
   payload files are **byte-identical** to 007's already-triaged set. `host.cmd` identical;
   `arc.ini` differs in 2 cosmetic lines; 3 new files all attributed and benign. So triage is a
   **delta problem** — run it once per toolchain version, not once per game.
2. **§4 on `setup.exe` — the strong test is unavailable.** No Authenticode at all. Entropy 6.482
   flat, 0 RWX sections, no protection strings; `.itext` is one more false positive for Finding
   5's pile. Verdict clean, but on weak evidence only.
3. **Payload verified intact BEFORE blaming anything** — all 7 bins md5-match FitGirl's manifest,
   14 GB. This is what makes the rest of the finding trustworthy.
4. **§5 installer path — FAILED.** Clean prefix, both fixes armed, 25 minutes, **0 bytes.**
   Reproduced the original stall exactly. Ruled out: payload, `{app}` substitution, prefix arch,
   missing DLLs, under-patching (clspatch caught 10 runtime helpers at byte offsets *identical*
   to 007's).
5. **It is a THIRD failure mode.** §5's differential table describes two; this is neither. Read
   offset on `fg-01.bin` frozen at **byte 31**, RSS flat, main thread in `NtWaitForSingleObject`,
   a worker spinning in `NtFreeVirtualMemory`, srep helper **never spawned.**
6. **§6 direct path — SUCCEEDED.** All 7 containers rc=0. 18 GB. `fg-01` → a 17,217,543,459-byte
   `.rpa` in 5m20s, validated `RPA-3.0 … Made with Ren'Py.` Same `unarc.dll`, same helpers — so
   the defect is in the ISDone/Inno layer **above** unarc.
7. **§7–§12 are unnecessary, not untested.** The title ships a **native Linux build**. Ran it:
   `Ren'Py 8.3.3.24111502`, gl2, `AMD Radeon 780M (radeonsi, phoenix, ACO)`, Mesa 26.1.6, no
   traceback. Five seconds of `ls` deleted six sections of work.

8. **§8's EGL vendor pin is falsified as a general technique** (Finding 15). It selects the dGPU
   for 007 and **breaks Mia outright** — gl2, gles2 *and the software renderer* all die with
   `Invalid window`. The software path failing is the tell: no window was ever created. Pinning
   the vendor removes **Mesa's** EGL, and SDL's Wayland backend needs it to negotiate a surface
   with a compositor running on the AMD card. Wine/Proton doesn't care because it makes its own
   window first. Working route for native titles is the older GLX offload:
   `SDL_VIDEODRIVER=x11 __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia`.

## DONE this turn — the game is now launchable

- **`/usr/local/bin/mia`** — launcher in the shape of `/usr/local/bin/007`. Defaults to the
  **AMD 780M** (deliberately unlike 007: this is a 2D visual novel, waking the 4050 buys nothing
  and costs RTD3 residency). `mia --nvidia` uses the GLX offload route through `dgpu-exec-v2`,
  which is mandatory under DECISION 25. Both paths verified by reading the renderer out of the
  game's own `log.txt`.
- **Lutris entry added** — `~/.config/lutris/games/returning-to-mia.yml` (**flat** `game:`/
  `system:` shape, not the installer-script shape) + row id 3 in `pga.db`. It wasn't there for
  the boring reason: nothing had ever added it. `lutris -l` confirms.

## DONE this turn — tooling

- **`~/re/tools/fginstall.sh`** — game-agnostic §5 path. `-s setup.exe -t target`. Carves
  `arc.ini` out of the installer itself, arms `clspatch.py`, maps `E:` to the target's **parent**
  (Inno is unreliable given a bare drive root as `/DIR`).
- **`~/re/tools/fgextract.sh`** — game-agnostic §6 path, the one that works.
  `-r repack-dir -o out-dir 01 02 …`. Stages the repack's **own** helpers so the test stays honest.
- Both generalized from the `*007*` originals with nothing title-specific left in them.

## DONE this turn — docs

- `docs/paper/GENERALIZATION.md` — **the record.** Findings 9–14, a rewritten layer table
  (measured rows, not reasoned ones), the tooling and technique notes, corrected resume point.

---

## IN PROGRESS

Nothing is mid-flight. Tree is consistent.

---

## Next steps

1. **Correct §5 and §6 of the paper.** Now the highest-value paper work, ahead of the §4
   corrections, because it changes what a reader is told to *do*: recommend §6 first, add the
   third failure mode, add the native-build check before §7.
   **Blocked on Shawn: "do not continue to write the old paper now."**
2. **Correct §4** with Findings 1, 2, 4, 5 and now 10. Same block.
3. §13 "Generalization" section from the layer table. Same block.
4. Cheap: `drmcheck.py` over more clean PEs under `/mnt/win-os/Program Files`. Every clean PE
   with zero RWX strengthens what is now the primary structural test.
5. Rename `~/re/tools/007-mkproton.sh` → `mkproton.sh`. Verified game-agnostic.
6. Root-cause the Mia installer spin. Characterised, not fixed. **Low priority — §6 gets the
   game anyway.**
7. Push. `fd8a82e0` and everything after is local only. **Never authorized — ask.**

---

## Key decisions & constraints

- **Do not write new `.tex` prose.** Standing instruction. Corrections are staged in
  `GENERALIZATION.md` on purpose.
- **Do not push** without asking. Nothing in this line of work has ever been pushed.
- `GENERALIZATION.md` is the record; this handoff is a pointer. Do not duplicate it here —
  there is one handoff and it gets overwritten, so anything only written here is one response
  away from being gone.
- **Keep `/mnt/win-os/Games/ReturningToMia`** (3.0 MB, 0-byte `.rpa`). It looks like junk. It is
  the evidence for the §5 failure.

---

## Gotchas & things NOT to redo

- **Do NOT copy 007's `__EGL_VENDOR_LIBRARY_FILENAMES` pin to a native Linux game.** It removes
  Mesa's EGL and SDL can then create no window at all — even the *software* renderer dies. Use
  `SDL_VIDEODRIVER=x11 __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia` instead.
- **`pkill -f "…/ReturningToMia"` kills your own shell** — the pattern is in the agent shell's own
  command line. Use a bracket class (`py3-linux[-]x86_64/…`) or `pgrep | xargs kill`. Cost me a
  truncated test run and a bogus exit 144.
- **Lutris game configs are FLAT** (`game:`/`system:` at top level). The installer-script shape
  gives "This game has no executable set." Same trap 007 hit. Lutris must not be running when
  you write `pga.db`; back it up first.
- **Try §6 first.** §5 is 25 minutes to a zero-byte failure; §6 is 5 minutes to a working game.
- **Check for a shipped native Linux build before doing any graphics work.** `ls` the game dir
  for `lib/py3-linux-*` or similar. This is the cheapest step in the whole method.
- **Output file size is a useless progress signal for unarc.** It creates the target at full or
  zero size and fills it out of order. The real signal is the *read offset on the input*:
  `/proc/<pid>/fdinfo/<fd>` for the fd on `fg-01.bin`. That is what exposed the byte-31 freeze.
  Flat RSS + `wchan` of `0` distinguishes a spin from slow work.
- **`eu-stack`/`gdb` need `sudo` here** — `/proc/sys/kernel/yama/ptrace_scope` is `1`.
- **`xwininfo`, `xdotool`, `wmctrl` are NOT installed**, so §9's dialog-enumeration technique is
  unavailable. Go to thread stacks instead.
- **Verify the payload before blaming the installer.** md5 the bins first. It is the single most
  common confound and it costs one command.
- **`clspatch.py` must run concurrently**, never statically — the installer re-materialises fresh
  unpatched helpers at runtime.
- **SDL ignores `DISPLAY=:77`** and will use the Wayland session, so a test launch appears on
  Shawn's real desktop. Warn him first.
- **"Signature valid" does not mean "unprotected"** — and on repack installers there is often no
  signature at all, so the test does not even run.
- **Entropy does not find Denuvo.** Measured negative result, not a tooling failure.
- **A string match is not a finding until you read the bytes around it.**
- **Do not say the Linux crack is "impossible."** Accurate: the *existing tool* cannot work
  (Windows kernel PE importing `ntoskrnl.exe`; Wine translates programs, not drivers). A Linux
  equivalent is conceivable — patch KVM's NPT fault handler. **Hard and unbuilt, not impossible.**
- **Answer the question that was asked.** Depth on request, not by default.
- `\verb` inside `\textbf{}` is fatal in LaTeX.

---

## Files touched

- `docs/paper/GENERALIZATION.md` — Findings 9–14, rewritten layer table, tooling + technique
  notes, corrected resume point. **The main artefact of this turn.**
- `~/re/tools/fginstall.sh`, `~/re/tools/fgextract.sh` — new, game-agnostic.
- `HANDOFF.md` — this file, overwritten in place.
- `LUMINOS_STATUS.md` — research-track status line.
- Luminos Notes + brain log — one `[RESEARCH]` entry.

### Untouched on purpose
- `docs/paper/*.tex` — blocked by standing instruction.
- `~/re/tools/drmcheck.py`, `clspatch.py` — already correct; needed no changes for a third title,
  which is itself a small piece of evidence for generalizability.
