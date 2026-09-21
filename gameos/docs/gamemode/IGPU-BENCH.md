# docs/gamemode/IGPU-BENCH.md — Radeon 780M, measured not theorised
# [CHANGE: claude-code | 2026-09-20]
Measured on the G14 (GA403UU, Ryzen 7 8845HS, LPDDR5-6400 2x... see below), 2026-09-20.
Companion to FEASIBILITY.md, which estimated these numbers. **Three estimates were wrong.**

Tooling: no packages installed — `luminos-brain safe` returned **NO** for vkpeak/clpeak,
so purpose-built Vulkan compute microbenchmarks were written instead and live in
`tools/gamemode-bench/`. They build against the vulkan headers + glslc already present.

---

## 1. Results

| metric | value | notes |
|---|---|---|
| **FP32 burst peak** | **5.54 TFLOPS** | sclk pinned 2700 MHz, verified via hwmon `freq1_input` |
| **FP32 sustained (12s+)** | **3.88 TFLOPS** | **-30% vs burst** — this is the real number |
| **Achieved bandwidth** | **84.6 GB/s** | 83% of the 102.4 GB/s theoretical. Good efficiency. |
| Idle | 800 MHz, 11.2 W PPT, 55 C | |
| Sustained load | 2641-2700 MHz, **65 W PPT**, **95 C** | package power, CPU otherwise idle |
| Time to 95 C | **~7 seconds** | from a 55 C idle start, platform_profile=performance |

## 2. The dual-issue question, settled

FEASIBILITY.md §1 argued the 780M is ~4.15 TF plain and that the 8.29 TF figure is a
dual-issue (VOPD) peak games rarely approach. Both halves are now measured:

- 768 shaders x 2 FLOP x 2.70 GHz = **4.147 TF** plain, **8.294 TF** dual-issue.
- Burst measured 5.539 TF = **2.67 FLOP/shader/clock** = **67% VOPD utilisation**.
  So dual-issue *does* fire on friendly code — FEASIBILITY was slightly pessimistic
  calling 4.15 the realistic number for a synthetic.
- Sustained measured 3.882 TF = **1.91 FLOP/shader/clock** = **below the plain FMA rate.**
  Once thermals bite, the dual-issue advantage is entirely gone.

**The honest single number for this chip is 3.9 TF sustained, not 4.15, not 8.29.**

## 3. What changed vs FEASIBILITY.md

1. 🔴 **A 30% burst-to-sustained gap exists and was not predicted.** Any benchmark run for
   under a second on this chip reports ~5.5 TF and is lying about gameplay.
2. 🔴 **The iGPU pulls the package to 65 W and 95 C in 7 seconds, on its own, with the CPU
   idle and the dGPU asleep.** FEASIBILITY §2 argued on first principles that the iGPU
   "shares power, thermal budget and bandwidth with the CPU, so they slow each other down."
   That is now a measured 65 W, not an argument. On a chassis whose total budget is ~90-100 W
   shared with the 4050, **giving the iGPU render work during a game directly removes power
   and thermal headroom from the 4050 and from the CPU feeding it.**
3. ✅ Bandwidth confirmed as the binding constraint, and the 83% efficiency figure means
   there is no driver-side headroom to recover — 84.6 GB/s is what the bus gives.
4. ⚠️ LPDDR5 still configured **6400 MT/s against a 7500 MT/s rating** (re-confirmed via
   dmidecode). External roofline analysis of this same chip concludes memory speed is a
   higher-leverage lever than TDP; an extrapolated **+6-9% FPS** if 7500 were reachable.
   Whether AGESA/firmware allows it is **not investigated**.

## 4. Where it actually sits

| | sustained FP32 | bandwidth | VRAM |
|---|---|---|---|
| **Radeon 780M (measured)** | **3.88 TF** | **84.6 GB/s shared with CPU** | shared from 16 GB |
| RTX 4050 Laptop (AD107) | ~12 TF | 192 GB/s dedicated | 6 GB |
| PlayStation 5 | 10.28 TF | 448 GB/s unified | ~12.5 GB to games |

**The 780M is ~1/3 of the 4050 in sustained compute and 19% of a PS5's bandwidth.**
FEASIBILITY's headline holds and is strengthened: the PS5-class part in this laptop is
the 4050, and it is not close.

## 5. Real-game settings (external data — NOT measured here, no games installed)

Published 780M benchmarks, cross-checked across wccftech / ultrabookreview / xtgamer /
laptopmedia / Notebookcheck:

- **Esports + pre-2020 titles:** native 1080p High/Ultra, 60-200 fps. Fine.
- **2018-2021 AAA** (God of War 2018, RDR2, Forza Horizon 5, Doom Eternal, Miles Morales):
  Low/Medium at native 1080p or FSR Balanced → **60 fps is reachable**.
- **2022+ AAA** (Cyberpunk, Spider-Man 2, TLOU2, KCD2, Indiana Jones): 60 fps at native
  1080p is **not** reachable. Realistic target is **30 fps**, Low/Medium, internal render
  **540-900p** upscaled to 1080p output via FSR3/TSR Performance.
- **Ray tracing:** functional, not usable. Doom Eternal 45-50 fps is the best case;
  Spider-Man RT lands 20-35 fps.
- **Equivalent discrete part:** roughly **RTX 2050**; between GTX 1650 and RTX 3050.

So "it can run AAA at 1080p" is true only if 1080p means *output* resolution with a
540-900p internal render, at 30 fps, on Low/Medium. That is the honest version.

## 6. Method notes / gotcha for whoever re-runs this

**The first power measurement in this session was wrong and was caught before reporting.**
`bench` with RUNS=20 is ~145 ms of GPU work; sampling hwmon across it over 6 s of wall
clock returned 12-15 W, which is essentially the *idle* figure. Rebuilt with RUNS=2000
(~12 s of continuous load) the same chip reads **65 W**. Any power or thermal number taken
from a sub-second workload on this APU is idle-contaminated. See `tools/gamemode-bench/README.md`.

Also: `power1_average` read as empty/0 on one pass after the hwmon index shifted —
resolve the hwmon path dynamically (`ls /sys/class/drm/card2/device/hwmon/hwmon*/freq1_input`)
rather than hardcoding `hwmon5`.

## 7. Not yet measured

- Real game frame rates on this box — **no games are installed** (Steam library is empty).
- The 780M under load *while the 4050 is also loaded* — the number that actually decides
  whether any iGPU offload is affordable. Needs a game.
- Whether 7500 MT/s is reachable at all on this firmware.
