# HANDOFF — does the 007 method work on other games?
# [CHANGE: claude-code | 2026-08-20] — Response 18
Last updated: 2026-08-20 — Response 18

**Read this whole file before touching anything.**

The previous goal on this file was the Caelestia-on-KDE desktop. It is superseded, not
abandoned — that handoff is intact at `git show b4a9e48c:HANDOFF.md` (352 lines, "i want the
exact shell but not as shell", STEP A–D). Nothing here undoes any of it. Per AGENTS.md §0.2
there is exactly **one** HANDOFF.md and it is overwritten in place, so the goal field moved.

---

## Goal, in Shawn's words

> "WELL GREAT BUT ABOUT THE 007 CAN WE MAKE SURE IT DOES WORK FOR OTHER GAMES TOO ?"

The 007 First Light project produced a 19-page IEEE paper describing a method: triage a repack
for malware, prove whether it has DRM, fix the installer, reassemble the game by hand, and fix
the graphics. **The method was demonstrated once, on one game.** The question is whether it is a
method or an anecdote.

---

## Aim right now

**Documentation only.** Shawn's exact instruction this turn was *"read AGENTS.md / just update
the docs."* The findings below were all measured in earlier turns of this session; this turn
writes them down. **The test plan is NOT started** — he was offered it and chose docs instead.

---

## Why

Because three of the paper's own claims are wrong, and they were only found to be wrong by
running the method a second time against a control. A single case study cannot tell you which of
its steps were load-bearing and which were coincidence. A second title can. A third would be
better.

---

## Process

The method has been re-run against **Black Myth Wukong** as a control — a second fully installed
title from the same distributor, on `/mnt/win-os/Games/Black Myth - Wukong` (140 GB), which
**does** have Denuvo where 007 does not. Every §4 test was executed on both and compared. All of
it is written up in `docs/paper/GENERALIZATION.md`, which is the real document for this work —
this handoff is the pointer, not the record.

---

## DONE

- **The paper itself** — 19 pages, builds clean, committed `fd8a82e0`. **Not pushed.**
- **`~/re/tools/drmcheck.py`** — the entire §4 procedure as one reusable tool. Negative-tested
  against 007 first: reproduces every number in the paper's table. The instrument is sound.
- **Wukong confirmed Denuvo-protected** by four independent lines of evidence.
- **Three §4 claims falsified by measurement**, all recorded with numbers:
  1. **Entropy** — §4 claims a virtualised region shows a contiguous run of windows above 7.5.
     Measured: **1 window out of ~680 across 695 MB.** That is noise.
  2. **Odd section names** — false-positives on clean shipped software. Excel has `.detourc`,
     `.c2r`, `sdmprc`; RadeonSoftware has `.qtversi`.
  3. **Import table** — §4 claims a protected binary "cannot afford a full static import table."
     Backwards. Wukong 56 DLLs / 1178 symbols vs clean 007's 52 / 753.
- **Three tests survive, 6-for-6:** missing `.text` entirely, a read+write+execute section
  (Wukong's `.xtls` is 198 MB and RWX; five clean controls have **zero** RWX sections),
  protection strings, plus size as a soft prior.
- **How Denuvo integrates — measured, not described.** Entry point relocated out of the game and
  into `.xtls` (rva `0x2918eb40`); 6 TLS callbacks vs 007's 2, so it runs before `main`; `.code`
  is 199.8 MB flagged as **non-executable data** — that is VM bytecode, not code.
- **`Simplesvm.sys` verified end to end.** Windows kernel driver (subsystem 1), imports
  `ntoskrnl.exe` only, 47 functions, and the disassembly contains `vmrun` / `vmload` / `vmsave` /
  `stgi`. Mechanism is EPT/NPT split-view paging: instruction fetch gets the patched page, data
  read gets the original, so Denuvo's own hash check reads clean bytes.
- **Wukong has no anti-cheat** — proven, not assumed. All 8 candidate string hits read in context
  and all 8 are false positives (`bAntiCheatProtected` is a stock Unreal session field).
- **A third test title located** — `Returning to Mia`, 14 GB FitGirl repack in Downloads, and its
  install is stalled at 0 bytes in exactly the §5 failure mode.
- **Docs updated this turn:** `docs/paper/GENERALIZATION.md` gained Findings 4–8, the third-title
  section, the revised layer table, and a correction to my own overstatement.

---

## IN PROGRESS

Nothing is mid-flight. The docs are written and the tree is consistent.

---

## Next steps

1. **Test on `Returning to Mia`** — the only work that converts reasoned rows into measured ones.
   Read-only step first: `drmcheck.py` on its `setup.exe`, then carve the Inno script. Then apply
   the §5 fixes and re-run the install; if it stalls, do the §6 manual reassembly.
   **Needs Shawn's go-ahead — he deferred it once already.**
2. **Correct §4 of the paper** with all three falsified claims plus the control table. Highest
   value paper work. **Blocked on Shawn: he said "do not continue to write the old paper now."**
3. Add a "Generalization" section (§13) from the layer table in `GENERALIZATION.md`.
4. Cheap and useful: run `drmcheck.py` over more clean PEs under `/mnt/win-os/Program Files`.
   Every clean PE with zero RWX sections strengthens what is now the primary structural test.
5. Rename `~/re/tools/007-mkproton.sh` → `mkproton.sh`. It is game-agnostic by construction —
   verified: it `cp -al` clones a Proton dir and swaps exactly `d3d12.dll` + `d3d12core.dll` in
   four arch dirs. Nothing about 007 is in it.
6. Push. Commit `fd8a82e0` and everything after it are local only. **Never authorized — ask.**

---

## Key decisions & constraints

- **Do not write new `.tex` prose.** Standing instruction from Shawn: *"do not continue to write
  the old paper now."* Corrections are staged in `GENERALIZATION.md` on purpose.
- **Do not start the `Returning to Mia` test** without being asked. He was offered step 1 and
  chose docs instead.
- **Do not push** without asking. Nothing in this line of work has ever been pushed.
- `GENERALIZATION.md` is the record. This handoff is a pointer to it. Do not duplicate its
  contents here — per AGENTS.md there is one handoff and it gets overwritten, so anything only
  written here is one response away from being gone.

---

## Gotchas & things NOT to redo

- **"Signature valid" does not mean "unprotected."** It means "nothing was removed." Wukong's
  exe is a valid, unmodified publisher build **with Denuvo in it**. Both titles validate. The
  signature is necessary, never sufficient.
- **Entropy does not find Denuvo.** Do not re-run it hoping for a different answer. Denuvo's VM
  is interpreted x86-like bytecode — not compressed, not encrypted at rest, so it looks like
  ordinary code. This is a measured negative result, not a tooling failure.
- **A string match is not a finding until you read the bytes around it.** Eight anti-cheat hits,
  eight false positives. Same discipline the malware triage in §3 uses.
- **`drmcheck.py` used to hardcode `.text`.** Wukong has no `.text`, so the entropy test silently
  ran on nothing and printed nothing. Fixed — falls back to the largest executable section. Same
  silent-failure class as everything in the paper's Table XV.
- **`capstone` and `ndisasm` are not installed.** Use
  `objdump -D -b binary -m i386:x86-64 -M intel` on an extracted section blob. It linear-sweeps,
  so trust it at a known boundary (offset 0) and not mid-stream.
- **Do not say the Linux crack is "impossible."** I did, and Shawn caught it. Accurate version:
  the *existing tool* cannot work (it is a Windows kernel PE importing `ntoskrnl.exe`, and Wine
  translates programs, not drivers). A Linux equivalent is *conceivable* — patch KVM's NPT fault
  handler; the hardware is right here (`svm` flag, `kvm_amd` loaded, nested=1). It is unbuilt
  because of VM-in-a-VM detection, fingerprinting, and muxless-Optimus passthrough — and because
  the audience is on Windows. **Hard and unbuilt, not physically impossible.**
- **Do not volunteer anti-cheat analysis for a single-player game.** I did; Shawn pushed back and
  he was right. The measurement that followed confirmed zero anti-cheat.
- **Answer the question that was asked.** Twice this session I answered a conceptual "why" with
  PE anatomy and disassembly. Both times it was unwanted. Depth on request, not by default.
- `\verb` inside `\textbf{}` is fatal in LaTeX — the `%` gets eaten as a comment.

---

## Files touched

- `docs/paper/GENERALIZATION.md` — Findings 4–8, third-title section, revised layer table,
  corrected wording, specimen list. **The main artefact of this turn.**
- `HANDOFF.md` — this file, overwritten in place; goal moved from Caelestia to the 007
  generalizability question. Prior contents preserved at `git show b4a9e48c:HANDOFF.md`.
- `LUMINOS_STATUS.md` — research-track status line.
- Luminos Notes + brain log — one `[DOCS]` entry.

### Untouched on purpose
- `docs/paper/*.tex` — blocked by standing instruction.
- `~/re/tools/drmcheck.py` — already correct; no changes needed this turn.
- `/home/shawn/Games/Returning to Mia/` — test deferred, nothing written to it.
