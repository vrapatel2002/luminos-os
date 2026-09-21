# docs/gamemode/WALL3-BREACHED.md — NVIDIA/Linux DOES have a usable system-memory heap
# [CHANGE: claude-code | 2026-09-20]
Measured on this G14's RTX 4050, nvidia-open-dkms 610.57.04. Probes in `tools/vram-probe/`.
**This contradicts the published consensus and changes the plan.**

---

## What everyone says

"NVIDIA has no GTT on Linux. If you ask for VRAM you get VRAM or you get nothing."
GH open-gpu-kernel-modules #758, and years of forum threads.

## What the card actually reports

```
HEAPS
  heap 0:  6141 MB  DEVICE_LOCAL          <- VRAM
  heap 1: 11451 MB  (host)                <- SYSTEM RAM, exposed to Vulkan

MEMORY TYPES
  type 0: heap 1  (no flags)              <- the interesting one
  type 1: heap 0  DEVICE_LOCAL
  type 2: heap 1  HOST_VISIBLE HOST_COHERENT
  type 3: heap 1  HOST_VISIBLE HOST_COHERENT HOST_CACHED
  type 4: heap 0  DEVICE_LOCAL HOST_VISIBLE HOST_COHERENT   <- ReBAR / HVV
```

**Memory type 0 is 11.4 GB of system RAM with no property flags at all** — not host-visible,
not device-local. It is device-accessible system memory. Nobody selects it, because every
allocator's heuristic is "prefer DEVICE_LOCAL", and failing that "must be HOST_VISIBLE".
Type 0 is neither, so it is invisible to normal selection logic.

## Three things proved by measurement

**1. An OPTIMALLY-TILED colour attachment can be allocated from type 0.**
`vkGetImageMemoryRequirements` for a 1024x1024 `R8G8B8A8_UNORM`,
`COLOR_ATTACHMENT|TRANSFER_SRC`, `TILING_OPTIMAL` image returns
`memoryTypeBits = 0x3` — **types 0 and 1.** Allocation and `vkBindImageMemory` both succeed.

This is the part the research said would fail. Tiling/compression page-kinds were expected to
require the FB aperture. They do not, for this configuration.

**2. The GPU renders into it correctly.**
`vkCmdClearColorImage` to (0.25, 0.5, 0.75, 1.0), copied back, read:
`pixel = 64,127,191,255`. Exact. **Verified, not inferred.**

**3. We can get 11 GB of it.**
44 x 256 MB chunks allocated from type 0 before failure = **11,264 MB**, i.e. essentially
the whole advertised heap.

## The cost, measured

Same Vulkan compute kernel, same buffer size, only the memory type changed:

| memory type | what it is | achieved bandwidth |
|---|---|---|
| type 1 | VRAM (DEVICE_LOCAL, heap 0) | **145.5 GB/s** |
| type 0 | system RAM (heap 1) | **21.6 GB/s** |

**6.8x slower.** That is PCIe-limited, as expected. For reference the 780M gets 84.6 GB/s
from the same DRAM, because it is on the memory bus rather than across PCIe.

## What this changes

- 🟢 **Wall 3 (aperture semantics) is breached.** Tiled, renderable images *can* live in
  system memory on NVIDIA/Linux. The "no GTT" consensus is right about the *automatic
  eviction* and wrong about the *capability*.
- 🟢 **Wall 1 (closed ICD) becomes mostly moot.** We do not need NVIDIA to change anything.
  The heap is already exposed through the public Vulkan interface. What is missing is an
  allocator that chooses it.
- 🟢 **Wall 2 (no eviction infrastructure) is now the only real one — and it moves to
  userspace.** DXVK already knows which resources exist, already tracks a budget via
  `VK_EXT_memory_budget`, and already has `evictResources()` / `requestMakeResident()`.
  It just relocates to `NoDeviceMemory` (host-visible) rather than to type 0.
- 🔴 **No kernel patch is needed.** The §3 finding that PMA is patchable CPU code is
  interesting but unnecessary. Do not start there.

## The actual work, restated

**Teach DXVK to use memory type 0 as an eviction tier.**

- Hot resources (render targets, current textures) stay in type 1 — 145 GB/s.
- Cold resources spill to type 0 — 21.6 GB/s, but resident and correct, instead of an
  allocation failure.
- `vela-vramd` decides *what* is cold, since the OS can see the whole picture and DXVK
  only sees one process.

That is a real eviction tier built on a capability the driver already ships, and it is
the thing that stops the 6 GB ceiling from ending a run.

## Format coverage: 14 of 14 (probe4.c)

The "which formats are eligible" risk is **gone**. Every resource class a real renderer
uses reports `memoryTypeBits = 0x3` and binds to type 0 successfully:

| resource | size | type 0 |
|---|---|---|
| colour RT 1080p RGBA8 / RGBA16F HDR / 2880x1800 | 8-21 MB | YES |
| depth D32_SFLOAT, depth+stencil D24S8 | 8.4 MB | YES |
| MSAA 2x and 4x colour | 17-32 MB | YES |
| BC1 / BC3 / BC7 compressed +mips | 2.7-5.3 MB | YES |
| storage image RGBA8 / RGBA16F | 8-17 MB | YES |
| cubemap array 1024 x6 +mips | 32 MB | YES |
| shadow map array D32 x4 | 64 MB | YES |

**No format restriction of any kind was found.**

## Why 21.6 GB/s — the link, measured

`LnkSta: Speed 16GT/s, Width x8` — the 4050 is on **PCIe 4.0 x8**, not x16.

| | |
|---|---|
| per lane (16 GT/s, 128b/130b) | 1.97 GB/s |
| x8, one direction | **15.75 GB/s** |
| x8 full duplex, aggregate | 31.5 GB/s |
| measured | **21.6 GB/s aggregate = 10.8 GB/s each way = 69% of theoretical** |

69% is ordinary PCIe efficiency after TLP overhead. Nothing is tunable here; x8 is how the
board is wired. For scale, VRAM's measured 145.5 GB/s is itself 76% of the 4050's 192 GB/s
spec, so both numbers carry the same efficiency.

## Honest limits

- 21.6 GB/s is a cliff. Anything in the per-frame working set will thrash there. This
  raises the ceiling before failure; it does not add fast memory. **Policy quality is
  therefore the whole game** — bad eviction choices are worse than none.
- **Still untested: whether DCC / delta colour compression is silently disabled for type 0
  allocations.** If it is, effective bandwidth is worse than the raw 21.6 GB/s suggests for
  colour targets specifically. Hard to observe directly; would show up as a render-heavy
  workload underperforming the synthetic number.
- All probes are synthetic. A real game under real pressure is the only proof that matters.
- Host-*pointer* import (`VK_EXT_external_memory_host`) is a different, weaker path: it only
  offers types 2 and 3, so it can back a **linear** image (verified: bind succeeded) but
  **not** an optimal-tiled one. GreenBoost's trick does not generalise to graphics — but it
  does not need to, because type 0 already does.
