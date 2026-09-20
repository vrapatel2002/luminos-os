# docs/gamemode/SHARED-VRAM-PLAN.md — building Windows' shared GPU memory on Linux
# [CHANGE: claude-code | 2026-09-20]
Task: find how Windows does it, compare to our stack, list every wall, and say how each
could be overcome. Supersedes the "does not exist, move on" framing in MEMORY-STRATEGY.md.

---

## 1. How Windows actually does it — and the key surprise

**WDDM is NOT demand paging.** This is the single most important thing in this document.

The GPU never faults mid-execution and resumes. Microsoft's docs are explicit that touching
a non-resident allocation is *illegal and fatal* — device removed, TDR. Instead:

1. Since WDDM 2.0 every allocation gets a **GPU virtual address fixed for its lifetime**,
   so the physical backing can move without rewriting command buffers.
2. The user-mode driver maintains a **per-device residency list** (`MakeResidentCb` /
   `EvictCb`).
3. Before any context is scheduled, **VidMm guarantees everything on that list is resident**,
   by building a separate **paging DMA buffer** via `DxgkDdiBuildPagingBuffer` and running it
   on the GPU's copy engine — operations like `DXGK_OPERATION_TRANSFER`,
   `MAP_APERTURE_SEGMENT`, `UPDATE_PAGE_TABLE`, `DISCARD_CONTENT`. Completion is tracked with
   a monitored fence.
4. Apps cooperate through `IDXGIAdapter3::QueryVideoMemoryInfo` (budget) and
   `ID3D12Device::MakeResident`/`Evict`.

**So it needs no exotic hardware.** No recoverable GPU page faults, no IOMMU (for the
GpuMmu model). It is: *ensure resident, then submit.* Ordinary DMA copies and page tables.

**That means it is replicable in principle — and Linux already replicates it.**

## 2. Linux already has this. Just not for NVIDIA.

`amdgpu` does the identical thing through **TTM**:
- Domains `TTM_PL_VRAM`, `TTM_PL_TT` (GTT — pinned system RAM mapped through the GART so the
  GPU addresses it directly), `TTM_PL_SYSTEM`.
- `amdgpu_cs_parser_bos()` locks and **`ttm_bo_validate()`s every buffer a submission
  references before the command buffer runs** — the exact shape of WDDM's residency model.
- If VRAM is full, TTM walks the domain LRU, evicts cold buffers to GTT via an accelerated
  blit behind a `dma_fence`, then places the new one.
- GTT is sized from system RAM (historically ~half). **This is why our 780M reports 7.6 GB
  of GTT.**

Intel's Xe does the same. **Nouveau does the same — on NVIDIA silicon** (`nouveau_ttm.c`,
`nouveau_bo.c`). So the hardware is not the problem.

## 3. 🟢 The surprise: the VRAM allocator is NOT in signed firmware

Folk wisdom says "it's all in GSP firmware, forget it." **Traced through the actual source
of `NVIDIA/open-gpu-kernel-modules` @ 615.71.09 — that is wrong.**

- `src/nvidia/src/kernel/mem_mgr/video_mem.c` (the `NV01_MEMORY_LOCAL_USER` class = VRAM
  allocations) calls `_vidmemPmaAllocate()` -> `pmaAllocatePages()` **unconditionally**.
- `.../phys_mem_allocator/phys_mem_allocator.c` — the PMA, the actual VRAM page allocator —
  contains **zero RPC calls**. Straight-line CPU code.
- The one RPC branch in `video_mem.c` is gated `if (!IS_GSP_CLIENT(pGpu))` — and an Ada card
  **is** a GSP client, so that path is **skipped**. It is legacy vGPU plumbing.
- The repo contains **no precompiled non-firmware binaries**. RM is real, readable,
  buildable C: ~656k lines in `src/nvidia`, MIT licensed.

**The "is there room in VRAM" decision runs as patchable CPU code in the `nvidia.ko` we
build ourselves via DKMS.** GSP owns init, power, security and privileged HW programming —
not this.

That is the opening. It is not, by itself, enough.

## 4. The walls, and what each would take

| # | Wall | Severity | Route through it |
|---|---|---|---|
| 1 | **The Vulkan ICD is closed.** It picks memory types and heaps and assumes an aperture. A kernel-side substitution it doesn't know about risks silent corruption rather than clean degradation. | 🔴 Hard | None directly. Work *above* it (DXVK) or *around* it (nouveau/NVK). |
| 2 | **No eviction infrastructure exists in RM.** No TTM-equivalent: no domains, no LRU, no placement, no `ttm_bo_validate`. The only VRAM->sysmem mover is `fbsr.c` (suspend/resume) and it **requires all GPU contexts torn down**. There is no live-eviction path to build on. | 🔴 Hard | Would have to be written from scratch inside RM — this is the multi-year part. |
| 3 | **Aperture semantics.** NVIDIA encodes FBMEM vs SYSMEM differently in GMMU page tables, and tiling/compression "page kinds" plus ROP/L2 paths assume FB-backed memory. AMD's GPU treats VRAM and GTT uniformly in one GPU VA space; NVIDIA's does not. | 🔴 Hard | This is GH issue **#758** on the open modules — open, no NVIDIA response. Architectural, not policy. |
| 4 | **Host-imported memory is not DEVICE_LOCAL.** `VK_EXT_external_memory_host` works (kernel side is `os_desc_mem.c` / `NV01_MEMORY_SYSTEM_OS_DESCRIPTOR`, `os-mlock.c` pinning) but NVIDIA exposes only host-visible memory types for it. Every real use found is staging/video interop. **No documented case of binding a renderable image to it.** | 🟠 Medium | Testable in an afternoon. If a color attachment *can* bind, a lot opens up. If not, GreenBoost's trick cannot generalize to graphics. |
| 5 | **No command-buffer visibility.** WDDM-style residency needs to know what a submission touches. The closed ICD builds those command buffers. | 🟠 Medium | DXVK *does* know — it builds the D3D->Vulkan translation. Residency logic belongs there, not in the kernel. |
| 6 | **GSP firmware is signed and WPR2-locked.** | ⚫ Absolute | Irrelevant, per §3 — the allocator isn't there. Nouveau treats GSP as an opaque coprocessor and talks RPC to it. |

## 5. What to actually build, ranked by payoff per effort

**Tier 1 — buildable now, no driver hacking**

1. **Patch DXVK's heap gate.** `dxvk_memory.cpp` already retries failed allocations with
   `DEVICE_LOCAL` cleared. It gates the aggressive path behind a first-heap-only rule whose
   own comment says it exists *"to avoid falling back to HVV on systems without resizable
   BAR."* **We have ReBAR — BAR1 is 8 GB over a 6 GB framebuffer.** The protection does not
   apply to us. Small patch, real code, measurable against Wukong.
2. **`vela-vramd` — budget enforcement above the driver.** Poll VRAM, and step gamescope's
   internal resolution or the title's texture setting down *before* the ceiling, instead of
   letting the driver hard-fail. **Not paging — preemption.** Given walls 1-3, this is the
   only thing that reliably prevents the crash, and it is entirely ours to write. Windows'
   own budget API (`QueryVideoMemoryInfo` + budget-change notifications) is the same idea:
   even Microsoft expects apps to *stay under* the line, not to page across it.
3. **vkd3d-proton `upload_hvv`** — already shipped, measured **+12% fps in Horizon Zero
   Dawn** by removing one copy. Free to try.

**Tier 2 — a real experiment with a real chance of failing**

4. **Patch `phys_mem_allocator.c` / `video_mem.c`** to retry a failed VRAM allocation against
   `ADDR_SYSMEM`. The source is there and builds. Someone proposed exactly this in NVIDIA's
   forums; **nobody has published a working build.** Expect walls 1 and 3 to produce
   corruption rather than slow-but-correct rendering. Worth doing to learn where it breaks —
   not worth expecting a product from.

**Tier 3 — the honest proof-of-concept**

5. **Boot nouveau + NVK.** It uses TTM, so it *already has GTT* on this exact RTX 4050.
   Reclocking is automatic on Ada via GSP (`nouveau.config=NvGspRm=1`) so the old
   stuck-at-low-clocks problem is gone. Cost: **40-63% of proprietary performance and no ray
   tracing** (Phoronix, Sept 2026, Ada + Blackwell). But it would let us **watch VRAM
   oversubscription actually work on our own hardware**, which no amount of reading settles.

**Tier 4 — not available**

6. Making the closed ICD cooperate. Modifying GSP firmware.

## 6. The honest bottom line

**Windows' mechanism is replicable — Linux replicates it three times over (amdgpu, Xe,
nouveau). What is missing is one vendor's implementation, and that vendor's closed userspace
sits in the middle of the only path that would matter for us.**

Building a true WDDM-equivalent for the proprietary NVIDIA stack is not a weekend project
and not an OS-level project — it is a driver project inside RM, against a closed ICD, and
NVIDIA has not done it in the decade people have been asking (GH #758, and forum threads
spanning drivers 555 through 610 with no staff answer).

**But the goal underneath the request — "stop the 6 GB ceiling from ending the run" — is
reachable without any of that**, via Tier 1. That is where the effort should go, and
`vela-vramd` is exactly the piece the new OS is entitled to own.
