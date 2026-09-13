# SPEC — concurrent CPU+iGPU prefill on the media server
# [CHANGE: claude-code | 2026-09-13]

Machine: Dell Inspiron 3590, i5-10210U (4c/8t, AVX2 only), 16 GB DDR4-2667 dual-channel,
Intel UHD 620 on shared RAM, two rotational drives, Jellyfin + *arr 24/7.
Model: Qwen2.5-Coder-7B-Instruct Q4_K_M (and the pure-Q4_K repack `qwen7b-pureQ4K.gguf`).

## What the client asked for, in their words

> "There is a measured 45% prefill speedup sitting untouched in the record for this machine.
> Build it. Prefill only — time-to-first-token on a big pasted file. Not generation."

Target architecture as specified: pipeline ubatches through a layer-split model. iGPU owns
the first N layers, CPU owns the remaining 28−N. Ubatch k on the CPU stage while ubatch k+1
enters the iGPU stage. No tensor splitting, no allreduce, no non-contiguous views. Explicitly
NOT tensor parallelism, which was already measured and loses at every ratio.

## ⚠️ REWRITTEN 2026-09-13. The premise above was contradicted by a number that was itself wrong.

This section originally argued that the iGPU collapses with prompt depth (5.44 t/s at 4,858
vs the CPU's 13.0) and that the pipeline therefore could not pay. **That argument is dead,
because the 5.44 did not measure the Intel iGPU at all.**

`llama-bench --list-devices` on this box reports **two** Vulkan devices:

```
0 = Intel(R) UHD Graphics (CML GT2)  | uma:1 | fp16:1 | warp 32 | 11779 MiB, 10601 free
1 = AMD Radeon R5 M435 (RADV HAINAN) | uma:0 | fp16:0 | warp 64 |  2048 MiB,  2046 free
```

`src/llama.cpp:260-283` sorts devices into `gpus` and `igpus`, then adds the integrated ones
**only `if (gpus.empty())`**. The AMD part enumerates as discrete, so the Intel iGPU was
**never placed in `model->devices`**. Every `-ngl 99` run in the record went to a 2 GB GCN1
part from 2013 with `fp16: 0`, and spilled the remaining layers back to the CPU. No command
in the record passed `-dev`, and `common/common.cpp:1683` narrows the device list only when
it is passed. **The fix in use is `-dev Vulkan0`.**

Proof the Intel GPU was idle, not slow — 433 samples across the both-devices arm read
`uncore_W = 0.00` and `rc6_busy = 0.0%` while `rc6_residency_ms` accumulated 5026-5031 ms per
5000 ms of wall clock (counter alive, 100% idle). Adding `-dev Vulkan0` moved those to
**8.47–10.11 W** and **100.0% busy** — a positive control, not an inference.

**Intel UHD 620 alone, `-dev Vulkan0 -ngl 99 -fa on`, tree `8395162`, llama-bench:**

| prompt | pp t/s |
|---:|---:|
| 512 | 25.5787 |
| 1024 | 25.5868 |
| 2048 | 25.5877 |
| 4096 | 25.5866 |

**Flat to 0.03% across an 8× range.** There is no depth collapse. The iGPU is ~1.9× the CPU
at every length tested, and `-fa off` matches within 0.01%, so flash attention is not a factor
on this device. The pp512 numbers the "+45%" rests on were the Intel iGPU and are sound; the
number that appeared to refute them was a different piece of silicon.

## Assumptions — every gap filled, and what it was filled with

1. **The mission is the goal, not the mechanism.** The goal is prefill TTFT on a ~4,000-token
   file. Ubatch pipelining is one route. It is not protected if the measurement kills it.
2. **The iGPU must first be shown useful at depth.** If it cannot exceed the CPU's 13 t/s at
   4,096 tokens, no scheduling work on top of it can pay. This is the gating question.
   **ANSWERED 2026-09-13: yes, 25.59 t/s flat to 4,096.** The gate is passed.
8. **"iGPU" in this project means the Intel UHD 620 and nothing else.** The AMD R5 M435 is
   excluded by measurement, not preference: own VRAM at ~6.2 GB/s (4.6× slower than system
   RAM), `fp16: 0`, GCN1 from 2013, 2 GB against a 4.28 GB model. Any number in the record
   that is ambiguous about which device produced it is discarded, not corrected.
9. **Every run must pin the device explicitly.** `-dev Vulkan0` is mandatory on this box.
   A run without it is not a slower run, it is a run of a different machine.
3. **`uncore` (intel-rapl:0:1) is the iGPU power rail.** Verified: reads exactly 0.000 W with
   the GPU idle while the counter is live. Used as the primary busy/idle discriminator in
   preference to RC6 residency, which the record itself warns is misread on an idle GPU.
4. **The iGPU is card1**, at `/sys/devices/pci0000:00/0000:00:02.0/drm/card1`, not card0.
   The earlier "RC6 idle 99.96%" reading is treated as unconfirmed until re-measured.
5. **llama-bench, not TTFT, for throughput.** It excludes model load from the reported t/s.
   A TTFT figure on this box includes reading 4.36 GiB off a rotational drive with mmap
   disabled by Vulkan, which is exactly the confound that could manufacture a "collapse".
6. **Bit-exactness is not the bar for prefill; token identity is.** Per the mission: first 32
   greedy tokens must match the unpatched build.
7. **Nothing gets installed on the box for a measurement.** `bc` is absent; awk does arithmetic.

## Blind spots hunted before any code

- **Model load contamination** (assumption 5) — addressed by the tool choice.
- **Memory cliff.** Vulkan disables mmap globally, pushing `shared` 139 MB → 3,818 MB. The box
  currently sits at 192 Mi free / 7.8 Gi buff/cache with Jellyfin live. Every arm logs
  `shared_MB` pre and post, and the sampler tracks the peak. Past ~5 GB is the swap cliff onto
  rotational drives.
- **Thermal drift ~10%/minutes.** No cross-arm comparison without a bracket: the deciding run
  is ordered vk1a, vk0, cpu, cpu_b, vk1b so the first and last arms bracket everything between.
- **A gate that passes without running.** Iteration 42's correctness gate reported PASS having
  compared two empty files (`llama-cli` rejected `-no-cnv`; `cmp -s` on two zero-byte files
  succeeds). Every gate from here asserts there is something to compare before comparing it.
- **Jellyfin and the *arr stack must survive.** Everything runs under `choom -n 1000`.

## Contracts — what is frozen

- `~/llmperf/queue/NN-name.sh`, run in name order by `runner.sh`; finished scripts move to
  `queue/done/`. Reordering is a rename. **Editing a queued script is safe; editing or
  interrupting a running one is not.**
- Results land in `~/llmperf/<name>.txt`. Every script ends by echoing `<NAME>_DONE` to stderr.
- `~/llama.cpp` @ `8ba09e5`, tree clean, is the baseline. Patched work goes in worktrees under
  `/srv/media/_llmtest/wt-*`, never in the baseline tree.
- Measured and predicted are never put in the same table. Estimates are labelled in-sentence.

## Done means

One real coding question against one real ~4,000-token file, cold cache: time-to-first-token
before and after, both measured on the same tree in the same session, with the first 32 greedy
tokens identical to the unpatched build.

## Exit

A prefill path that passes the correctness gate and beats 25.59 pp512, **or** three consecutive
iterations failing with three DIFFERENT isolated mechanisms, each proven by experiment and
located in source. "Hardware limit" does not count unless a specific resource is shown saturated.

---

# Iteration log

## Iteration 1 — BLOCKER LOCATED IN SOURCE, measurement queued

**Blocker A, the architecture is disabled by construction.** `src/llama-context.cpp:427-431`:

```c
bool pipeline_parallel =
    model.n_devices() > 1 &&
    model.n_gpu_layers() > model.hparams.n_layer_all &&   // requires FULL offload
    model.split_mode() == LLAMA_SPLIT_MODE_LAYER &&
    cparams.offload_kqv && !model.has_tensor_overrides();
```

A CPU+iGPU layer split has `n_gpu_layers < n_layer_all` by definition, so clause 2 is false
by construction; with a single iGPU, `n_devices() == 1`, so clause 1 is false too. At 437-441
the capability check does `continue` on `GGML_BACKEND_DEVICE_TYPE_CPU` — comment `// ignore
CPU backend` — so the scheduler never asks whether the CPU could be a stage.

Prior art confirms this is deliberate, not an oversight:
- **PR ggml-org/llama.cpp#6017** (slaren, Mar 2024) added `n_copies` / `GGML_SCHED_MAX_COPIES`.
  CUDA-only; requires async compute **and** the event interface. The CPU backend has neither
  (`.graph_compute_async` is NULL).
- **ggml issue ggml-org/ggml#721** (slaren, Feb 2024) proposed exactly the missing piece — a CPU
  backend with a persistent thread pool acting as an async queue, "to implement pipeline
  parallelism with CPU and GPU backends." **Closed 2024-06-19 as completed without implementing
  async**, on the reasoning that scheduler partial-offload improvements made it unnecessary.
- **TurboPrefill** (github.com/sergey-automation/TurboPrefill) is the closest live prior art: a
  llama.cpp scheduler patch doing ubatch-level wave scheduling, reporting 1.6–5.3×, largest on
  bandwidth-starved rigs. `split_mode=layer`, **multi-GPU only, no CPU stage.** Best template.
- Docs `multi-gpu.md` and Discussion #20252 both state pipeline parallelism does not support
  partial CPU offload.

**Blocker B, and it is upstream of A.** The iGPU may not be worth pipelining at all. The
depth collapse above needs re-measuring before anything is built on the pp512 number. External
corroboration that this is a real, open bug rather than a local misconfiguration:
**issue ggml-org/llama.cpp#18808** — Intel Vulkan prompt processing falls from 200-300 tok/s to
single digits past 4k-8k context, "GPU utilization spikes 0 to 100% with widening zero gaps",
regression bisected to **b7064**, flash attention implicated, still open and unfixed. That is
the same shape as 25.6 → 5.4 here. Note also that UHD 620 has no `coopmat`, so the Vulkan FA
path here is the scalar one (PR #13324), not the accelerated `coopmat2` path.

**Experiment queued: `55-igpudepth.sh`.** Separates two hypotheses.
- H1 starvation (what the record concluded): uncore stays at its 0.000 W floor throughout.
- H2 attention cost: uncore is high, and `-fa off` changes the depth slope while agreeing at 512.
- H3 measurement artifact: vk1a pp4096 comes back near 25 t/s, meaning the 5.44 was a TTFT
  number contaminated by model load, and the pipeline premise is intact after all.

## Iteration 2 — `55-igpudepth.sh` result: ALL THREE HYPOTHESES WERE WRONG, and so was the arm

The run reproduced neither the 25.59 nor the collapse: pp512 **6.858**, pp2048 **6.291**,
pp4096 **5.930** — a 14% decline, not an inversion, and slower than the CPU everywhere. A
result that matches no hypothesis is usually a sign the experiment measured the wrong thing,
and it had. All **433** samples read `uncore_W = 0.00` and `rc6_busy ≈ 0.0%` with the process
in `dma_fence_default_wait`, while `rc6_residency_ms` accumulated 5026–5031 ms per 5000 ms of
wall — the counter was alive and the Intel GPU was 100% idle for the entire run.

H1 looked confirmed. It was not: the Intel GPU was idle because it was **not in the device
list at all** (`src/llama.cpp:280`, `if (gpus.empty())`), and the work was going to the AMD
R5 M435 with CPU spill. `dma_fence_default_wait` was the CPU waiting on the *AMD* fence.

**I was wrong twice today and both are worth recording.** First, I framed
`llama-context.cpp:427` as "the architecture is disabled by construction". Under this
project's rules a five-line `if` in a checked-out tree is the work, not a wall. Second, I
inherited the record's assumption that "iGPU" meant the Intel part, and built an entire
hypothesis tree on a number that came from different silicon. The lesson is cheap to state
and was expensive to learn: **on a multi-GPU box, assert which device ran before interpreting
what it measured.** `55-igpudev.sh` now dumps `--list-devices` and greps the per-arm stderr
for device binding before any number is read.

Also worth recording as a dead end that cost nothing: I first suspected Vulkan submission
starvation via `serialize_submissions`. Killed by reading `ggml-vulkan.cpp:7384` — it is
env-gated on `GGML_VK_SERIALIZE_SUBMISSIONS` and off by default, so the `waitForFences` at
18189-18203 never executes. Issue #18808 (Intel Vulkan pp collapse past 4k, bisected to
b7064) is likewise **not** what is happening here; the curve is flat, so there is nothing to
bisect.

## Iteration 3 — `55-igpudev.sh`: the iGPU is fine, and was always fine

`-dev Vulkan0 -ngl 99 -fa on`, tree `8395162`: **25.5787 / 25.5868 / 25.5877 / 25.5866 t/s**
at 512 / 1024 / 2048 / 4096. Flat to 0.03% over an 8× range. `-fa off` matches within 0.01%.
Against the CPU's 13–14 t/s the Intel iGPU is **~1.9× faster and does not degrade with
length**. Root cause named and located; the fix is `-dev Vulkan0`.

**The next question is not "why is it slow" but "why only 56% of its own peak".** Live sysfs
during the run: `rps_act_freq_mhz = 900` steady while `rps_cur_freq_mhz` and
`punit_req_freq_mhz` both request **1100**, package at **97 °C** against a 100 °C critical.
Two separate deficits — an 82% clock cap that is heat, and a shader-efficiency gap.

The arithmetic, which **corrects something written earlier the same day**: 4096 tokens ×
~15.2 GFLOP/token ÷ 160.08 s ≈ **389 GFLOP/s**. At the *measured* 900 MHz, fp32 peak is
24 × 8 × 2 × 0.9e9 = **345.6 GFLOP/s** and fp16 peak is **691.2**. The measured figure
**exceeds fp32 peak**, so fp16 is already engaged — confirmed in source at
`ggml-vulkan.cpp:8074`, where `device->fp16 && prec == GGML_PREC_DEFAULT` selects
`pipeline_dequant_mul_mat_mat[Q4_K].f16acc`. An earlier note in this session called the same
number "~100% of fp32 peak" and floated fp16 as a free 2×; that was wrong on both counts — it
compared against a 1.0 GHz nameplate instead of the measured clock, and it had not read line
8074. **Candidate cause #6 (precision fallback) is closed**, with arm `nof16` in
`57-igperf.sh` standing as the control that proves it rather than asserting it.

**Queued:** `56-igate.sh` — correctness gate (first 32 greedy tokens, CPU vs `-dev Vulkan0`;
token identity, not bit-exactness, because the two backends accumulate differently by
construction) and cold-cache TTFT on the real 4,858-token file, ABBA-ordered.
`57-igperf.sh` — `-ub` sweep 128→2048 to separate a compute-bound GEMM from a fixed
per-ubatch cost, the `GGML_VK_DISABLE_F16` control, and `GGML_VK_PIPELINE_STATS=mul_mat` for
shader register spills. (`GGML_VK_PERF_LOGGER` stays untouched — it is recorded as taking
this driver down with `ErrorDeviceLost`, and it is a different code path at line 7735 from
the pipeline-statistics path at 3266.)
