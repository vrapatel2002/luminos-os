# docs/gamemode/MEMORY-STRATEGY.md — can we do what a console does?
# [CHANGE: claude-code | 2026-09-20]
Follows BMW-BENCH.md, which found system RAM (not VRAM) to be the binding constraint.
Question asked: consoles run modern AAA under 16 GB — find out how, and whether we can.

---

## 1. Correction to an earlier claim

I previously said "DX12 + DXR roughly doubles VRAM under Proton." **That overstated it.**
Checking vkd3d-proton #1874 properly: Guardians of the Galaxy goes from **5.1-5.5 GB without
DXR to filling an 8 GB card with it** — that is **~1.45-1.6x, not 2x**. And the maintainer
notes the same title reports roughly *half* that on native Windows for apparently similar
real usage, so part of the gap is reporting/accounting, not pure memory pressure.

More importantly the cause is narrower than "DX12": it is **DXR specifically — the BVH
acceleration structures.** Those get built as soon as the *feature* is enabled, whether or
not RT is being drawn that frame. Plain DX12 translation has its own smaller VRAM tax
(vkd3d-proton #991), but it is not the big number.

**Practical consequence: `VKD3D_CONFIG=nodxr` avoids the acceleration-structure allocation
entirely** for any DXR-capable title we are not actually using RT in. That is a real,
free VRAM lever and it is not currently set anywhere on this box.

## 2. "What about games with no DX11 path?"

They are the worst case here, and there is no escape hatch. Alan Wake 2, Starfield,
Indiana Jones, Doom: The Dark Ages are DX12-only, so they go through vkd3d-proton with
its translation tax, and the RT-mandatory ones (Alan Wake 2, Doom TDA) also pay the BVH
tax with no way to opt out. vkd3d-proton 2.13's changelog says outright that they had to
stop using ReBAR for upload heaps on <=8 GB cards because "we were regularly hitting the
upper limits of what the GPU could hold in VRAM."

Wukong ran DX11 (`Dx12=0`). That was the easy case, and it still used 5.2 of 6.1 GB.

## 3. Unified memory / VRAM overflow to system RAM — the hard answer

| mechanism | on this hardware |
|---|---|
| Windows WDDM "Shared GPU Memory" equivalent | **DOES NOT EXIST on NVIDIA/Linux** |
| AMD-style GTT (system RAM as graphics memory) | **NVIDIA has none.** amdgpu gets it free from TTM; NVIDIA's stack doesn't use TTM at all |
| `nvidia_uvm` / CUDA Unified Memory | **compute only** — no Vulkan/graphics path. `--unified-memory` tested by others, no effect |
| HMM in nvidia-open | **explicitly disabled in-tree**, `TODO` since 2022, and compute-oriented anyway |
| Resizable BAR | **already on** (BAR1 = 8 GB). Helps upload efficiency, adds no capacity |
| `VK_EXT_pageable_device_local_memory` | **REAL and active** — see below |

So: when the 4050 runs out of VRAM there is no kernel-level spill to system RAM. What we
do have is **userspace eviction** in DXVK 2.5+ / vkd3d-proton 2.9+ (an NVIDIA contribution),
which demotes low-priority resources to host memory and promotes them back on access.
**Verified present: GE-Proton11-6 ships DXVK v3.1.** That is why the card degrades to
stutter near the ceiling instead of hard-crashing. It is a soft landing, not capacity —
anything in the active per-frame working set just thrashes.

⚠️ The 780M *does* have unified memory and always did: **7.6 GB of GTT**, 1.4 GB in use.
That asymmetry is worth remembering — the iGPU can borrow system RAM, the dGPU cannot.

## 4. "Storage as RAM" — already happening, and it is the problem

Measured this session, during gameplay:

```
allocstall_normal    3,874      \  18,143 DIRECT RECLAIM STALLS
allocstall_movable  14,269      /  (a thread blocked, inline, waiting for memory)
pgscan_direct    2,165,133
pgsteal_direct   1,285,207
pswpout          4,232,545      (~16 GB written to swap)
```

Direct reclaim is a synchronous stall in the allocating thread. This is the mechanism
behind the 70 ms frametime spikes in BMW-BENCH §3, and it is a *memory management* failure,
not a GPU one — the GPU held a steady 93% throughout.

**The current swap stack is also structurally wrong.** zram (8 GB, saturated, prio 100)
stacked in front of a 32 GB swapfile (prio 10) creates LRU inversion: compressed pages stay
resident in fast RAM while genuinely colder pages get pushed to disk anyway. Chris Down's
March 2026 analysis (ex-Meta MM engineer) is explicit — *"If in doubt, prefer zswap. Only
use zram if you have a highly specific reason to"* — with Meta production data showing zswap
cut disk writes up to 25%. **zswap is already compiled in on this box and is disabled
(`enabled=N`, compressor zstd ready).** Arch guidance: run one or the other, never both.

## 5. What the consoles actually have — the encouraging part

| platform | total | to games | bandwidth |
|---|---|---|---|
| **Xbox Series S** | **10 GB** | **~8 GB** | 224 / 56 GB/s split |
| Nintendo Switch 2 | 12 GB | **9 GB** (3 GB reserved) | 102 / 68 GB/s |
| PlayStation 5 | 16 GB unified | ~12.5-13.5 GB (est., Sony never published) | 448 GB/s |
| Xbox Series X | 16 GB | 13.5 GB (official) | 560 / 336 GB/s |
| Steam Deck OLED | 16 GB unified | ~14-15 GB dynamic (1 GB default carveout, grows) | 102.4 GB/s |
| **This G14** | **22 GB (16 + 6)** | **~5 GB RAM + 6 GB VRAM in practice** | 84.6 + 192 GB/s |

**We have more total memory than any of them. Xbox Series S ships the same generation of
AAA on 8 GB — less than half our total — and never swaps once.**

So the budget is not the problem. Four things are:
1. **Split pools.** Assets exist in system RAM *and* VRAM. Unified memory structurally has
   one copy. This is the gap Microsoft built DX12 GPU Upload Heaps to close on PC; adoption
   is still thin and there is no published "X GB saved" figure.
2. **Hardware streaming.** PS5 Kraken+Oodle measures ~3.16:1 on real texture sets; Xbox
   claims SFS gives "approximately 2.5x effective I/O throughput and memory usage"
   (vendor claim, never independently reproduced). Linux equivalent: vkd3d-proton has had
   DirectStorage GDeflate GPU decompression since 2.10 (2023), still being reworked in 3.0
   (Nov 2025) — real, immature.
3. **Fixed target.** Consoles budget to the byte against one known memory map.
4. **OS footprint — and this is the one we own.** Series X reserves 2.5 GB. Series S ~2 GB.
   Switch 2 3 GB. **Luminos idles at 10.1 GB of 15.2 GB before a game starts.**

Sobering counterpoint worth recording: Black Myth Wukong's own co-founder said Series S's
10 GB shared "without years of optimisation experience — is really hard to make work."
This title is a hard case *for console developers too*. It is not a fair yardstick.

## 6. What is actually actionable, ranked by measured size

1. 🟢 **OS RAM footprint: 10.1 GB → console-class ~2 GB. Recovers ~8 GB.** By far the
   largest lever available and entirely within our control. This is the whole case for the
   new OS, restated with numbers.
2. 🟢 **Fix the swap architecture.** Drop the stacked zram+swapfile for zswap over the
   swapfile; `vm.page-cluster=0` if any zram is kept; raise `vm.watermark_scale_factor`
   from 10 toward 50-100 so kswapd wakes with lead time instead of threads hitting direct
   reclaim. **Success metric is not a feeling — it is `allocstall_*` in `/proc/vmstat`
   dropping under the same workload.** Baseline to beat: **18,143**.
3. 🟢 **`VKD3D_CONFIG=nodxr`** for DX12 titles we are not using RT in — removes the BVH
   allocation outright.
4. 🟡 **`dxvk.maxMemoryBudget`** to force graceful degradation instead of a crash, at a
   performance cost we choose. Debug-grade knob; use deliberately.
5. 🟡 **DirectStorage/GDeflate** via vkd3d-proton — the console streaming path. Exists,
   not yet something to depend on.
6. 🔴 **Nothing adds VRAM.** 6 GB is 6 GB. Every lever above is about system RAM, spill
   behaviour, and avoiding allocations we do not need.

## 7. Not established

- Whether any of §6.2's tuning measurably reduces frametime spikes **in a game** — no
  public gaming-specific benchmark exists for it. We have a baseline and a counter, so
  this is directly testable here and should be.
- No controlled public comparison of a 6 GB dGPU + 16 GB PC vs an 8 GB Series S on the
  same title. Our own measurements are better data than anything published.
