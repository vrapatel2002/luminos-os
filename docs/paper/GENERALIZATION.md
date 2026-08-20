# Does the 007 work generalize? — findings + resume point

**Status: IN PROGRESS, stopped 2026-08-20. Paper itself is DONE (19 pages).**

The question asked: *"we did it one game good but now real question is it
applicable to any or all other?"*

Answer so far, with evidence. Some of it **contradicts the paper** and the paper
needs a correction pass.

---

## The control we found: Black Myth Wukong

A second, fully installed title on `/mnt/win-os/Games/Black Myth - Wukong`
(140 GB). Same distributor (`FitGirl-Launcher.exe` is present). **Has Denuvo.**
This is the control §4 needed and never had.

Built `~/re/tools/drmcheck.py` — the whole §4 procedure as one reusable tool.
Negative-tested it against 007 first: it reproduces every number in the paper's
Table (64,228,744 B, md5 `3e0c3e10…`, 43 windows, 5.906–6.700, mean 6.505, 0
windows ≥ 7.5, stock sections). So the instrument is sound.

### Result on both titles

| Test | 007 (no Denuvo) | Wukong (Denuvo) | Discriminates? |
|---|---|---|---|
| Authenticode digest | **VALID** | **VALID** | **NO** |
| Windowed entropy ≥7.5 | 0 of 43 | **1 of ~680** | **NO** |
| Non-standard sections | none | **10** | **YES** |
| Protection strings | none | **`DENUVO`** | **YES** |
| File size | 64 MB | **728 MB** | **YES** |

### Finding 1 — the entropy test FAILED on a real Denuvo binary

Per-section, across 695 MB of a known-Denuvo executable, **exactly one 1 MiB
window out of ~680 crosses 7.5**. That is noise.

```
Wukong  .shared  263.2 MB  X  entropy 6.443  win>=7.5: 0
        .code    199.8 MB  -  entropy 6.031  win>=7.5: 1
        .xtls    198.0 MB  X  entropy 6.761  win>=7.5: 0
```

**§4 currently claims:** *"Had a virtualising layer been present, it would appear
as a contiguous run of windows well above 7.5."* **That is now empirically
false.** Denuvo's VM is ordinary x86 that interprets — it is not compressed and
not encrypted at rest, so it is not high-entropy. The `sokpacker` false-negative
caveat the paper cites turns out to apply directly to the one case that mattered.

→ **ACTION: demote entropy in §4 from "corroborating" to "was tried, did not
discriminate," and add this control table.** This makes the paper stronger, not
weaker — it is a measured negative result on a real protected binary.

### Finding 2 — the signature test answers a different question than §4 implies

Wukong's exe is **also** a valid, unmodified publisher build. The signature
validates. And Denuvo is right there in it.

So "signature valid" means **"nothing was removed"** — it does *not* mean
"unprotected." §4's chain of reasoning is:

> signature valid → nothing removed → if protection is not visible now, it was
> never there

That is still **logically sound**, but the load-bearing clause is *"if protection
is not visible now"* — which depends entirely on the **weak** tests, and one of
those two weak tests (entropy) just failed. The paper currently presents the
signature as sufficient on its own. It is not. It is necessary, and it needs a
*working* visibility test beside it.

→ **ACTION: rewrite the "Why this settles the question" block in §4 to make the
visibility test explicit, and cite Wukong as the case that proves the signature
alone is not enough.**

### Finding 3 — why the signature survives on a cracked Denuvo game

Because the crack never touches the exe. Wukong's countermeasure is the
hypervisor (§4 contrasting case), which sits *below* the game. 007's is a Steam
API DLL replacement, which sits *beside* it. Neither modifies the binary.

→ Useful generalisation: **repack cracks in this family are non-invasive to the
main executable.** That is why the signature method works at all on repacks, and
it is worth stating.

### Also fixed: a real bug in my own instrument

`drmcheck.py` originally hardcoded `.text` for the entropy profile. Wukong has
**no `.text` section at all** — its code is in `.code`/`.shared`/`.xtls`. The
entropy test silently did not run and printed nothing. Now falls back to the
largest `IMAGE_SCN_MEM_EXECUTE` section. Same class of silent failure as
everything in the paper's Table XV.

---

## Generalizability by layer — current assessment

| Paper section | Generalizes to | Confidence | Evidence |
|---|---|---|---|
| §3 malware triage | any Inno Setup installer | **High** | format-level, not title-level |
| §3 script carving | any Inno Setup installer | **High** | same |
| §4 signature test | any signed PE | **High** — but see Finding 2 | tested on 2 titles |
| §4 entropy | — | **Rejected** | failed on the one control |
| §4 sections/strings/size | any PE | **High** | 3-for-3 on Wukong |
| §5 `Global\` namespace fix | all ISDone/unarc repacks | **High, untested** | engine-level, not title-level |
| §5 `c:\arc.ini` fix | all ISDone/unarc repacks | **High, untested** | same |
| §6 reassembly method | all FitGirl repacks | **Medium-High, untested** | Wukong is one; worklists differ per title |
| §7 Optimus divide-by-zero | every D3D12 game on any Optimus laptop | **High** | hardware topology, nothing to do with 007 |
| §8 EGL vendor pin | this machine's config | **Low** (specific); class is general | — |
| §11 vkd3d-proton 3.0.1 | **every D3D12 game on NVIDIA under Proton** | **High by construction** | see below |
| §9 dialog-enumeration diagnosis | any Wine hang | **High** | technique, not fix |

### The graphics fix is game-agnostic by construction

Verified `~/re/tools/007-mkproton.sh` touches **nothing game-specific**. It
clones a Proton dir with `cp -al` and replaces exactly two files —
`d3d12.dll`, `d3d12core.dll` — in four arch directories. No 007 files, no
prefix contents, no per-title config. The name `007-` on the script is
misleading.

→ Therefore the fix applies to **any** D3D12 title that hits the same NVIDIA
SPIR-V compiler fault. Whether other titles *hit* that fault is untested —
we have no second D3D12 game installed on the Linux side.

→ **ACTION: rename `007-mkproton.sh` → `mkproton.sh`, it is a general tool.**

---

## Resume point — what to do next

1. **Correct §4 of the paper** with Findings 1 and 2, and add the two-title
   control table. This is the highest-value remaining work: it turns a
   single-case study into a case study with a control.
2. Add a short **"Generalization" section** (would become §13) covering the table
   above, honestly marking which rows are tested and which are reasoned.
3. Rebuild: `cd docs/paper && pdflatex main && pdflatex main`
   (currently 19 pages, 0 undefined refs, 5 minor overfull boxes).
4. Optional, cheap, high value: run `drmcheck.py` over more PEs to widen the
   control set — `HV-StartGame.exe` (the hypervisor loader), the Steam DLLs, and
   anything under `/mnt/win-os/Program Files`.
5. Optional, expensive: install a second D3D12 title on the Linux side to test
   whether the vkd3d-proton 3.0.1 result reproduces. This is the only way to
   move the §11 row from "high by construction" to "measured."

### Tools
- `~/re/tools/drmcheck.py` — §4 procedure on any PE. `drmcheck.py <exe> [exe…]`
- `~/re/tools/007-mkproton.sh` — Proton variant builder (game-agnostic)
- `~/re/tools/pescan.py` — older sections/entropy/imports dump

### Files
- `docs/paper/main.tex` + `sec1..sec13` — the paper, builds clean
- `docs/paper/007-first-light-linux-case-study.pdf` — 19 pages
