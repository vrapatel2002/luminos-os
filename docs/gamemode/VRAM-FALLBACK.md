# docs/gamemode/VRAM-FALLBACK.md — "use RAM as VRAM": what's real, what's reachable
# [CHANGE: claude-code | 2026-09-20]
Shawn was right that NVIDIA ships a system-memory fallback. Correcting the record
from MEMORY-STRATEGY.md, which said it flatly does not exist.

---

## 1. The feature is real — and it is CUDA-only and Windows-only

**"CUDA – Sysmem Fallback Policy"**, NVIDIA Control Panel -> Manage 3D Settings.
The underlying behaviour shipped in driver **536.40 (Aug 2023)** — instead of returning
`cudaErrorMemoryAllocation`, the driver satisfies oversized allocations out of **pinned
host memory** reached over PCIe, using the UVM paging machinery. NVIDIA documents it
(KB a_id/5490) as "System Memory Fallback for Stable Diffusion".

Two hard limits:
- **CUDA only.** It is a CUDA allocator policy. D3D12/Vulkan graphics allocations are
  untouched — a game still gets a hard allocation failure on the same driver.
- **Windows only.** No `nvidia-settings` attribute, no `NVreg_*` module parameter, no
  env var, no NVAPI equivalent. An NVIDIA moderator answered the direct question:
  *"Sorry, not supported by the nvidia linux driver."*
  (forums.developer.nvidia.com/t/system-memory-fallback-for-linux/296874)

`nvidia-modprobe --unified-memory` has been tried by others and does not reproduce it.

## 2. Why Windows can and Linux cannot

Windows' **WDDM VidMm owns residency**, not the vendor driver. VidMm decides what lives
in the local segment (VRAM) vs the non-local segment (system RAM) and pages transparently;
the vendor KMD only implements the DDI callbacks. "Shared GPU memory" in Task Manager *is*
that non-local segment.

Linux's equivalent framework is **TTM**, and it is fully capable of this — `amdgpu` and
`i915`/`xe` plug into it and get exactly this behaviour. **That is precisely why the 780M
has 7.6 GB of GTT.** NVIDIA's proprietary Linux driver does not use TTM at all; it carries
its own resource manager that predates and bypasses that infrastructure, and never
implemented transparent eviction for graphics buffers.

**So it is a driver-architecture choice, not a Linux limitation.** Nouveau, which does use
TTM, gets GTT for free — and is unusable for gaming for unrelated reasons.

⚠️ 2026 development, noted and dismissed: **GreenBoost** (Mar 2026) is a third-party kernel
module + `LD_PRELOAD` CUDA shim that reimplements sysmem fallback on Linux via pinned
2 MB pages exported as DMA-BUF. It works — **for CUDA. It does not touch Vulkan, DXVK or
nvidia-drm**, and nobody has adapted the idea to graphics.

## 3. Can we lie to the driver about VRAM size? No — and it backfires

- `dxgi.maxDeviceMemory` (DXVK) changes only the number returned from
  `IDXGIAdapter::GetDesc` and the DXGI budget query. It lies **to the game**, never to the
  allocator. Its documented purpose is the *opposite* trick: unsticking old engines that
  cap their own texture pool because they don't recognise large cards.
- `VkPhysicalDeviceMemoryProperties` heap sizes come from the resource manager reading the
  physical framebuffer at init. **There is no override of any kind.**
- Over-reporting removes the game's own throttling, so it streams in more, and the
  allocation still fails against the real heap — converting graceful degradation into
  `VK_ERROR_OUT_OF_DEVICE_MEMORY`. No documented case of anyone gaining from this.

## 4. The copies — Shawn was right that duplication exists

Standard discrete-GPU texture upload:

| # | copy | avoidable? |
|---|---|---|
| 1 | disk/archive -> CPU system memory | **No.** Pure I/O; consoles pay it too |
| 2 | CPU memory -> HOST_VISIBLE upload heap | **Yes, with ReBAR** |
| 3 | upload heap -> DEVICE_LOCAL tiled texture | **Yes, with GPU upload heaps** — this one is an API/tiling convention, not a PCIe requirement |

D3D12's `D3D12_HEAP_TYPE_GPU_UPLOAD` (requires ReBAR) collapses 2+3 into one: the app
writes into a heap that *is* the real resource. `VK_EXT_external_memory_host` can remove
copy 2 by importing a host pointer directly — but it is **unreliable on NVIDIA's Linux
driver** (reported failing with ErrorOutOfDeviceMemory or absent entirely; solid on RADV).

## 5. 🟢 The "one pool" code already exists — and we have the hardware that ungates it

This is the actionable finding. **DXVK's allocator already implements host-memory fallback**
(`src/dxvk/dxvk_memory.cpp`):

- On a failed device-local allocation it retries with the bit cleared:
  `fallbackInfo.properties &= ~VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT;`
- `heap.enforceBudget = !isUnifiedMemoryArchitecture() && ...DISCRETE_GPU` — the budget
  cap is applied *because* we are a discrete GPU.
- And a deliberate gate, with this comment in the source: *"Only consider memory types from
  the first reported heap. This way, we avoid falling back to HVV on systems without
  resizable BAR by accident."*

**That gate exists to protect machines without Resizable BAR. This machine has ReBAR —
BAR1 is 8 GB, covering the entire 6 GB framebuffer.** The protection does not apply to us.

vkd3d-proton has the same idea already shipped: **PR #741 `upload_hvv`** (host-visible VRAM
for the UPLOAD heap) measured **+12% fps in Horizon Zero Dawn** (83-84 -> 92-94) purely by
removing an intermediate copy. And **issue #2258** documents a live bug in the
HVV -> sysmem fallback cascade — the exact mechanism we would be extending.

**Realistic experiment:** build DXVK with the first-heap restriction relaxed (or
`enforceBudget` forced off), run it against Wukong, and measure. Small patch, real code,
open source, and we have the ReBAR prerequisite.

## 6. The caveat that keeps this honest

Two things get conflated and must not be:
- **BAR-mapped host-visible VRAM is still VRAM.** Full bandwidth, CPU-writable. This is
  what `upload_hvv` exploits and where the +12% came from.
- **Genuine system RAM over PCIe is ~32 GB/s against the 4050's 192 GB/s.** Rendering out
  of it is an order-of-magnitude cliff.

So spilling to host memory **stops crashes; it does not make anything fast.** The win from
§5 is removing copies and raising the ceiling before failure — not turning 16 GB of DDR5
into usable VRAM.
