# docs/gamemode/REHEARSAL-01.md — first dress rehearsal: INVALID, and why
# [CHANGE: claude-code | 2026-09-20]
Run 19:06-19:13, 2026-09-20. Desktop stopped, Wukong run inside `cage`.
**The comparison is invalid. The harness broke the machine's swap mid-test.**

## What went wrong

The script ran `swapoff -a; swapon -a` to clear swap for a clean measurement.
**`/swapfile.luminos` never came back** — it is enabled by
`/usr/local/bin/luminos-pagefile`, **not** `/etc/fstab`, so `swapon -a` had nothing to
restore it from. The test therefore ran on **zram alone: 8 GB instead of 41 GB**, and
zram was pegged full (8191/8191 MB) for the whole gameplay window with system RAM
availability down to **1.35 GB**.

So two variables moved at once, in opposite directions:
- desktop removed (frees memory — the thing being tested)
- swap capacity cut 80% and exhausted (starves memory — an artefact of the bug)

Swap was restored manually afterwards; the machine is healthy. The harness has been
patched to **never touch swap** and to re-enable any missing device in its exit trap.

## Numbers anyway, marked as contaminated

| | baseline (desktop up, 41 GB swap) | rehearsal (desktop off, 8 GB swap) |
|---|---|---|
| avg FPS | 53.6 | **52.5** |
| median | 51.0 | 51.4 |
| 1% low | 37.9 | **34.0** |
| min | 15.4 | **1.6** |
| allocstall | 18,143 | **23,201** |
| pswpout | 4,232,545 | **2,284,971** |

## What is still valid, and worth keeping

1. 🟢 **The kiosk session model works.** `cage` + Lutris + Proton launched and ran the
   game with no desktop behind it, DualSense included. That is the VELA session shape
   validated end to end, and it cost nothing to learn.
2. 🟢 **`pci_dev=0000:01:00.0` fixed the MangoHud mis-attribution** from BMW-BENCH §5.
   MangoHud now reports the real 4050: *"Set renderD128 as active GPU (driver=nvidia
   id=10de:28e1)"*.
3. 🔴 **Real VRAM figure, correctly attributed: avg 5.56 GB, peak 5.69 GB of 6.14 GB —
   93% of the card.** At Medium, ray tracing OFF, 900p internal, DX11. Worse than the
   5.2 GB estimated earlier from nvidia-smi spot checks.
4. 🟡 **A signal worth chasing:** average FPS barely moved (53.6 → 52.5, -2%) *despite*
   the machine being far more memory-starved than baseline. GPU load averaged **89%**
   with VRAM at 93%. That points to **average frame rate being GPU/VRAM-bound at these
   settings, not RAM-bound** — while the *lows* did degrade (1% low 37.9 → 34.0, min
   15.4 → 1.6), which is where memory stalls actually show up.
   If that holds in a clean run, it splits the thesis: **a lighter OS buys frame-time
   consistency, not average frame rate.** That is still worth having — consistency was
   the stated goal — but it is a narrower claim than "the OS is what's holding us back."

## Re-run requirements

- Swap left completely alone (41 GB, both devices). Patched.
- Same scene, same settings, same duration.
- One variable only: desktop present vs absent.
- Compare `allocstall` and 1% low, not just average FPS.
