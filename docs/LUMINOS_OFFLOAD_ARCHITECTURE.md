# Luminos Offload Architecture — Big-LLM-on-System-RAM
# [CHANGE: claude-code | 2026-06-28]
# Status: PHASE 0 (de-risking) IN PROGRESS
# Decision rationale: LUMINOS_DECISIONS.md → DECISION 23

## Goal
Run the ~10.378B HOPE model (custom self-modifying-memory architecture, CUDA-only
kernel, no CPU fallback) on this laptop by **weight-offloading**: park 4-bit weights
in system RAM, stream them to the dGPU layer-by-layer, keep the hot/stateful parts
VRAM-resident.

## Hardware reality (confirmed 2026-06-28)
- dGPU: RTX 4050, 6 GB VRAM (4.6 GB usable), Ada (cc 8.9).
- PCIe: **Gen4 x8 capable (~16 GB/s)**, but link **idles at Gen1 (2.5 GT/s ≈ 2 GB/s)** under
  `NVreg_DynamicPowerManagement=0x02` (BUG-047). ← the real bottleneck risk.
- System RAM: 14 GB usable LPDDR5x, shared CPU/iGPU/OS.
- Memory pressure: zram (8 GB zstd) + luminos-ram active MADV_PAGEOUT, swappiness 60.
- CUDA toolkit: /opt/cuda (nvcc present). No torch env yet. HOPE checkpoint not on disk yet.

## Model budget (from architecture, reconciles to 10.379B)
- 36 attention layers; streamed part = 4d²+3dI = 218.1M → **109 MB/layer at 4-bit**.
- Resident-mandatory: self-mod-memory weights ~415 MB (bf16, CUDA kernel) + state.
- Resident-recommended: tok_emb (random access) 311 MB(4-bit), KV cache (int8 ~0.6 GB), lm_head, activations.
- ~2.2 GB resident baseline → ~2.4 GB VRAM headroom free.

## Throughput model
- bytes/token = (36 − R_resident) × 109 MB + lm_head 311 MB.
- ceiling = bytes/token ÷ PCIe GB/s. **MEASURED pinned bandwidth = 12.26 GB/s** (not the 16 raw).
- Revised ceilings @12.26 GB/s: R=0 → 4.24 GB → ~2.9 tok/s; R=18 → 2.27 GB → **~5.4 tok/s**; R=22 → ~6.7 tok/s.
- **Key lever: residency.** Each GB resident removes 1 GB/token streamed (every layer runs once/token).
- Chunked re-loading every token saves NOTHING (same bytes); only PERMANENT residency helps.

## Phased plan
- **Phase 0 — Foundations & de-risk (GATE):** torch+CUDA venv; obtain checkpoint+kernel;
  PCIe Gen4-under-load test; per-layer compute time (→ optimal R); verify 4-bit on 4050.
- **Phase 1 — PCIe max speed (luminos-power):** session-scoped P0/Gen4 pin, revert after. ✅ DONE (v4.3).
- **Phase 2 — RAM safety (luminos-ram):** exempt pinned region from zram/MADV_PAGEOUT;
  reserve pinned budget in headroom math (BUG-070); session swappiness drop; shared start/stop signal. ✅ DONE.
- **Phase 3 — Model prep:** 4-bit attn/FFN/CMS, bf16 self-mod-mem; define resident/stream split; optional KV 32→8.
- **Phase 4 — Streaming engine:** pinned ring buffer + double-buffered async copy (2 CUDA streams);
  resident layers loaded once; JIT dequant on GPU; CUDA kernel resident.
- **Phase 5 — Integration, tuning, validation:** real tok/s vs ceiling; thermal+OOM stability.
- **Phase 6 — Productionize:** clean teardown, widget status, docs.

## Measurement log
### Phase 0
- 2026-06-28: PCIe link confirmed Gen4 x8 cap, Gen1 idle.
- 2026-06-28: **PCIe sustained-load test PASSED** (probe: /tmp/pcie_bw.cu, 256MB×400 H2D loop).
  - Link held **16.0 GT/s x8 (Gen4) for the full 15s under load — NO downtrain.** The feared 8× DPM
    throttle does NOT happen under streaming traffic; Gen1 is only a true-idle state.
  - **H2D pinned = 12.26 GB/s, pageable = 9.47 GB/s** → pinning ≈ +30%, confirms pin-the-weights plan.
  - Implication for Phase 1: the LINK self-manages under streaming load; the power-pin matters more for
    keeping GPU CORE CLOCKS (P0) up during compute than for the link itself. (Test was pure DMA, GPU core
    idle, yet link stayed Gen4 → link speed and P-state are decoupled.) Still verify under real
    compute+transfer interleave (micro-gaps between layers).
  - Build note: CUDA 13.2 nvcc needs `-ccbin g++-15` (system gcc 16.1.1 too new). Relevant for Phase 4.
- 2026-06-28: blockers 0.1/0.2 RESOLVED — model lives in `/home/shawn/hope-llm/` (NOT in luminos-os).
  - Reuse existing venv `/home/shawn/hope-llm/.venv` (torch 2.12.0+cu130, CUDA True, **triton 3.7.0** for the
    custom DGD kernel, transformers 5.12.1, safetensors 0.8.0). DO NOT rebuild torch stack — kernel is
    version-fragile. No new venv → no luminos-brain gate needed for reuse.
  - Checkpoints: `checkpoints/qwen3_transplant/best.pt` = **20 GB** (10.4B); `checkpoints/smollm_transplant/best.pt`
    = 1.8 GB (472M, runs locally already — fits VRAM, needs NO offload).
  - **bitsandbytes + accelerate MISSING** → 4-bit quant toolchain install needed (Phase 0.5/Phase 3).
    Installing into the venv IS a package action → REQUIRES `luminos-brain safe` (Rule 5) before pip.
  - Note: `configs/ds_zero2_offload.json` exists — prior DeepSpeed ZeRO offload experiment on their side.
- FORK RAISED 2026-06-28: offload only matters for the 10.4B (a model that FITS can't validate offload).
  Decision pending from user: build/validate offload against the 20 GB 10.4B, or drop offload & just run 472M.
- 2026-06-28: **Phase 0.4 per-layer compute MEASURED** (probe /tmp/layer_compute.py, decode batch1 seq1, bf16):
  - per-layer compute = **2.56 ms**; per-layer stream (4-bit) = **8.89 ms** → firmly TRANSFER-BOUND.
  - **compute-bound flip R* = 25.6 resident layers** — MORE than VRAM can hold (~18–22). So the binding
    constraint is VRAM capacity, NOT the flip: **every layer we can fit resident adds speed, none wasted.**
  - tok/s @12.26 GB/s: R=0 → 2.9, R=9 → 3.8, **R=18 → 5.4**, R=22 → 6.7.
  - => Strategy: maximize resident layers up to VRAM limit. KV re-collapse 32→8 (frees 0.45–0.9 GB →
    +4–8 layers) pushes toward R* and ~6.7 tok/s. Beyond R≈26 it stops helping (compute-bound).
  - CAVEAT: this is attn+FFN only. The resident CUDA DGD memory kernel adds a FIXED per-token cost
    (not yet measured — needs real model) that will shave real tok/s somewhat below these ceilings.
- DECISION: user chose Option A (build offload, target the 20 GB 10.4B). 472M dropped as a target.
- PENDING: 0.5 4-bit verify on 4050 — needs bitsandbytes+accelerate install into the venv (GATED: Rule 5).
  - UPDATE 2026-06-28: other chat owns 0.5. Install = plain `pip install bitsandbytes` into the EXISTING
    hope-llm/.venv (py3.14.4, torch 2.12.0+cu130, triton 3.7.0 — already DGD-verified). NOT pyenv 3.12.13
    (would force a torch/triton rebuild that breaks the version-fragile DGD kernel), NOT a gate override
    (it's a normal pip install — run the luminos gate normally). Hard rule: install must NOT upgrade
    torch/triton; if pip tries, abort and use --no-deps / --no-build-isolation, or fall back to torchao int4.
    Sanity check after: `from src import triton_dgd` must still import with torch 2.12.0+cu130 / triton 3.7.0.
    Verify script written: hope-llm/scripts/verify_4bit.py (tiny proxy, not the 20GB checkpoint — proves
    4-bit works on 4050 + DGD stays bf16 + both coexist in one forward). torchao fallback arm on standby.

### Phase 1 — PCIe / GPU performance pin (luminos-power v4.3)
- 2026-06-28: **Phase 1 DONE.** Added a session-scoped offload GPU pin to luminos-power (DECISION 23).
  - New socket commands: `offload_start` / `offload_stop` / `offload_status`. The Phase 4 engine calls
    offload_start before streaming and offload_stop on teardown.
  - On start: persistence mode on (`nvidia-smi -pm 1`); GPU graphics clock LOCKED to max (3105 MHz on this
    4050) so the sub-ms gaps between streamed layers can't trigger a P-state downclock mid-token; TGP pinned
    to 90W on the next monitor tick (thermal-gated — still drops to 55W if GPU ≥ 83°C for safety).
  - On stop: clock lock reset (`--reset-gpu-clocks`), TGP handed back to the dynamic manager, signal removed.
  - **PCIe link deliberately NOT pinned** — Phase 0 proved it self-trains to Gen4 x8 under streaming load
    (Gen1 is idle-only). So Phase 1 ended up lighter than the original plan: it's a GPU-core-clock pin, not a
    link pin. This matches the Phase 0 finding that link speed and P-state are decoupled.
  - **Shared cross-daemon signal:** `/run/luminos/offload.active` (written by power on start, removed on stop).
    Phase 2 luminos-ram will read this to know when to exempt the pinned weight region. Single source of truth.
  - Concurrency: `offloadActive atomic.Bool` set from the socket goroutine; the TGP write (currentGPUTGPW)
    stays single-writer in monitorLoop → no data race. `go build` + `go vet` clean.
  - NOT YET DEPLOYED: binary compiles but the running luminos-power.service has not been restarted (needs root
    + would interrupt the live power governor — defer to a deliberate deploy step with the user).

### Phase 2 — RAM pinning safety & coordination (luminos-ram)
- 2026-06-28: **Phase 2 DONE.** Added weight-offload RAM coordination to luminos-ram (DECISION 23).
  - New socket commands: `offload_start {pid, reserved_mb}` / `offload_stop`. The Phase 4 engine sends these
    (alongside the matching power commands) with its own PID + the pinned-weight budget to reserve.
  - **Protect the inference process** while a session is active:
    - central guard in `madvise()` — skip MADV_PAGEOUT on the protected PID (prefetch/WILLNEED still allowed);
    - `isProtectedAlways()` returns true for the PID — never SIGSTOP-frozen or killed mid-session.
    - (Note: a headless CLI inference process isn't window-tracked, so the hot/cold reclaim + leak/restart
      loops wouldn't touch it anyway — these guards are belt-and-suspenders insurance.)
  - **The real lever — session swappiness drop:** save current vm.swappiness, set 10 for the session
    (base is 60), restore on stop. This is what actually keeps the kernel from paging the RAM-parked 4-bit
    weights to zram (which would wreck streaming throughput). Pinned ring-buffer pages are mlocked → already
    unevictable; the bulk pageable weight region is what swappiness protects.
  - **Headroom reservation (BUG-070 tie-in):** `getMemStats` now reports `offload_reserved_gb` +
    `effective_available` (= MemAvailable − reservation, floored at 0) so luminos-train-ram and any other
    headroom consumer don't count the offload region as free.
  - **Crash failsafe:** monitorLoop runs `checkOffloadLiveness()` every 3s — if the inference PID dies without
    offload_stop, auto-release protection and RESTORE swappiness (so the lowered value can't linger
    system-wide). Power-side GPU-pin crash recovery is deferred to Phase 5 (power doesn't yet hold the PID).
  - Concurrency: `offloadPID`/`offloadReservedMB` atomic (socket-writer / monitor-reader); `offloadMu` +
    `savedSwappiness` guard start/stop. Lock order stateMu→offloadMu only (no reverse path) → no deadlock.
  - `go build` clean. `go vet` clean except a PRE-EXISTING `unsafe.Pointer` note on the process_madvise
    syscall (line ~1178) — unrelated to this change.
  - NOT YET DEPLOYED: same as Phase 1 — restart both luminos-ram + luminos-power together in one deliberate
    deploy step before Phase 4/5.
  - **Swappiness write under hardened unit:** luminos-ram.service runs as root with a restricted
    CapabilityBoundingSet (PTRACE/NICE/KILL) + ProtectSystem=full. /proc/sys/vm/swappiness is root-owned 0644
    and ProtectSystem=full does NOT cover /proc/sys, so root file-owner write should succeed without extra
    caps — VERIFY on deploy (smoke test: offload_start then `cat /proc/sys/vm/swappiness` == 10).
