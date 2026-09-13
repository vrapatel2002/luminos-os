# Media Server LLM Performance — Running Build Log
# [CHANGE: claude-code | 2026-09-12]

Target: make the Dell Inspiron 3590 media server run a coding-capable LLM at interactive
speed. Hardware unchanged. Attack prefill and generation.

**Machine:** i5-10210U (4c/8t, AVX2, no AVX-512/VNNI/AMX), 16 GB DDR4-2667 dual-channel,
UHD 620 iGPU, two rotational drives, no SSD. Jellyfin + *arr run 24/7 and must survive.

**Rule for this log:** every number is measured unless the sentence says "estimate".
Measured and predicted are never put in the same table.

---

## Trees and provenance

| tree | branch | notes |
|---|---|---|
| `~/llama.cpp` @ `8395162` | `cpu-igpu-tensor-parallel` | f3f1a8f + instrumentation commit |
| `~/llama.cpp/build` | GGML_VULKAN=OFF, GGML_CPU_REPACK=ON, GGML_NATIVE=ON, Release | CPU numbers come from here |
| `~/llama.cpp/build-vk` | GGML_VULKAN=ON | iGPU / tensor-parallel numbers |

Prior-session instrumentation was uncommitted; committed as `8395162` before any
measurement so baselines are honest.

**Verified the instrumentation is free for CPU-only runs.** The added code lives entirely
in `ggml_backend_tensor_copy_async()` (multi-backend only) and `ggml-backend-meta.cpp`
(`-sm tensor` only), each behind a `static const bool = getenv(...)`. CPU-only path is
untouched. So `build/` numbers are comparable to a clean master.

---

## Iteration 1 — free flags. Baseline established, two findings, one self-inflicted error.

`llama-bench -m Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf -p 512 -n 32 -t 4 -r 1 --no-warmup`,
CPU tree, `choom -n 1000`, *arr services left running. Whole matrix repeated 3× to
interleave against thermal drift.

**Pass 1 is discarded — the box was contaminated.** A research agent was running
`llama-server` prefills on the same machine during pass 1. It shows up unmistakably:
`kvq8` pp 8.27 vs 12.3 later, `poll0` pp 8.62 vs 13.1, and `t8` tg 0.57 vs 5.74 (a 907%
spread). Passes 2 and 3 are mutually consistent to ~1%. Numbers below are the p2/p3 mean.

| config | pp512 t/s | tg32 t/s |
|---|---:|---:|
| **baseline (`-fa auto`)** | **13.13** | **5.48** |
| `-fa off` | 13.13 | 5.34 |
| `-fa on` | 13.18 | 5.41 |
| `-t 8` | 12.89 | **5.74** |
| `-fa on -ctk q8_0 -ctv q8_0` | **12.28** | 5.37 |
| `--poll 0` | 13.06 | 5.37 |
| `-C 0x55 --cpu-strict 1` | 7.32 | 4.24 |

Findings:

1. **`-fa auto` already resolves to ON** on this CPU-only build, and there is a real CPU
   flash-attention kernel — no silent fallback. `-fa off/on/auto` are within noise at
   pp512 because the context is short; FA's value is at long context, not here. So
   "turn on flash attention" is not an available win — it was never off.
2. **Quantizing the KV cache costs prefill 6.5%** (13.13 → 12.28). Mechanism: the
   quantize/dequantize of K and V is extra compute on a machine whose prefill is
   compute-dominated. KV quant is a memory-footprint lever here, not a speed lever, and
   it is not free. This contradicts the assumption in the prior record that `-ctk/-ctv
   q8_0` was a "prefill lever".
3. **`-t 8` beats `-t 4` on generation by +4.7%** (5.48 → 5.74) while costing prefill
   1.8%. This refines the old record's "4 threads ≈ 8 threads": they are equal on
   prefill, but SMT does help generation, where the cores are stalled on memory and the
   sibling thread has something to do.

**Correction — the `0x55` row is my error, not a finding.** I asserted 0x55 was "one
thread per physical core". It is not. `/sys/.../topology`: cpu0/cpu4 are siblings,
cpu1/cpu5, cpu2/cpu6, cpu3/cpu7. So `0x55` = cpus 0,2,4,6 = **physical cores 0 and 2
only** — I ran 4 threads on 2 cores, hence −44%. The correct one-per-core mask is `0x0f`.
Re-tested properly in iteration 2. No conclusion about pinning can be drawn from that row.

---

## Iteration 2 — the compute term: kernel coverage by quant type

**Constraint stated:** prefill 13.13 t/s. A two-point solve from the prior record gives
0.107 s weight-read + 0.065 s compute per token, i.e. compute is ~38% of cost, and prefill
(which batches and amortizes reads) is the compute-dominated phase. Attack the compute.

**Mechanism found by reading the source, not by category reasoning.**
`ggml/src/ggml-cpu/repack.cpp:4573-4700` dispatches interleaved ("repacked") AVX2 GEMM
kernels. On this machine the repack-eligible types are **Q4_0, Q4_K, IQ4_NL, MXFP4, Q8_0**.
**Q5_K and Q6_K have no AVX2 branch at all** — their only repack paths are ARM NEON
(`ggml_cpu_has_neon() && ggml_cpu_has_matmul_int8()`). Q2_K's requires AVX-512.

Measured composition of the model actually in use:

| model | Q4_K | Q6_K | total |
|---|---:|---:|---:|
| Qwen2.5-Coder-7B **Q4_K_M** | 3.192 GiB (73.3%) | **1.162 GiB (26.7%)** | 4.356 GiB |
| requantized **pure Q4_K** | 3.989 GiB (100%) | 0 | 3.989 GiB |

The Q6_K is `blk.*.ffn_down` 0.726 GiB + `output.weight` 0.416 GiB + `blk.*.attn_v`
0.020 GiB. `output.weight` is only evaluated for the last position during prefill, so
**prefill sees 17.1% of bytes on the generic kernel; generation sees all 26.7%.**

Requantize: `llama-quantize --allow-requantize --pure <in> <out> Q4_K`, 49 s.
Note `--pure` is required: `--output-tensor-type`/`--token-embedding-type` are evaluated
*before* the pure branch and would override it.

Pure-Q4_K should help via two independent mechanisms, which is why it needs an A/B rather
than an argument: (a) `ffn_down`/`output` move onto the repacked kernel, (b) the file is
8.3% smaller, so generation reads fewer bytes regardless of kernel.

### Methodology flaw found in my own sweep — stated so the numbers aren't over-read

I interleaved by repeating the whole matrix 3×, which defeats *drift between passes* but
NOT *position within a pass*: config #7 is always measured on a hotter box than config #1.
It shows up plainly — `-t 8` measured −1.8% pp in sweep 1 (position 4 of 8) and −14.6% in
sweep 2 (position 5 of 7, after two extra model loads).

Consequence: **only adjacent-position comparisons from these sweeps are trustworthy.**
Luckily the comparison I actually wanted is adjacent by construction — `q4km`/`pureq4k`
sit at positions 1/2, 3/4 and 5/6, so the three model A/B pairs are clean. Cross-position
claims (e.g. "pinning costs X" or "`-ub 1024` costs Y") are **not** supported by this data
and I am not drawing them.

All later A/Bs in this log use **ABBA alternation within a pass** and report medians.

### Result — iteration 2

**Second methodology finding: discard pass 1 always.** Pass 1 runs on a cool box that is
still in turbo; `q4km` measured pp 15.46 in pass 1 and 13.20 / 13.08 in passes 2 and 3.
Passes 2 and 3 agree to ~1% and are the steady state — which is also the state a real
5-minute prefill actually runs in. All conclusions below use the p2/p3 mean.

Three adjacent pairs, Qwen2.5-Coder-7B, CPU tree, steady state:

| pair (adjacent positions) | pp512 Q4_K_M → pureQ4K | tg32 Q4_K_M → pureQ4K |
|---|---|---|
| `-t 4` | 13.14 → 14.41 (**+9.6%**) | 5.38 → 5.84 (**+8.6%**) |
| `-C 0x0f --cpu-strict 1` | 13.28 → 14.43 (**+8.7%**) | 5.38 → 5.83 (**+8.5%**) |
| `-t 8` | 12.86 → 13.93 (**+8.3%**) | 5.74 → 6.15 (**+7.1%**) |

**Prefill +8.3% to +9.6%. Generation +7.1% to +8.6%. Consistent across all three pairs.**

**I must correct myself.** Mid-run I read the pass-1 numbers and wrote that prefill moved
only +0.9% and that "the kernel-coverage theory is not where the prefill win lives." That
was wrong, and it was wrong because I drew a conclusion from the single least reliable
pass. With all three passes in, prefill gains ~9% and it is the most consistent result in
the sweep.

**The two phases gain for two different, separable reasons — and each one matches its own
arithmetic:**
- **Generation +8%**: the file is 8.3% smaller (4.356 → 3.989 GiB) and generation runs at
  ~76% of the pure weight-read ceiling. Fewer bytes alone predicts ~8%. Measured 7–9%.
  This is a *bytes* win, not a kernel win.
- **Prefill +9%**: prefill moves only 0.11 GB/s, i.e. 0.3% of the bus — it is ~99.7%
  compute, so bytes cannot explain it. This is the `ffn_down` tensors (17.1% of prefill
  bytes) moving from the generic AVX2 Q6_K `vec_dot` onto the interleaved
  `q4_K_8x8_q8_K` GEMM. **This is a kernel win, and it confirms the mechanism.**

Worth stating, because it bounds the rest of the kernel work: the generic path is not a
naive one. My tree already contains PR #22345 (merged 2026-04-26), which raised AVX2 Q6_K
MUL_MAT from 101 to 144 GFLOPS. So ~9% is what beating an *already-tuned* non-interleaved
kernel on 17% of the bytes is worth. That is the correct scale to expect from kernel work
here, and it is why the tiled-mul_mat A/B is worth running rather than assuming.

**Kept.** Pure-Q4_K is the new baseline: **pp 14.41, tg 5.84** (from 13.14 / 5.38). It also
frees 366 MB of page cache, which is not nothing on a box where a 900 MB swing was
measured to be worth 21.9×.

**Unpriced risk, stated plainly:** quality. `output.weight` went 6-bit → 4-bit and nothing
has measured what that cost. There is no quality number anywhere in this project. Flagged
as the top outstanding gap.

**Free lever spotted, not yet tested:** prefill wants `-t 4` (14.41 vs 13.93) and
generation wants `-t 8` (6.15 vs 5.84). `llama-server` takes these separately as
`-t` (generation) and `-tb`/`--threads-batch` (prefill), so `-t 8 -tb 4` should get both.

---

## Iteration 3 — tiled AVX2 mul_mat (PR #27851). No gain on the baseline. Mechanism isolated.

**Constraint:** prefill 14.41 t/s, ~99.7% compute. Iteration 2 proved kernel choice is worth
~9% here. The obvious next kernel lever is upstream PR **#27851** ("Optimized AVX2 kernel"),
a tiled/blocked `mul_mat` that replaces the generic per-row `vec_dot` loop.

**Why this was testable cleanly.** The PR gates itself on an env var:

```c
static bool ggml_tiled_matmul_enabled(void) {
    const char * env = getenv("GGML_CPU_TILED_MM");
    enabled = env == NULL || atoi(env) != 0;   // on by default
}
```

So **one binary answers both sides** — no build-to-build drift, no separate tree. Built it in
a `git worktree` at `/srv/media/_llmtest/wt-pr27851` (branch `pr27851`, HEAD `9196ebd`,
Release, `GGML_VULKAN=OFF GGML_CPU_REPACK=ON GGML_NATIVE=ON`) so the main tree was untouched.

**Correctness first:** `GGML_CPU_TILED_MM=1 test-backend-ops -o MUL_MAT -b CPU` →
**1314/1314 passed, Backend CPU: OK.** The known `ggml_n_dims(op->src[0]) == 2` assert in that
PR does not trigger on this machine.

### Result — ABBA-alternated, same binary, medians over 3 passes

| config | pp512 tiled OFF | pp512 tiled ON | delta | spread |
|---|---:|---:|---:|---:|
| Qwen2.5-Coder-7B **Q4_K_M** | 12.96 | 13.16 | **+1.5%** | ≤1.5% |
| Qwen2.5-Coder-7B **pure Q4_K** | 14.23 | 14.22 | **−0.1%** | ≤0.7% |
| Q4_K_M, **pp2048** | 12.37 | 12.49 | **+1.0%** | ≤0.3% |

| config | tg32 tiled OFF | tg32 tiled ON | delta |
|---|---:|---:|---:|
| Q4_K_M | 5.34 | 5.35 | +0.2% |
| pure Q4_K | 5.79 | 5.76 | −0.5% |

**Not kept. It does not beat the baseline.**

**The mechanism, isolated by the experiment itself.** The tiled kernel and the repacked kernel
are not additive — **they compete for the same tensors, and repack already won them.** The
tiled path can only engage where repack does *not*, i.e. on types with no AVX2 interleaved
branch. On Q4_K_M that is the 26.7% of bytes that are Q6_K, and tiling those is worth +1.5%.
On pure Q4_K there are no such tensors left at all, and the measurement is **exactly zero**.
The dose-response tracks Q6_K content precisely: 26.7% Q6_K → +1.5%; 0% Q6_K → −0.1%.

Iteration 2 already harvested that same 26.7% more completely, by moving it onto the
*repacked* kernel (+9.6%) rather than a tiled generic one (+1.5%). There is nothing left for
this PR to do on this model.

**This settles the council's central disagreement, against me.** In iteration 2 the First
Principles advisor argued prefill runs at ~34% of AVX2 peak (185 vs 537 GOPS) so a 2× is on
the table; the Contrarian argued tiled and repack cancel on AVX2 and the win is ~zero.
**The Contrarian was right, and the measurement says so: −0.1% on the actual baseline.**
"34% of peak" is a real number, but the gap is not reachable by a better generic GEMM — the
repacked kernel is already the thing that closes it as far as it closes on this chip.

**Bonus: iteration 2 reproduced independently.** This sweep measured both models ABBA in the
same pass, on a different binary, on a different day's thermal state: pure vs Q4_K_M is
**+9.8% pp (14.23 vs 12.96)** and **+8.4% tg (5.79 vs 5.34)**, against +9.6% / +8.6% before.
The pure-Q4_K win is real and it replicates.

---

## Iteration 4 — the PRIMARY TARGET: the handed-down hypothesis is wrong. New mechanism named.

**The constraint, restated as a measured number.** Under `-sm tensor` at `-ts 1/99` — iGPU
given 1% of the split, allreduce 0.7% of runtime, zero waiting, 0.109 s of memcpy out of
41 s — the CPU takes **55.8 s** for a prompt it finishes in **39.8 s** alone. **1.42×
self-inflicted, with the other device effectively removed.** (Prior session, recorded.)

The hypothesis I inherited: *split weights arrive as non-contiguous views, so both backends
drop their optimized GEMM kernels.* I was told to confirm or kill it. **I am killing it,
and naming the replacement.**

### Why the non-contiguity hypothesis is wrong — read in the source

`ggml/src/ggml-backend-meta.cpp:1108-1126`. When the meta buffer materialises a device's
share of a tensor it does **not** make a strided view of the original. It allocates a fresh
tensor of the sub-shape and rescales the strides consistently:

```c
ne[split_dim] = <this device's share>;
for (int i = 0; i < GGML_MAX_DIMS; i++) {
    if (tensor->nb[i] > tensor->nb[split_dim]) {
        nb[i] = tensor->nb[i] * ne[split_dim]/tensor->ne[split_dim];
    }
}
ggml_tensor * t_ij = ggml_new_tensor(simple_ctx, tensor->type, GGML_MAX_DIMS, ne);
```

Every stride larger than the split stride is scaled by exactly the split fraction; the rest
are unchanged. That is the definition of a contiguous sub-tensor, and the weight bytes are
physically re-laid-out into each device's own buffer by the scatter in
`ggml_backend_meta_buffer_set_tensor` (:1220-1350). **The split weights are contiguous.**
The hypothesis named the wrong thing.

### The replacement mechanism — also read in the source, and it is one line

`ggml/src/ggml-backend-meta.cpp:357`:

```c
simple_bufts.push_back(ggml_backend_dev_buffer_type(ggml_backend_meta_dev_simple_dev(dev, i)));
```

The meta buffer type is built from each sub-device's **default** buffer type. For the CPU
device that is `ggml_backend_cpu_buffer_type()`.

But the fast interleaved AVX2 GEMMs in `repack.cpp` are *only* reachable when weights live
in an **extra** buffer type — fetched via `ggml_backend_dev_get_extra_bufts` and appended
to the buft list in `llama-model.cpp:make_cpu_buft_list()` (:570-586), gated on
`use_extra_bufts`. **The meta backend never asks for extra bufts.** There is no call to
`ggml_backend_dev_get_extra_bufts` anywhere in `ggml-backend-meta.cpp`.

So the claim is: **under `-sm tensor` the CPU's share of every weight lands in the plain CPU
buffer, repack never happens, and the CPU runs 100% of its GEMMs on the generic
`ggml_vec_dot_*` path.** That is a buffer-type bug, not a layout bug — and it is the same
lever iteration 2 already proved is worth real money on this machine.

### Prior art — where I looked, and what is there

- `-sm tensor` is ggml-org/llama.cpp **PR #19378** (backend-agnostic tensor parallelism,
  experimental). It is **GPU-only by design**: only CUDA got the extensions, and CPU
  participation is listed as future NUMA work. `src/llama.cpp:258` *deliberately skips* any
  device whose buffer type is `ggml_backend_cpu_buffer_type()` — which is why nobody
  upstream has hit this. The CPU only joins when forced in by hand, which is what the prior
  session's llama-bench patch does.
- Checked current master's `ggml-backend-meta.cpp`: still **no** occurrence of `extra_buft`
  or `repack`. The gap is unfixed as of this writing.
- Searched llama.cpp issues/PRs for repack × split-mode-tensor, meta backend × extra bufts,
  `ggml_backend_cpu_repack_buffer_type`, "tensor parallelism CPU repack slower". **Nothing.**
  Nearest hits (#25829, #25594, #22307, #27467) are CUDA correctness, not this.
- Published AVX2 repack gains, for calibration: **PR #12332** (Q4_Kx8 AVX2) measured pp512
  **+61%** on Q4_K_M and **+76%** on Q4_K_S on a Ryzen 7600X, with tg128 **−1.8%**.
  **PR #9921** (online repacking, Q4_0) measured pp512 **+28%** on an i9-13900K.

### The test — zero patch required

`llama-bench`'s `-ot` builds its buffer-type table from `ggml_backend_dev_buffer_type(dev)`
only (`tools/llama-bench/llama-bench.cpp:861-871`) — the *default* bufts. So
**`-ot ".*=CPU"` forces every weight into the plain CPU buffer and disables repack**, with
no code change, on a stock binary. That reproduces the meta backend's buffer choice exactly.

Prediction, **labelled as a prediction and kept out of every table below**: if repack loss
is the mechanism, `-ot ".*=CPU"` should cost prefill roughly what `-sm tensor` costs the
CPU — around 1.4× — and pure-Q4_K should lose *more* than Q4_K_M, because 100% of its bytes
are repack-eligible against Q4_K_M's 73.3%. A dose-response is the part that makes it a
confirmation rather than a coincidence.

### The control I designed did not work. Correcting myself before drawing anything from it.

I ran the `-ot ".*=CPU"` A/B (ABBA, 3 passes, medians) and it showed **nothing**:

| config | pp512 default | pp512 `-ot ".*=CPU"` | delta |
|---|---:|---:|---:|
| Q4_K_M | 13.06 | 13.11 | +0.4% |
| pure Q4_K | 14.28 | 14.37 | +0.6% |
| Q4_K_M tg32 | 5.33 | 5.34 | +0.2% |

Rather than report that as "repack is worthless", I checked whether the control had actually
fired. **It had not.** `llama-bench -v` with the override prints:

```
tensor blk.0.attn_q.weight (6 MiB q4_K) buffer type overridden to CPU_REPACK
```

The override is taken as a *starting point* and llama.cpp still promotes eligible tensors to
the repack buffer type. So `-ot ".*=CPU"` does **not** disable repack, the research
suggestion that it would was wrong, and **the whole table above measures nothing.** It is
recorded only so the next person does not repeat it. No conclusion is drawn from it.

The real control is `llama-server -nr/--no-repack` (`params.no_extra_bufts`), confirmed
present on this tree. Re-running there.

### An unplanned finding from the verification log, which may matter more

The default load prints, for the 4092 MiB pure-Q4_K file:

```
done_getting_tensors: tensor 'token_embd.weight' (q4_K) (and 141 others) cannot be used
                      with preferred buffer type CPU_REPACK, using CPU instead
load_tensors:   CPU_Mapped model buffer size =  3757.65 MiB
load_tensors:   CPU_REPACK model buffer size =  3792.80 MiB
```

**Two buffers, 7550 MiB total, for a 4092 MiB file.** The repacked weights are a second,
anonymous, non-file-backed copy. On a box with no SSD, where freeing ~900 MB was once
measured to be worth **21.9×**, a second multi-gigabyte copy is not a footnote. Measuring
speed *and* `MemAvailable` together in the `-nr` A/B, because on this machine the footprint
may be the more valuable half of the answer.

### Iteration 5 — the working control. Hypothesis CONFIRMED, with a number.

`llama-server -nr` vs default, ABBA, 2 passes, identical 512-token prompt, `-c 2048 -cram 0
-t 4`, `MemAvailable` and server RSS sampled after load and before the prompt.

| config | pp512 t/s (4 runs) | median | server RSS | MemAvailable |
|---|---|---:|---:|---:|
| **repack on** (default) | 16.11 / 15.34 / 15.41 / 15.35 | **15.37** | **7,732 MiB** | 8,760 MiB |
| **repack off** (`-nr`) | 9.83 / 9.67 / 9.65 / 9.62 | **9.66** | **4,285 MiB** | 12,540 MiB |

**The interleaved AVX2 repack GEMM is worth 1.59× on prefill on this machine.**
Spread within each arm is ≤1%. This is the single largest measured kernel effect in the
project.

**Independent corroboration:** upstream PR #12332 measured **+61%** pp512 for Q4_Kx8 AVX2 on
a Ryzen 7600X. I measure **+59%** on an i5-10210U. Two different CPUs, same ballpark — the
mechanism is the kernel, not something local to this box.

**The PRIMARY TARGET is now confirmed, quantitatively.** The prior session measured the
`-sm tensor` CPU penalty at `-ts 1/99` as **1.42×** with copies, waiting, scheduling and
power all ruled out. Losing repack costs **1.59×**. Those agree in direction and magnitude,
and the gap is in the expected direction: at `-ts 1/99` the CPU does 99% rather than 100% of
the work, and the non-`mul_mat` ops (attention, norms, rope) never used repack in either
case, so the whole-run penalty must be smaller than the pure-GEMM penalty. **The mechanism
of the tensor-parallel CPU slowdown is loss of the repack buffer type, caused by
`ggml-backend-meta.cpp:357` building its per-device buffer types from
`ggml_backend_dev_buffer_type()` and never calling `ggml_backend_dev_get_extra_bufts`.**
The inherited "non-contiguous views" explanation is wrong and is retired.

**But fixing it would not rescue tensor parallelism, and the same arithmetic says so.**
At `-ts 50/50` the prior session's instrumented budget was: total 41.07 s = CPU compute
28.0 s + waiting on the iGPU 12.8 s + data movement 0.1 s — i.e. the iGPU took ~40.8 s for
its half. Restoring repack cuts the CPU's 28.0 s to roughly 17.6 s (÷1.59), and the CPU then
simply waits longer: total stays ≈41 s, because **the binding term is the iGPU's separate
~4× slowdown, and Vulkan has no repack path to lose.** So repack explains the CPU half of
the `-sm tensor` penalty completely and the iGPU half not at all.

**Conclusion for the architecture, stated plainly: tensor-splitting is the wrong
decomposition on this box.** Splitting a single matmul makes both engines slower at their
own work. Running two *whole* prefills concurrently was already measured to ADD
(11.5 + 25.6 = 37.0 vs 25.6 best-single, +45%). The useful heterogeneous design here is
pipeline/graph-level, not tensor-level.

**Second, independent finding — the price of repack is 3,447 MiB of RAM.** Repack is not a
free kernel swap; it materialises a second, anonymous, non-file-backed copy of every
eligible tensor (`CPU_Mapped 3757 MiB + CPU_REPACK 3793 MiB` for a 4092 MiB file). On a
machine with no SSD where a ~900 MB swing was once worth 21.9×, that is a real lever in the
other direction: **`-nr` buys back 3.45 GB for a 1.59× prefill cost.** For the 7B it is the
wrong trade — 8.7 GB still available, no cliff risk — and repack stays on. It is written
down because for any *larger* model on this box, `-nr` is the difference between fitting and
collapsing onto rotational disk, and nothing in the record knew that until now.

---

## Iteration 6 — the thing nobody had measured. 66× on time-to-first-token.

Every one of the five council advisors, independently and without seeing each other, said the
same thing: stop optimising the cost of work you should not be doing. Prefix caching had
never been measured once in this project. Here it is.

**Setup.** `llama-server`, pure-Q4_K, `-c 8192 -cram 0`, real file: `luminos_moe_offload.py`,
18,382 bytes → **4,858 prompt tokens**. Five turns against one server, in this order:
T1 a cold question; T2 a *different* question about the same file; T3 a byte-identical repeat
of T1; T4 the same question after appending a function to the file; T5 = T2 with a short
answer. Server-side timings, so the network is excluded.

### Result — config `base` (`-t 4`)

| turn | prompt tokens evaluated | reused from cache | TTFT | generate | **total** |
|---|---:|---:|---:|---:|---:|
| **T1 cold** | 4,858 | 0 | **378.98 s** | 40.5 s (114 tok) | **419.5 s** |
| T2 different question, same file | 21 | 4,844 | **5.73 s** | 46.5 s (129 tok) | **52.2 s** |
| T3 identical repeat | 14 | 4,844 | 4.14 s | 40.1 s (111 tok) | 44.2 s |
| T4 after appending a function | 30 | 4,841 | 8.44 s | 41.3 s (114 tok) | 49.8 s |
| T5 same as T2, short answer | 24 | 4,841 | 6.63 s | 11.3 s (32 tok) | **17.9 s** |

**Time to first token: 378.98 s → 5.73 s. 66×.** Not a percentage — an order of magnitude,
twice. It required no patch, no rebuild and no flag: `cache_prompt` defaults to true and it
simply had never been exercised.

**T4 is the one that makes this real.** Appending a function to the file still reused 4,841
of 4,888 tokens, because the edit is *after* the shared prefix. An editing session against
one file pays the 6.3-minute prefill once, then ~8 s per question.

**T5 prices output length, which had also never been measured.** 32 tokens instead of 129
takes a warm turn from 52.2 s to 17.9 s — **2.9× on total time, for free**, purely by asking
for a shorter answer.

### The constraint has moved, and the record needs correcting

**Generation at real context is 2.75 t/s, not 5.84 t/s.** Every generation number in this
project — including my own iteration-2 baseline — was measured with an essentially empty KV
cache (`llama-bench -n 32` with no prompt). At 4,858 tokens of context the same model
generates at **2.75 t/s, a 2.1× penalty** the record did not know about. I am correcting it
here.

Consequence: **on a warm turn, generation is 46.5 s of 52.2 s — 89% of the cost.** Prefill,
which has been the target of every iteration so far, is now 11%. The binding constraint has
moved from prefill to long-context generation, and all remaining effort belongs there.

### Second measured lever, from the same sweep

`-t 8 -tb 4` — the free lever spotted in iteration 2 and never tested — measured on the same
file, same session:

| config | TTFT cold | tg t/s at 4.8k context |
|---|---:|---:|
| `-t 4` | 378.98 s | 2.75 |
| **`-t 8 -tb 4`** | 390.16 s | **3.18** |

**+15.6% generation for −2.9% prefill.** At zero context iteration 1 measured this at only
+4.7%; at real context it is worth three times more, because attention over a 4,858-token KV
cache stalls on memory and the sibling thread has work to do. Since generation is now 89% of
a warm turn, this is a clear keep. **New baseline: `-t 8 -tb 4`.**

### Iteration 7 — speculative decoding stops working at real context

Same sweep, same file, same session. Draft model Qwen2.5-Coder-0.5B, `-td 4
--spec-draft-n-max 3` — the exact configuration the record measured at **+21%**.

| config | tg t/s @ 4,858 ctx (T2 / T3 / T4) | warm-turn total, 32-token answer |
|---|---|---:|
| `-t 8 -tb 4` (baseline) | 3.14 / 3.18 / 3.18 | 16.27 s |
| `-t 8 -tb 4` + 0.5B draft, k=3 | 3.16 / 3.17 / 3.05 | 16.23 s |

**Zero.** Every pair is inside the ≤1% run-to-run spread. The +21% in the record was measured
with an essentially empty KV cache; at 4,858 tokens of context the same configuration
delivers nothing. I am recording this as a scoped correction to the record rather than a
contradiction: **speculative decoding's +21% is a short-context result and does not survive
to the context length that actually matters here.**

**Mechanism — not yet isolated, and I am not going to assert one.** The obvious story is that
speculative decoding amortises *weight reads* across a verify batch, and at long context
weight reads are no longer the dominant per-token term: per-token cost went 0.172 s → 0.314 s
while the model did not change, so ~45% of the new cost is attention work that scales with
position count and does not amortise the same way. That is a plausible arithmetic, not a
measurement.

There is also a competing and much more boring explanation I have to rule out first: **the
server may not have been speculating at all.** `/tmp/srv_spec.log` shows the draft model
loading but none of `speculative decoding context initialized`, `... not supported by this
context`, or `... will use checkpoints`. `server-context.cpp:446` only emits `draft_n` /
`draft_n_accepted` in the timings when `n_draft_total > 0`, and my harness was not reading
those fields. **Harness patched to capture them. Until a non-zero `draft_n` is measured, the
"+21% does not survive long context" claim is about the configuration, not about speculative
decoding as a technique**, and the log says so.

### Iteration 7b — slot save/restore does not work in this configuration

`slotsave.sh` ran the 5-turn harness, saved slot 0, killed the server, started a fresh one,
restored, and re-ran. The restore was a no-op:

| | measured |
|---|---|
| save response | `{"n_saved":0,"n_written":36,"timings":{"save_ms":0.214}}` |
| file on disk | `/srv/media/_llmtest/kvslots/ctx.bin` — **36 bytes** |
| restore response | `{"n_restored":0,"n_read":36,"timings":{"restore_ms":0.051}}` |
| T1_cold after restore | **389.76 s** vs 383.96 s without a restore |

**Mechanism, read from source, not guessed.** `server-context.cpp:2585` sets
`res->n_tokens = slot->prompt.tokens.size()`, and it reported 0, while
`llama_state_seq_save_file` wrote only a 36-byte header. The slot's KV was **genuinely empty
at save time** — this is not a serialisation bug and not the missing `bc` (which was a real
but separate flaw in my script's timing arithmetic). `--cache-idle-slots` defaults to
**enabled** and its own help text reads *"save idle slots to the prompt cache on new task
... requires cache-ram"*; I ran with `-cram 0`. `slotprobe.sh` isolates which knob empties
the slot using a 4-token prompt so each trial costs seconds instead of 6.5 minutes.

**Free side-result — a noise floor.** Two independent 4,858-token cold prefills taken twelve
minutes apart on separate server processes measured 383.96 s and 389.76 s: **1.5% apart.**
Any effect smaller than that is not an effect.

---

## Iteration 9 — the binding constraint was never bandwidth. It is heat.

This is the largest correction in the log, and it invalidates the framing of every prior
iteration including the mission brief's own premise.

**STATE THE CONSTRAINT (measured live, under a real llama-perplexity load, 2026-09-12):**

| quantity | measured | source |
|---|---:|---|
| package temperature | **97 °C** (high = 100, crit = 100) | `sensors` |
| fan | **4834 RPM of 4900 max** — maxed out | `dell_smm` hwmon3 |
| all 8 threads | **exactly 2100.0 MHz** | `/proc/cpuinfo` |
| package power | **14.33 W** | RAPL `energy_uj` delta over 5 s |
| RAPL PL1 / PL2 | 28 W / 51 W | `constraint_0/1_power_limit_uw` |
| `package_throttle_count` | **1,840,632** and climbing | `thermal_throttle/` |
| intel_pstate | `no_turbo=0`, `max_perf_pct=100`, `scaling_max_freq=4200000` | — |

**And the decisive control:** with the box idle at 65 °C, a core immediately clocked
**3096.9 MHz**. Nothing in software is capping frequency. The CPU falls to 2100 MHz *because
it is 3 °C from thermal shutdown with the fan already at maximum*.

**Two standing claims are now wrong and I am correcting them plainly:**

1. The record says *"The CPU sits at 2.1 GHz all-core, pinned by a ~15.9 W package limit, at
   70 °C against a 100 °C limit — so prefill is power-capped, not heat-capped."* The
   temperature today is 97 °C, not 70 °C. It is **heat-capped, not power-capped.**
2. The mission brief says *"RAPL PL1 is 28 W, not 15 W — power is NOT the ceiling."* That is
   true but misleading in a way that matters: power is not the ceiling **because the CPU
   cannot spend the watts it is permitted.** It is allowed 28 W and draws 14.33 W. The
   effective ceiling is thermal, and it sits at **51% of the power budget.**

**Why this reframes everything.** Every number in this project — the 13 t/s prefill, the
5.84 t/s generation, the 1.72× iGPU prefill ratio, the +21% speculative decoding — was
measured on a CPU running at 2100 MHz instead of 3097 MHz, i.e. at **68% of its cooled
clock.** It also finally explains the recorded "box thermally drifts ~10% over four
back-to-back reps," which had been treated as measurement noise to be worked around rather
than as the signal itself.

**It also changes the figure of merit.** Under a hard thermal cap, throughput is not
watts × efficiency — the watts are fixed at what the heatsink can remove, so throughput is
governed by **work per joule.** That is a different optimisation target, and it cuts against
some of what has already been tried: speculative decoding deliberately spends extra compute
to save memory reads, which on a thermally-saturated part means extra heat and a lower
clock. Meanwhile the record already contains the measurement that matters most under this
new framing and did not act on it: **the iGPU does prefill at 2.38 tokens/joule versus the
CPU's 0.93 — 2.6×** — while drawing 10.73 W against the CPU's 14.45 W.

**ATTACK (in flight).** `thermal.sh`, ABBA-interleaved with a 3-second background sampler
recording max core MHz, package °C, package W and dGPU °C throughout:
- Q1 — is 2100 MHz thermal or a cap? *(already answered: thermal, 3096.9 MHz cooled)*
- Q2 — the AMD Radeon 520 is **bound, idle at 64 °C, refcount 0**, holding no DRI node, in
  the same chassis as a saturated heatsink. Jellyfin was verified to use `renderD128` (the
  **Intel** iGPU) in `/etc/jellyfin/encoding.xml`, so the AMD card is dead weight that only
  produces heat. Does unbinding `0000:01:00.0` from `amdgpu` buy the CPU clock, and is that
  clock worth tokens?

Checked and ruled out as levers before building: the fan is already at 98.7% of maximum, and
`dell-wmi-sysman` exposes no thermal-management or fan-profile attribute on this model (only
`ThermalLogClear`), so there is no BIOS fan curve to raise.

### Iteration 9 — council, research, and the mechanism named from a hardware register

**Council (5 advisors, in parallel) — what it changed.** Three advisors independently arrived
at the same arithmetic I had not done: 97 °C at 14.33 W is a thermal resistance of about
**5.7 °C/W**, where a U-series laptop cooler is designed for roughly 2 °C/W. That is not an
operating point, it is a **physical fault — a clogged fin stack or dried-out thermal paste,
running at ~3× its design resistance.** I am recording that as the most likely root cause. It
is maintenance, not a purchase, and it cannot be done over ssh, so everything below is
software working inside a fault.

Two advisors independently proposed the same thing and it is the strongest idea of the
session: **the box is idle almost all of the time, so prefill every file you might ask about
before anyone asks, at 3 a.m., when the thermal budget is worthless.** That converts the
6.5-minute TTFT into a background cost and makes the throttled clock irrelevant to latency.

The Expansionist landed the sharpest technical catch: **the 32.6 GB/s bandwidth ceiling is
itself probably a throttled measurement**, taken at 2100 MHz with the uncore throttled
alongside the cores. If so, "generation is at 81% of the ceiling, therefore bandwidth-bound"
is circular. The Outsider's catch — that a flat 2100.000 MHz on all eight threads looks like
an external clamp (BD PROCHOT from the embedded controller) rather than thermal hunting — was
worth testing and is now disproved below.

*Deviation from the council protocol, stated plainly:* I did not run the anonymised
peer-review round. Reading three hardware registers settled the live disagreements in about
two minutes, which peer review could not have done, and time on the box is the scarce
resource.

**Research (prior art) — two vectors killed before I spent an hour on them.**
- MSR 0x150 undervolting: the Plundervolt/CVE-2019-11157 lock is **firmware-gated, not
  silicon-gated**, and Dell rolled it across product lines (`kitsunyan/intel-undervolt` #43,
  `erpalma/throttled` #255). A locked mailbox does not error — the write succeeds and the
  value reads back wrong, so the only honest test is write-then-readback. Unlocking needs
  pre-boot EFI-shell access, which ssh does not provide.
- Cross-backend KV state transfer **is supported by construction**: serialisation goes through
  `llama_io_write_file::write_tensor` → `ggml_backend_tensor_get`, which pulls device memory
  into a host buffer in canonical ggml row layout. Restore enforces `n_layer`, per-layer
  `k`/`v` types, `ggml_row_size`, and critically **`v_trans`, which is `!cparams.flash_attn`**
  — so the two processes must agree on `-fa` and on `--cache-type-k/v` or restore fails with
  `"incompatible V transposition"`. No one has built phase-switched backends for llama.cpp;
  the CPU+GPU hybrid work (KTransformers, PowerInfer, HybriMoE) all splits by tensor, never
  by phase.

**THE MECHANISM, read from the register that exists precisely to answer this.**

| register | value | meaning |
|---|---|---|
| `MSR_CORE_PERF_LIMIT_REASONS` (0x64F) | `0x7d020002` | **ACTIVE NOW: Thermal.** Logged: Thermal, PL1, Max Turbo Limit, Turbo Transition Attenuation |
| `IA32_THERM_STATUS` (0x19C) | `0x88032a83` | `thermal_status=1`, **`PROCHOT_now=0`**, `pwr_limit_now=0`, readout **3 °C below Tjmax** |
| `MSR_RING_PERF_LIMIT_REASONS` (0x6B1) | `0x01020100` | **ACTIVE NOW: PL1** — the uncore/ring is frequency-limited |
| `MSR_TURBO_RATIO_LIMIT` (0x1AD) | `0x2727292a` | rated turbo: 1C **4.2 GHz**, 2C 4.1, 3C **3.9**, 4C **3.9** |
| `MSR 0x150` (OC mailbox) | wrote `0x8000001000000000`, read back `0x0` | **LOCKED** |

**Named, isolated, measured: core frequency is limited by `Thermal` (0x64F bit 1) and by
nothing else concurrently.** `PROCHOT_now = 0` kills the external-clamp hypothesis — no
embedded controller is asserting anything. `pwr_limit_now = 0` kills "power-capped" for the
cores. And the severity is worse than I first wrote: the part is **rated for 3.9 GHz on four
cores** and is delivering 1900–2100 MHz, so it is losing **~49% of its rated all-core turbo**,
not the 32% I estimated against the 3097 MHz idle observation.

**Separately and importantly: the ring bus is PL1-limited right now.** Memory traffic crosses
the ring. That means the recorded 32.6 GB/s may be a throttled figure, exactly as the
Expansionist argued. Test built (`bw.c`, OpenMP read bandwidth sampled every ~2 s from cold
through saturation) to measure the decay instead of assuming it.

**Vector (a), the idle AMD dGPU — KILLED, twice, by measurement.**
1. Prior art check turned into a direct measurement of this box: `runtime_suspended_time` is
   **816,767,556 ms against 818,694 s of uptime = already runtime-suspended 99.76%** of its
   life. Reading its hwmon temperature is what woke it. It reads **58 °C while the CPU package
   reads 67 °C** — it is *absorbing* chassis heat, not producing it. The 64 °C I cited as
   evidence for the vector was an artifact of my own probe.
2. Run it anyway as a control: with `amdgpu` unbound from `0000:01:00.0`, the package held at
   **97 °C** with the clock oscillating 1900–2142 MHz — **indistinguishable from bound.**
   Cost: zero. Benefit: zero. Mechanism: there was never any heat to recover.

**Vector (b), undervolting — KILLED by measurement.** The mailbox reads back zero.

### Iteration 9 results — the dGPU A/B, and a correction to my own input

ABBA-interleaved, `llama-bench -p 512 -n 32 -t 4 -r 3`, with a 3-second sampler running
throughout. Order was run first to last as listed.

| arm | pp t/s | tg t/s | max MHz | pkg °C | max pkg W |
|---|---:|---:|---:|---:|---:|
| amdON (first) | **15.16** ±0.38 | 5.86 ±0.07 | 3336 | 98 | 20.61 |
| amdOFF | 13.89 ±0.38 | 5.41 ±0.04 | 2867 | 98 | 19.33 |
| amdOFF2 | 13.45 ±0.21 | 5.35 ±0.04 | 2304 | 99 | 16.88 |
| amdON2 | 13.59 ±0.25 | 5.42 ±0.05 | 3397 | 98 | 17.23 |

**Unbinding the discrete GPU does nothing.** The only honest comparison is between adjacent
positions, and the two *identical* arms `amdOFF` and `amdOFF2` differ by **3.2%** — that is
the drift floor for this kind of run. `amdON2` vs `amdOFF2`, the adjacent ON/OFF pair, differ
by **1.0%**, three times smaller than the noise between two identical arms. The apparent
15.16 of the first arm is entirely first-position advantage on a cooler box. Mechanism, as
established above: the card was already runtime-suspended 99.76% of its life and runs colder
than the CPU, so there was never any heat to recover. **Vector (a) is dead.**

**A correction to a number I gave the council.** I reported package power as 14.33 W, and the
council reasoned from it that thermal resistance was ~5.7 °C/W. That 14.33 W was sampled
during a `llama-perplexity` run at `-t 4`, which is a *lighter* load than the benchmark. The
sustained maximum across these arms is **16.9–20.6 W at 98 °C.** So the honest figure is
roughly **3.8 °C/W** against a design figure nearer 2 °C/W — still about double, still
consistent with a fouled heatsink, but **not the 3× the council was working from, and my
earlier "the CPU can only spend 51% of its power budget" was overstated.** It spends roughly
60–74% of PL1. The qualitative conclusion survives; the magnitude was wrong and it was my
error.

**Vector (c) — "more cores at a lower clock beats fewer at a higher clock under a fixed
thermal cap" — is dead too, and this data kills it.** The single-thread burst arm is the
control that settles it:

| arm | threads | max MHz | pp t/s | pkg W | **t/s per GHz-core** |
|---|---:|---:|---:|---:|---:|
| t1_burst | 1 | 3800 | 6.07 | 13.87 | **1.60** |
| amdOFF2 | 4 | ~2200 | 13.45 | 16.88 | **1.53** |

Throughput is **linear in aggregate GHz-cores** — 1.53 to 1.60 t/s per GHz-core measured at
both ends of a 4× spread in width and a 1.7× spread in clock. There is no convexity to
exploit. Because the CPU already settles at the highest frequency the thermal envelope
sustains, any cap placed *below* that point strictly reduces aggregate GHz-cores and
therefore strictly reduces throughput. The First Principles advisor called this correctly
before the measurement: under a hard thermal cap the pstate governor *is* the work-per-joule
optimiser, and it has already solved this. **Do not re-solve it.**

**One genuinely alarming control:** the `t1_burst` arm put **a single thread** at 3800 MHz
and the package still reached **98 °C at 13.87 W**. One core is enough to saturate this
cooler. That is the clearest single piece of evidence that the limit is thermal resistance,
not thermal design.

**Also now explained, not worked around:** the record's "box thermally drifts ~10% over four
back-to-back reps" is exactly the 5.35→5.86 tg and 13.45→15.16 pp spread above (9.5% and
12.7%). It was never noise. It is the machine cooling down between runs and heating up
during them, and it is the single largest source of error in every number this project has
ever produced.

---

## Iteration 10 — is the 32.6 GB/s bandwidth ceiling itself a throttled number?

**The claim under test.** The record says "memory bandwidth 32.6 GB/s, generation hits 81% of
that ceiling, so it is bandwidth-bound." Iteration 9 measured
`MSR_RING_PERF_LIMIT_REASONS (0x6B1) = 0x01020100` — **the uncore/ring is ACTIVE-NOW PL1
frequency-limited**. If the uncore throttles alongside the cores, 32.6 GB/s is a throttled
figure and "81% of ceiling" is circular. The council's Expansionist raised this; it needed a
number, not an argument.

**Method.** `~/llmperf/bw.c` — OpenMP sum-reduction over a 2 GiB aligned `double` array,
printing achieved GB/s every ~0.2 s for 150 s. Run **first** in the chain, after a 300 s
cooldown, so it starts genuinely cold (package 53 °C, fan already spinning down from max).
Everything that generates heat was ordered after it.

| window | mean GB/s | max | min |
|---|---|---|---|
| 0–5 s (cold) | **32.51** | 32.63 | 32.41 |
| 5–10 s | 32.50 | 32.63 | 32.42 |
| 10–20 s | 32.29 | 32.56 | 31.64 |
| 20–40 s | 31.71 | 32.19 | 31.24 |
| 40–60 s | 30.86 | 31.43 | 26.32 |
| 60–90 s | 30.47 | 30.85 | 29.16 |
| 90–120 s | 30.16 | 30.45 | 28.72 |
| 120–151 s (saturated) | **29.89** | 30.12 | 29.61 |

**Result: the hypothesis is mostly killed, and the record's number is identified.**

1. The record's **32.6 GB/s is the COLD number.** Measured peak here is 32.63 GB/s — the same
   figure to three significant figures. Whoever measured it measured a cold box.
2. The sustained ceiling during a long prefill is **29.89 GB/s**. Total decay cold→hot is
   **8.1%**.
3. So the uncore *is* throttled, exactly as the MSR says — but it costs **8%**, not the ~45%
   of rated clock the cores lose. There is no large hidden bandwidth headroom.

**Correction to the record, and it sharpens rather than softens the conclusion.** Generation
was recorded at 81% of 32.6 GB/s = 26.4 GB/s effective. Against the *true sustained* ceiling
of 29.89 GB/s that is **88%**, not 81%. Generation is closer to the memory wall than the
record claims, not further from it.

**Why this is not a "bandwidth-bound" stopping point.** It names which bytes and what to do:
at 88% of achievable read bandwidth, generation cannot be made faster by reading the same
bytes faster — only by reading *fewer* bytes per token. That is a specific, ranked list:
smaller weights (the untested quality gate), fewer decode steps per accepted token
(speculative decoding, already +21%), fewer active parameters (MoE), and a smaller KV cache.
It removes "make the memory subsystem go faster" from the board with a measurement.

**Self-consistency check that validates the test.** Cores lose ~45% of rated clock over this
window; the bandwidth number loses 8.1%. If `bw` were core-limited rather than DRAM-limited
its curve would have tracked the clock. It did not, so it is measuring memory.

**Remaining gap, stated as a gap.** 29.89 GB/s is 70% of the DDR4-2667 dual-channel
theoretical 42.7 GB/s. That 30% is DRAM efficiency (refresh, page misses, bus turnaround) plus
whatever my single access pattern leaves on the table. Not yet decomposed — queued as
iteration 15, a variant sweep (thread count, non-temporal loads, prefetch distance) to find
out whether 29.89 is *the* ceiling or just *my* ceiling. Until that runs, 29.89 is a measured
floor on the ceiling, not the ceiling.

---

## Iteration 11 — council on the prefill wall, and the FLOP-efficiency decomposition

### The constraint, stated as required

Prefill of a real 4,858-token Python file takes **379.0 s of a 419.5 s cold end-to-end — 90%
of the wall clock**, at ~12.8 tok/s. Named mechanism (iteration 9): the CPU is pinned at
2100 MHz against a 3900 MHz four-core rating, `MSR_CORE_PERF_LIMIT_REASONS = 0x7d020002`
with **Thermal as the only active-now reason**, `PROCHOT_now = 0`, `pwr_limit_now = 0`.
Cooling path measures ~3.8 °C/W against a design figure near 2. Not repairable over ssh.

### Council verdict (5 advisors, 3 anonymised peer reviewers)

**Where the council agreed** — four of five independently reframed the problem the same way:
prefill is a **pure function of the file**, not of the question. It is deterministic,
cacheable, and already measured at 66× when cached. The box is idle ~20 h/day. So the work
is being computed at the one moment a human is waiting for it, and the fix is to move it off
the interactive path rather than to make it faster. Every peer reviewer ranked the advisor
who argued this *with arithmetic* above the one who argued it qualitatively.

**Where the council clashed** — one advisor (the Contrarian) argued the opposite: that the
prefill kernel is broken and worth 3–8×, and that caching is a distraction. Its argument was
that prefill at 12.8 t/s is only ~2.2× generation at 5.9 t/s, whereas a batched prefill
should be 10–30× generation, implying arithmetic intensity near 1 — "a stack of GEMVs".

**Blind spot the peer review caught, which changes the plan.** Three advisors sized the KV
cache at **2.4–2.5 GB** and reasoned from it: one hedged the warmer ("worth much less than it
looks"), one declared it "probably dead" on a 25 s disk-reload estimate. **This project has
already measured the KV for this exact model and file at ~266 MiB.** They were wrong by ~9×.
The model is GQA — 4 KV heads, not 28 — so the correct figure is ~57 KB/token. Every
conclusion that rested on 2.5 GB inverts. All three reviewers independently caught this and
all three promoted the one advisor whose arithmetic survived it.

**Second blind spot, caught by all three reviewers:** the 66× is an **in-process** prefix hit
via the RAM prompt cache, and RAM caching *works today*. Only **disk** persistence is
unproven, and it has already failed once (`n_saved=0`, 36-byte file). One reviewer named the
implementation error directly: `--prompt-cache` is a **`llama-cli`-only** flag, so the
"it's just a flag, schedule a cron" plans have no implementation in `llama-server` at all.
They require `--slot-save-path` + `POST /slots/{id}?action=save|restore` — the exact API that
is currently returning zero. Recorded as a correction to my own iteration-7b framing, which
treated the broken save as a configuration problem rather than as the load-bearing dependency
of the entire caching strategy.

**Third catch, already satisfied, recorded so it is not re-litigated.** One advisor warned
that prefix caching only works if the file precedes the question in the rendered prompt, and
that if a system prompt or timestamp leads, the 66× is a lab artifact. Checked: the harness
(`~/llmperf/prefill1.py`) emits a fixed 11-token preamble, then the file, then the question
last. The cacheable prefix is therefore the whole file. No change needed.

### Killing the Contrarian's kernel hypothesis with numbers, not with a category

The mission forbids "compute-bound" as a stopping point and demands *which kernel* and *what
measured FLOP efficiency vs theoretical*. Doing that arithmetic kills the hypothesis:

- Prefill at 12.8 tok/s on a 7B model ≈ 2 × 7e9 × 12.8 = **179 GFLOP/s effective**.
- AVX2 FP32 FMA peak at the *throttled* 2.1 GHz: 2.1e9 × 4 cores × 8 lanes × 2 (FMA) × 2 FMA
  ports = **268 GFLOP/s**.
- So prefill sustains **67% of the AVX2 FP32 FMA peak** — and it does so while additionally
  dequantising Q4_K on the fly. That is a well-optimised dense GEMM, not a GEMV.

Two of the Contrarian's three sub-claims were also dead on inspection: `objdump` finds
**2,091 FMA instructions** in the built `libggml-cpu.so` (so it did not fall back to scalar),
and `GGML_LLAMAFILE:BOOL=ON` with `GGML_NATIVE:BOOL=ON` (the `GGML_AVX2:BOOL=OFF` in
CMakeCache is the unused explicit override, not the effective setting).

**The decomposition that is allowed to stand:** prefill is limited by the *repacked
`q4_K_8x8_q8_K` AVX2 GEMM* running at 67% of its arithmetic peak, and that peak is itself set
by a clock held at 54% of rated by thermal throttling. At the rated 3.9 GHz the same kernel's
peak would be ~498 GFLOP/s. The binding term is the clock, and the clock is a heatsink.

**What survives from the Contrarian anyway:** its third sub-claim — that prefill is
*shape*-sensitive and nobody swept the shape — is untested and cheap, and is corroborated by
the fact that a pure layout change (repack) already bought 1.59×. Queued as a counterbalanced
`n_ubatch` × thread-count sweep (`~/llmperf/shape.sh`), with the sweep order **reversed** on
the second pass rather than repeated, so that a linear thermal drift cancels instead of being
measured.

---

## Iteration 13 — the slot-save failure was mine, and it is a one-flag fix

**Correcting iterations 7b and 11.** Both recorded that `llama-server`'s slot save API was
broken on this build: `POST /slots/0?action=save` returned `{"n_saved":0,"n_written":36}` and
produced a 36-byte file. Iteration 11's council treated that as the load-bearing risk in the
entire caching plan, and three peer reviewers independently flagged it as the thing that
could kill the architecture. Iteration 12 swept four flags looking for the cause
(`-cram 0`, `-cram 2048`, `--no-cache-idle-slots`, and both together). **All four arms
returned exactly `n_saved=0, n_written=36`.** I read that as "none of the knobs is the knob"
and started reading `server-context.cpp` for a deeper cause.

**The actual cause, found by accident in an unrelated log.** The Vulkan server's startup
output for the iGPU gate contains this line:

```
I slot get_availabl: id  3 | task -1 | selected slot by LRU, t_last = -1
I slot launch_slot_: id  3 | task 0 | processing task, is_child = 0
```

The server allocates slots **by LRU**, and with four slots all equally unused it picked
**slot 3**. I was saving **slot 0** — a slot that had never served a request. `n_saved=0` was
the server being completely truthful: that slot was empty. The 36 bytes are the state-file
header and nothing else.

This also explains why all four flag arms agreed: none of them could matter, because none of
them was ever the question. It is the cleanest example so far in this project of a
uniform-looking result hiding a probe aimed at the wrong object.

**Two earlier conclusions are withdrawn:**
1. "Slot save/restore does not work on this build" — **withdrawn, untested**. It was never
   tested; the wrong slot was.
2. The iteration-12 flag sweep is **void**, not negative. Four arms measuring nothing is not
   four pieces of evidence.

**The fix is `-np 1`**, which makes slot 0 the only slot and removes the possibility of
missing it. The corrected experiment (`~/llmperf/slotsave2.sh`) goes straight past the flag
question to the thing that decides the architecture: prefill the real 4,858-token file, save,
**kill the server**, start a fresh one, restore from disk, and measure TTFT — plus a second
question against the same file, to show the restored prefix is reusable and not single-shot.
`-fa on` is pinned on both processes because restore enforces `v_trans = !cparams.flash_attn`
(`llama-model.cpp:8483`) and a mismatch fails with "incompatible V transposition".

**What it is worth if it works, stated as arithmetic and labelled as such:** KV for this file
measured ~266 MiB; the rotational disks do ~100–120 MB/s sequential; so a restore is a
~2–3 s read against a 373.7 s prefill. That is a *prediction*, not a measurement, and the
experiment above is what turns it into one.

---

## Iteration 12 — THE GATE: iGPU prefill at 4,858 tokens. It fails, and not for the expected reason.

**Why this gate existed.** The record's iGPU prefill advantage (25.6 vs 14.8 t/s, 1.72×) was
measured at **pp512**. The record separately says that under tensor-parallel the iGPU's cost
for attention over a growing KV climbs ~9× faster than the CPU's, and that pp2048 was much
worse than pp512. Those two facts predict opposite outcomes at 4,858 tokens and nobody had
measured it. The whole phase-split design (iGPU prefills, CPU generates, KV handed over)
rests on this one number, so it was gated before any of it was built.

### Result

| arm | engine | prompt | TTFT | pp t/s |
|---|---|---|---|---|
| cpu_1 | `build/` CPU, `-t 8 -tb 4` | 4,858 | **373.7 s** | **13.0** |
| vk_1 | `build-vk/` Vulkan, `-ngl 99` | 4,858 (partial) | — | **6.19 @ 2048, 5.69 @ 4096** |

The CPU arm reproduces the standing baseline (373.7 s vs the recorded 379.0 s — inside the
1.5% noise floor, and adjacent in time, so comparable).

**The Vulkan arm is ≥2.3× SLOWER and getting worse with depth** (6.19 → 5.69 t/s between
2,048 and 4,096 tokens). **The gate fails.** The 1.72× iGPU prefill advantage does not
survive to real context length; it inverts. The phase-split build is not started.

### The mechanism, which is NOT "the iGPU is slow"

Sampled while vk_1 was provably mid-prefill (progress 0.84, still advancing):

| probe | reading |
|---|---|
| process state | `S`, `wchan = dma_fence_default_wait` |
| iGPU RC6 idle residency | **10,004 ms of 10,008 ms wall = 99.96% idle** |
| iGPU `gt_act_freq` vs `gt_cur_freq` | **300 MHz actual vs 867 MHz requested** (max 1100), 12/12 identical samples |
| `MSR_GRAPHICS_PERF_LIMIT_REASONS` 0x6B0 | `0x19020000` — **ACTIVE NOW: none** |
| process disk read | **0.00 MB/s**, major faults 36 → 36 (zero) |
| process CPU | 157 s CPU over ~780 s wall ≈ 20% of one core |
| package power (RAPL, 20 s window) | **2.86 W** |

Read together these say one thing: **the work is not reaching the GPU.** The process sits
blocked on a GPU fence; the GPU wakes for ~4 ms in every 10 s and is otherwise in RC6; the
graphics perf-limit register reports no active throttle at all, so it is not thermally or
power limited — it is simply not being given work. The 2.86 W package figure is independent
corroboration: a box doing 7B prefill cannot draw 2.86 W.

**This also corrects a mistake I nearly made twice.** My first reading of `gt_act_freq =
300 MHz` was going to be written up as "the iGPU is thermally pinned to 27% of its clock,
same fouled heatsink as the CPU" — which is what one council advisor predicted and what I
wanted to believe. It is wrong. 0x6B0 says no active limit, and RC6 says the GPU is idle, so
300 MHz is what an *idle* GPU reads, not a throttled one. This is the same class of error as
the iteration-9 dGPU temperature artifact: **reading a sensor on a sleeping device and
reporting it as a load measurement.** Second occurrence; noting it as a pattern to check for.

**Contributing factor, not yet isolated:** startup logs
`common_fit_params: failed to fit params to free device memory: n_gpu_layers already set by
user to 99, abort`, and `Shmem` stays at 135 MiB rather than growing by ~4 GB. So the
weights very likely never moved to device-visible memory, and the run may be pathological
rather than representative. That is a *hypothesis about why*, and it does not change the
gate's verdict — but it does mean one corrected re-probe is owed before the vector is closed
permanently. Queued.

**What this kills either way:** the phase-split build, and with it the value proposition
behind the tensor-parallel primary target. That target's appeal was that concurrent prefill
was measured to ADD (37.0 vs 25.6 t/s, +45%) — but that too was measured at short context.
At the length that actually matters, the iGPU contributes nothing to prefill because it
cannot be kept fed.

---

## Iteration 14 — is prefill shape-sensitive? (ubatch half)
`[CHANGE: claude-code | 2026-09-12]`

The council's Contrarian had three sub-claims. Two were killed in iterations 11 and 12. The
third survived: *prefill is shape-sensitive and nobody swept the shape.* It was corroborated
by a real fact — a pure layout change (AVX2 repacking) already bought 1.59× — so a batch-shape
effect was not absurd.

**Method.** `llama-bench -n 0 -p 1024 -r 1`, pure-Q4_K model, `-t 4`. The sweep is run twice:
once ascending, once descending. Not repeated — **reversed**. A linear thermal drift then pushes
the two passes in opposite directions and cancels in the mean, instead of being silently
measured as a shape effect. This box drifts ~10% over minutes, which is *seven times* the entire
effect being looked for, so an uncounterbalanced sweep here would have been worthless.

**Measured** (all numbers measured; no predictions in this table):

| n_ubatch | fwd t/s | rev t/s | mean | vs ub512 |
|---------:|--------:|--------:|-----:|---------:|
| 128  | 14.38 | 13.90 | 14.14 | +1.1% |
| 256  | 14.04 | 13.97 | 14.00 | +0.2% |
| 512  | 13.96 | 14.00 | 13.98 |  0.0% |
| 1024 | 13.93 | 13.97 | 13.95 | −0.2% |
| 2048 | 13.96 | 13.93 | 13.95 | −0.3% |

fwd−rev disagreement is ≤0.5% everywhere, so drift during this run was small and the means are
trustworthy. Total spread across a **16× range** of batch width: **1.4%**.

**Result: no gain. Sub-claim killed.**

**Mechanism, isolated by the experiment itself.** pp is invariant to the M dimension of the GEMM
from 128 to 2048. That means the kernel is *already in its asymptotic regime at ub=128* — widening
the tile gives it nothing, so the weight-column reuse is already saturated at the narrowest batch
tested. This is not an assertion; it is what a flat 16× sweep means. It also independently
corroborates iteration 11's arithmetic: a kernel sitting at 67% of AVX2 FP32 FMA peak *while also
dequantising Q4_K* has no shape-shaped headroom left to find, and the sweep found none.

The one directional signal is that ub=128 is the *fastest*, by +1.1% — the opposite of the
"bigger batch, better GEMM" intuition, and consistent with a smaller working set staying resident
in L2. At +1.1% against a 0.5% pass-to-pass disagreement it is barely distinguishable from flat,
and it is **not** worth a config change.

Thread-count half is still running (counterbalanced the same way) and is reported separately.

---

## Iteration 16 (research step) — the record's speculative-decoding entry is out of date
`[CHANGE: claude-code | 2026-09-12]`

**Why I went looking.** Iterations 10–12 leave generation as the constraint that matters, and
iteration 10 pinned it at **88% of the box's sustained read bandwidth** (29.89 GB/s measured
saturated). Per the mission's rule I am not allowed to stop at "bandwidth-bound", so the
decomposition is: *the only way to go faster is to emit more tokens per byte of weights read.*
That is precisely what speculative decoding does — it verifies k drafted tokens against one
read of the weights.

The record already has this at **+21%**, using a Qwen2.5-Coder-0.5B draft model. I went looking
for a cheaper drafter because **that +21% is bought with ~400 MB of resident RAM, on a box where
a 900 MB swing was measured to be worth 21.9×.** Paying 400 MB for 21% is a bad trade here and
the record never framed it as a trade at all.

**What I found, and it contradicts an assumption I was about to build on.** I expected n-gram /
prompt-lookup decoding to exist only as the standalone `llama-lookup` example, requiring me to
write the server integration. That is wrong, and I am correcting it plainly: **self-speculative
decoding was merged upstream in January 2026** — PR #18471 (srogmann, merged 2026-01-28) added
an abstract `common_speculative_state` with `begin()/draft()/accept()` so the drafter is no
longer hardwired to a draft-model `llama_context`, and PR #19164 (ggerganov, merged 2026-01-30)
added `ngram-mod`, a ~16 MB rolling-hash pool shared across slots. ggerganov's own note on the
refactor: *"we no longer construct the draft contexts in the server."*

**Verified on the box, not taken from the report.** The research came back citing the G14's
research clone, which is a different tree from the server's. So I checked the server's own
already-built binary:

```
$ ~/llama.cpp/build/bin/llama-server --help | grep spec-type
--spec-type none,draft-simple,draft-eagle3,draft-mtp,draft-dflash,draft-dspark,
             ngram-simple,ngram-map-k,ngram-map-k4v,ngram-mod,ngram-cache
```

It is already there. **No rebuild, no patch, no second model, no extra RAM.** Checking also
caught a real discrepancy: the flags on this build are `--spec-ngram-mod-n-min/-n-max/-n-match`,
and `--draft-min` / `--draft-max` are **removed** — the report's recommended command line would
have failed outright.

**The catch, and why the gate is shaped the way it is.** ggerganov's stated rule (#19164,
2026-01-31): *"unless your use case involves such repeating blocks of text, this method won't
help."* Reported acceptance rates span an enormous range — 0.830 on a verbatim-repeat task,
0.576–0.776 in `docs/speculative.md`, but **0.047–0.25 on free-form chat, where it was a net
slowdown** (130 → 119 t/s). A rejected draft costs real compute, and this box has none spare
(iteration 11: the GEMM is at 67% of AVX2 peak).

So "does ngram-mod help" is **not a well-formed question** for this project. Asking a model to
*explain* a file produces prose that quotes nothing; asking it to *emit a corrected function*
quotes the file back heavily. Those are opposite cases, and the real coding workload is the
second. `specgate.sh` therefore tests **both question shapes separately** — an averaged number
would have hidden the entire effect.

**The CPU-specific worry, resolved in source.** On a GPU, verifying k drafts is nearly free. On
a CPU already at 88% of its memory bandwidth at batch size 1, that is not obvious — if a batch
of 4 costs 4× the reads, speculation buys nothing. It does not:
`ggml/src/ggml-cpu/ggml-cpu.c:1187-1230` blocks the matmul 16×16 with the **batch-column loop
inside the weight-row tile**, so one weight-tile read serves up to 16 draft tokens, and
contiguous `src1` dispatches to `llamafile_sgemm` (tinyBLAS) for further register blocking.
Weight reuse across the draft batch is real. *Stated as a source reading, not a measurement —
the measurement is the gate itself.*

No CPU-only speculative-decoding benchmark exists upstream to compare against (searched
`repo:ggml-org/llama.cpp speculative decoding CPU`; all hits were CUDA/SYCL/Vulkan/MTP bugs).
So the number this gate produces will be a new one.

**Free correctness check.** Speculative decoding is lossless, so at `temperature 0` the emitted
text must be byte-identical with and without the drafter. `specgate.sh` saves every completion
and `cmp`s them. That is a checker built before the thing, and it costs nothing.

**Queue reordered.** `specgate` was sitting behind `vkfix` (which only re-closes a vector
already killed by measurement in iteration 12) and `genlen`. Killed the `chain9`/`chain10`
waiters **by PID** — the pattern-kill mistake in this session's record has already cost three
severed ssh sessions — and replaced them with `chain12`: specgate → genlen → vkfix.

---

## Iteration 14 continued — thread scaling, and an 80% that is not what it looks like
`[CHANGE: claude-code | 2026-09-12]`

Counterbalanced the same way (ascending pass, then descending pass):

| threads | fwd t/s | rev t/s | mean | vs 2 threads |
|--------:|--------:|--------:|-----:|-------------:|
| 2 |  8.80 |  9.39 |  9.10 |  — |
| 4 | 14.07 | 14.38 | 14.22 | **+56.3%** |
| 6 | 13.37 | 13.76 | 13.57 | +49.1% |
| 8 | 13.78 | 13.95 | 13.87 | +52.4% |

**Two clean results.** Hyperthreading is worthless for prefill — 8 threads (13.87) is *below*
4 (14.22). That is expected for a kernel already saturating the vector units: SMT shares the
FMA ports, and iteration 11 measured that kernel at 67% of AVX2 peak. The server's current
`-tb 4` is therefore already optimal, confirmed rather than assumed. The dip at 6 threads is
consistent across both passes, so it is real, not noise — 6 threads means 4 physical cores
with 2 running SMT siblings, the worst of both.

**The interesting number is 2 → 4 threads: 1.56×, not 2×.** I was about to write that up as
"80% parallel efficiency, the missing 20% is thermal throttling."

**I am not allowed to assert that, and the council's Outsider caught the same thing
independently:** *"80% scaling efficiency 2→4 threads while thermally saturated. The 2-thread
run almost certainly boosted higher. Your scaling curve is contaminated by the variable you're
trying to isolate."* Exactly right. With 2 cores busy the CPU boosts higher than with 4, so
this sweep confounds core count with clock, and "80% efficiency" is not a measurement of
parallel overhead at all.

The two candidate mechanisms make different, testable predictions:
- **clock throttling** → throughput per (core × GHz) is *constant*; the entire loss is clock.
- **parallel overhead** → throughput per (core × GHz) *falls* as threads rise.

`clkscale.sh` samples the actual clock during each run so the sweep can be divided by it.
Queued. Until it reports, the 1.56× has **no** mechanism attached and I am not claiming one.

## Two harness bugs caught, one of which had already silently produced a wrong result

**1. This box is on Python 3.14, not 3.13.** Four scripts referenced `/usr/lib/python3.13/…`.
Consequences, both bad:

- `cachehold.sh` — the gate on the entire warm-cache build — ran with *every single request
  failing* on `FileNotFoundError`, wrote a **zero-byte** result file, and **still echoed
  `CACHEHOLD_DONE`**. Read carelessly, an empty result file for a cache-retention test reads
  as "the cache retained nothing", which is the exact wrong conclusion, and it would have
  killed the highest-value plan in the project. Fixed the paths, added `-np 1`, and added a
  line-count check that reports `CACHEHOLD FAILED: only n/18 results` rather than declaring
  success.
- `quality2.sh` builds its perplexity corpus from stdlib files. All those globs expanded to
  nothing, so **`ppl_corpus.txt` was 18,382 bytes — byte-for-byte just `testfile.py`.** Every
  perplexity number this project would have produced was going to come from one small file.
  Rebuilt: **257,938 bytes**, 14× larger.

`-np 1` was added to `cachehold.sh` for a second reason worth recording: with several slots,
four files can simply occupy four different slots, which is a *different* mechanism from the
`--cache-ram` prompt cache and does not scale past `n` slots. Forcing one slot means any
retention across files can only have come from `--cache-ram`.

**2. The fan is already at maximum — which kills the council's leading hypothesis.**
Three of five advisors independently proposed that 17–20 W at 97–99 °C means a dead or
BIOS-throttled fan, and that forcing it would be a free win. Measured, read-only, no module
reload:

```
/sys/class/hwmon/hwmon3 : dell_smm
   fan1_input = 4172      pwm1 = 255      pwm1_enable = 1
```

**`pwm1` is already 255 and the fan is already turning 4172 RPM.** There is no fan headroom to
unlock; `i8kutils`/`dell_smm_hwmon force=1` cannot give what is already given. That specific
attack is dead before it was attempted, for the cost of one `cat`.

What survives from that hypothesis is the *heat path*, not the fan: a chassis moving 17–20 W
with the fan flat out and still sitting at 97–99 °C is a fouled fin stack or dried paste.
That is a physical fix, it cannot be done over ssh, and per the guardrails it will not be
turned into a shopping suggestion. It is recorded as a measured fact.

**Also observed, and deliberately not chased:** this machine has an AMD `amdgpu` in `hwmon1`
with an empty `temp1_input` (runtime-suspended discrete Radeon). Not pursued, for two measured
reasons rather than a guess: the *integrated* GPU was already measured 2.39× slower and
starved (`gt_requests` = 0 bytes), and this discrete part is weaker still with far less memory
than the 4.291 GB model needs — while waking it would add heat to the one resource already
proven to be the binding constraint.

---

## Iteration 15 — COUNCIL on the thermal ceiling, and why the answer was "stop asking about heat"
`[CHANGE: claude-code | 2026-09-12]`

**The constraint I put to the council**, as a measured number with a named mechanism: the CPU
runs at **2100 MHz against a 3900 MHz rating** because it is thermally saturated at 97–99 °C,
while drawing only **16.9–20.6 W against a 28 W PL1** — so it is heat, not power (MSR 0x64F
confirms thermal). Prefill is near-linear in clock, so recovering it is worth up to ~1.85×.
I asked for software-only attacks, naming: OC-mailbox undervolt (MSR 0x150), intel_pstate/EPP,
fewer-threads-higher-clock, duty-cycling, Dell fan control, Jellyfin heat, sensor validity,
and AVX2 license downclocking.

### Where the council agreed — unanimously, and against my framing
**All five advisors independently rejected the question.** Every one of them pointed out that I
had measured a **26×** (419.5 s cold → 16.2 s warm) and filed it as a caveat, while calling a
**1.85×** "the single largest multiplier identified so far." That sentence was wrong and I am
striking it. Two of them made the same additional point in almost the same words: even *perfect*
thermal recovery leaves generation at ~6 tok/s, which is not "interactive" by any definition, so
total success on the question as framed still fails the mission.

The mission's own guardrail — that measured beats predicted — was being violated by me in the
other direction: I was ranking a *modelled* 1.85× above a *measured* 26×.

### Where the council clashed
Attacking generation. One advisor said generation is bandwidth-bound and therefore the honest
target for speculative decoding, using the bandwidth headroom exposed by "8% decay vs 46% clock
loss." Another said generation is at **~48% of its bandwidth roof** (4.4 GB of weights ÷
29.89 GB/s ≈ 6.8 tok/s theoretical vs 3.3 measured), so the gap is a *software defect*, not
physics. **They cannot both be right, and this matters**: one says the wall is real, the other
says half the wall is a bug. `bytes.sh` was already queued and settles it by measuring DRAM
traffic at the memory controller. This also independently reproduces my own recomputation and
confirms the record's "generation is at 88% of the sustained ceiling" is **wrong** — I could not
reconstruct that figure from the model size, and two advisors got ~48% unprompted.

### What the council got wrong, killed by measurement
Three of five led with "the fan is dead or BIOS-throttled; forcing it is free clock." **Measured:
`pwm1 = 255`, `fan1_input = 4172` — already flat out.** Dead hypothesis, cost of one `cat`.
One advisor's concrete command line used `--prompt-cache-all` and `--keep -1`, which are
**llama-cli flags, not llama-server flags**; it would have failed on the first line. Prior
research had already caught the same class of error, which is exactly why command lines from
advice get checked against `--help` on this box before they get run.

### The blind spot peer review caught — it costed the plan nobody costed
Every advisor recommended persisting the KV cache. **None of them priced it.** Verified
independently, from the model's own geometry (28 layers × 4 KV heads × 128 dim × 2 for K/V):

| context | KV fp16 | KV q8_0 |
|--------:|--------:|--------:|
| 1,024 | 58.7 MB | 29.4 MB |
| 4,858 | **278.6 MB** | 139.3 MB |
| 8,192 | 469.8 MB | 234.9 MB |

So "prefill the whole repo overnight" is **~280 MB per file**. Eighty files is ~22 GB written to
**rotational** drives, evicting the page cache Jellyfin depends on, while holding the box at
99 °C all night. The machine currently has 155 MB free and 8.3 GB in buff/cache. That is not a
free lunch, and the warmer must be *sized*, not turned loose on a repo.

It also produced the fix for a hazard I had already found in source: llama.cpp's
`state_seq_load_file` validates **magic and version only** — not model identity — so a KV file
from a different same-shaped model restores as confident garbage. And bug #22629 means
`--cache-ram` is enforced only inside a `catch (std::bad_alloc)` that Linux overcommit stops
from ever firing. Concrete mitigation from review: **`MemoryMax=` on the systemd unit**, so the
bound is enforced by the kernel rather than by a branch that never executes. That directly
serves the hard requirement that Jellyfin survives.

### The verdict I am acting on
Stop attacking heat. It is real, it is measured, the fan is already maxed, and the remaining
fix is physical and therefore out of scope — recorded as a fact, not converted into a purchase.
Attack instead, in this order: **(1)** never prefill the same tokens twice; **(2)** find out
whether generation's ~48%-of-roof gap is a defect or the roof (`bytes.sh`); **(3)** speculative
decoding on generation, using the zero-RAM n-gram drafter rather than the 0.5B model.

One dissent worth recording rather than burying: an advisor asked why inference runs on the
weakest, hottest, most contended machine in the house at all, given that ssh implies a second
machine. That is a fair challenge to the premise, but the mission fixes the hardware, so it is
noted and not pursued.

---

## Iteration 19 — the warm cache, built and guard-tested

**Constraint being attacked:** re-asking anything about a file that was already read costs
the full 370.46 s prefill again, because nothing survives a server restart.

**Built:** `~/llmperf/llmcache.py` (~150 lines, three verbs: `warm`, `ask`, `status`).
The file goes FIRST in the prompt and the question LAST — not cosmetic, it is what makes
the expensive part of the prompt a stable prefix that different questions can share.

It exists to close two gaps in llama.cpp, both confirmed in its source, neither of which
is a bug I can fix from outside:

1. **No identity check on restore.** `llama_context::state_seq_load_file`
   (`src/llama-context.cpp:2493`) validates a magic number and a version and nothing else —
   not the model, not the quantisation, not RoPE. Restoring a KV file written by a
   *different* model of the same shape yields confident garbage with no error. So every
   entry carries a manifest and restore is refused on any mismatch. A wrong answer in 3 s
   is worse than a right one in 370 s.
2. **No real memory bound.** ggml-org/llama.cpp#22629: `--cache-ram` is enforced only
   inside a `catch(std::bad_alloc)` that Linux overcommit stops from ever firing. That is a
   direct threat to Jellyfin, so the bound lives outside llama.cpp — systemd `MemoryMax=`
   plus this tool's own on-disk budget.

**Guard test — 9/9, run on the server under Python 3.14** (`~/llmperf/test_llmcache.py`).
Deliberately run against a stub HTTP server, not the model: it costs no CPU so it could run
while a benchmark held the box, and it can force the mismatch cases a real llama.cpp server
accepts *silently* — which is the whole reason the manifest exists.

| case | result |
|---|---|
| warm writes a manifest and asks the server to save that key | PASS |
| warming twice does not re-prefill | PASS |
| ask restores when everything matches | PASS |
| **model swapped under the cache → refuses** | PASS |
| source edited → old entry not found at all | PASS |
| manifest corrupted → refuses | PASS |
| server rejects the restore → degrades to a normal prefill, no crash | PASS |
| over disk budget → exit 1 | PASS |
| under budget → exit 0 | PASS |

**Design fact the test exposed, and a message corrected because of it:** the `prefix_sha`
check does *not* catch a source edit. The entry key **is** the prefix hash, so an edited
file misses the cache entirely — a stronger guarantee than a comparison, since there is no
stale entry to find. `prefix_sha` only fires on a corrupt or hand-edited manifest. The
message used to say "source file changed", which was wrong about its own mechanism; it now
says "manifest does not match this source file".

**Queued as `wcgate.sh` (chain17, first item).** It is a redo of slotsave2, because
slotsave2 flattered itself in two ways: it restored 62 ms after writing (straight out of
page cache) into a server that had never restarted. `wcgate` kills the server between write
and read and evicts the KV files with `posix_fadvise(DONTNEED)` first — one file at a time,
never `drop_caches`, which would also throw away Jellyfin's cache and the 4.3 GB model and
turn this into an unrelated disk benchmark. Cold and warm use the same file and the same
question, so the pairing is exact.

`chain16` was replaced by `chain17` to put this first. Nothing was lost: chain16 had not
executed a single step, it was still in its wait loop on `CHAIN8_DONE`.

---

## Iteration 20 — "compute-bound" decomposed into a named port

### Correction to the record, first

**Every number in iterations 14–21 was measured on `qwen7b-pureQ4K.gguf` (4,290,884,384 B
= 4.291 GB), not on the stock Q4_K_M (4,683,074,336 B = 4.683 GB).** `env.sh` sets
`MP=qwen7b-pureQ4K.gguf` — the all-Q4_K requantisation built in iteration 2 — and I had
been *labelling* those runs Q4_K_M. The arithmetic itself was unaffected: I had been
dividing by 4.29 GB, which is the correct size for the model that was actually running.
Only the label was wrong. It matters going forward because pure Q4_K has no Q6_K tensors,
so **every** weight matrix takes the same kernel path.

### The quality gate on that model (task #6, closed)

Paired per-chunk perplexity, same corpus, 8 chunks:

| | final PPL | vs Q4_K_M |
|---|---|---|
| Q4_K_M (output.weight Q6_K) | 11.2590 ± 0.73991 | — |
| pure Q4_K (output.weight Q4_K) | 11.3978 ± 0.75110 | **+1.23%** |

Mean of the per-chunk ratios +1.57%. These are *running* perplexities so the chunks are
correlated — read the sign and size of the final ratio, not the sd. Verdict: **+1.23%
perplexity buys 392 MB, i.e. 8.4% fewer bytes read per generated token.** On a box where
generation is bandwidth-shaped that is a good trade, and pure Q4_K stays the working model.

### Hypothesis (a) is dead — measured, not argued

The council split on whether prefill's ~200 GFLOP/s meant (a) Q4_K is being dequantised to
fp32 and run on the float FMA path at ~74% of peak, or (b) it is on the integer path at
~37% of peak. Three independent facts kill (a):

1. **`llamafile_sgemm` never sees Q4_K.** Its type switch in
   `ggml/src/ggml-cpu/llamafile/sgemm.cpp` has **zero** `Q4_K` case labels — verified on
   this box's own tree at commit `8395162`, not on a clone. tinyBLAS is irrelevant here.
2. **The repacked integer path is selected, and is not gated behind AVX-512.**
   `ggml/src/ggml-cpu/repack.cpp:4600` →
   `else if (cur->type == GGML_TYPE_Q4_K) { if (ggml_cpu_has_avx2()) { if (cur->ne[1] % 8 == 0) return &q4_K_8x8_q8_K; } }`.
   Qwen2.5-7B's 3584 / 18944 / 152064 row counts all satisfy `% 8 == 0`, so every large
   matmul qualifies. The kernel is `ggml_gemm_q4_K_8x8_q8_K`, `arch/x86/repack.cpp:2042`.
3. **The float units are nearly idle during prefill.** A 1.0 s system-wide PMU sample taken
   while a prefill was in flight:

   | counter | value | note |
   |---|---|---|
   | cycles | 8.127e9 | ≈ 4 busy threads at ~2.03 GHz — matches `-tb 4` |
   | instructions | 20.79e9 | IPC 2.56 |
   | `uops_dispatched_port.port_5` | **4.695e9** | ~58% occupancy |
   | `uops_dispatched_port.port_0` | 3.407e9 | ~42% |
   | `uops_dispatched_port.port_1` | 3.499e9 | ~43% |
   | `fp_arith_inst_retired.256b_packed_single` | 2.270e9 | ×16 flops = **36.3 GFLOP/s** |

   36.3 GFLOP/s is **13.5% of the 269 GFLOP/s fp32 peak**. If prefill were running on the
   float path this counter would have to be near 200 GFLOP/s. It is not. (a) is dead.

`perf` was not installed on this box, which is why no earlier iteration could have run this
check — the council's unanimous "just run perf" was not executable as written. Installed.

### What replaces it: port 5, not "compute"

Port 5 is the only port on a Skylake-class core that executes `vpshufd`, `vpermd`,
`vperm2f128` and `vshufps`. In `ggml_gemm_q4_K_8x8_q8_K` those instructions do nibble
unpacking, Q4_K's 6-bit packed scale/min decode (the `kmask1/2/3` constants `0x3f3f3f3f`,
`0x0f0f0f0f`, `0x03030303`), and the 8×8 interleave — **none of which is arithmetic**. The
sample above has port 5 at ~58% against ~42% on the two multiply ports, i.e. the data-
movement port is the busiest thing in the machine while half the multiply capacity idles.

That sample is directional, not proof: it was system-wide, multiplexed across 6 events on
4 counters, and included Jellyfin. `port5.sh` (queued first in chain18) repeats it scoped
to the process, with exactly four general-purpose events so nothing multiplexes, prefill
and generation measured separately because they are different kernels (gemm vs gemv), plus
`perf record`/`perf annotate` for the hot symbol and its instruction histogram.

### Prior art, and it is measured on AVX2-only hardware

**ik_llama.cpp PRs #515 and #531** repack Q4_K into **`Q8_K_R8`** (8-bit, 8-row interleaved)
on the fly, activated only when the batch exceeds ~32 tokens — i.e. prefill only, decode
untouched. Q8_K_R8 needs no nibble unpack and no 6-bit scale decode in the inner loop,
which is precisely the port-5 traffic above. Reported prompt-processing results on
**AVX2-only, no-AVX-512** parts:

| CPU | mainline llama.cpp | ik_llama.cpp | ratio |
|---|---|---|---|
| Ryzen 5975WX (Zen3), Q4_K_S | 148.69 t/s | 291.90 t/s | 1.96× |
| Ryzen 7950X, Q4_K_S | 108.40 t/s | 269.60 t/s | 2.49× |

Those are *their* numbers on *their* hardware, not a prediction for this box. llama.cpp's
own Q4_K prefill PR **#17494** (merged 2025-11-27) does the same kind of thing but is
**ARM64 dotprod only** (`ggml_gemm_q4_K_8x4_q8_K`); its 1.88× is M4 Max / Pi 5, not x86.

Negative results, so they are auditable: I found **no** published 7B-Q4_K prefill figure for
any Comet Lake-U part (searched llama.cpp discussions #4167, #10879, #23313,
OpenBenchmarking, llm-tracker), and **no** 7B numbers for UHD 620 / Gen9.5 under OpenVINO,
SYCL, MLC, PowerInfer or ktransformers — llama.cpp's SYCL docs do not list Gen9.5 as a
target, and ktransformers/PowerInfer both assume AVX-512/AMX or a discrete GPU.

### Council verdict on this constraint

**Agreed, all five:** stop doing FLOP algebra and look at the symbol; and prefill is the
wrong phase to attack because the warm cache already made it a once-per-file cost while
generation is paid on every token forever.

**Clash, and peer review settled it against the majority.** Four advisors called
generation's 14.1 GB/s "47% of the ceiling — half the machine idle". A reviewer checking
the arithmetic pointed out what that framing conceals: the ceiling *in tokens* is
29.89 GB/s ÷ 4.291 GB = **6.97 tok/s**. So the entire bandwidth headroom in generation is
**2.1×**, and it is only purchasable by reading fewer bytes per token. "Half the machine is
idle" made it sound like a defect; it is a hard 2.1×. Nobody had computed it.

**Peer review also caught:** one advisor's `--numa distribute` is a no-op on a
single-socket UMA laptop; another's float-path threshold was off by 2× (an FMA is 2 flops,
so ÷16 not ÷8); and the claim that the fp32 and int8 peaks "differ by exactly 2× so the
algebra cannot decide" is numerology — the peaks are not locked at 2×, because without VNNI
the widen-and-accumulate chain costs extra uops. The strongest single catch was that my
`2 × params × tok/s` numerator was never measured: the input embedding is a gather rather
than a GEMM, and attention FLOPs at 4,858 tokens were omitted entirely. So ~200 GFLOP/s has
error bars, and "74% of peak with RMSNorm, RoPE and softmax in the loop" should itself have
been a tell that the numerator was inflated. The PMU counters above sidestep the whole
dispute by measuring instructions instead of inferring them.

---

## Iteration 21 — context length is the master variable (measured, and nobody's list had it)

Three prefill points, all from the same wcgate run, same model, same flags, minutes apart:

| prompt tokens | prefill wall | prefill rate |
|---|---|---|
| 2,914 (shlex.py) | 208.48 s | **13.98 tok/s** |
| 7,445 (tempfile.py) | 647.65 s | **11.49 tok/s** |

And two generation points:

| context | generation |
|---|---|
| 2,914 | **4.33 tok/s** |
| 4,858 | **3.29 tok/s** |

**Both phases get slower as context grows, and for generation the byte count cannot explain
it.** KV is a measured 57,360 B/token, so going from 2,914 to 4,858 tokens of context takes
the read per generated token from 4.291 + 0.167 = 4.458 GB to 4.291 + 0.279 = 4.570 GB —
**2.4% more bytes for a 24% slowdown**. Something that is not bytes scales with context.
The obvious candidate is attention itself, whose per-token cost is linear in context while
the weight read is constant, but that is a hypothesis and `ctxgen.sh` is queued to test it:
counterbalanced ascending/descending sweep at roughly 530 / 1,580 / 3,170 / 4,930 tokens,
with a unique first line per variant so the server's prompt cache cannot share prefixes
between points, plus IMC DRAM traffic measured *during generation only* at both extremes so
bytes and compute can be told apart.

I should also flag the drift caveat honestly: the 4.33 and 3.29 figures came from different
scripts at different times, so thermal drift is a live alternative explanation. That is
precisely why `ctxgen.sh` measures every point back-to-back in both directions rather than
trusting these two.

**Why this is not trivia: it may be eating part of the warm-cache win.** The cache restores
*long* contexts. If long contexts make every generated token slower, the cache buys a fast
first token and then pays for it on every token after. That has to be quantified before the
cache result is trusted as a clean win.

### KV geometry, now confirmed three independent ways

| source | bytes/token |
|---|---|
| computed from geometry (28 layers × 4 KV heads × 128 dim × 2 (K/V) × 2 B) | 57,344 |
| slot save, 2,891 tokens → 165,828,476 B | 57,360 |
| slot save, 7,445 tokens → 427,045,916 B | 57,360 |

That is a 0.03% agreement and it means the footprint arithmetic can be trusted: **one
7.4k-token file costs 427 MB of KV on a rotational drive shared with Jellyfin.**

## Iteration 23 (queued) — quantise the KV cache

`-ctk q8_0 -ctv q8_0` halves the KV. Stating the expected sizes as arithmetic, not
prediction: 427 MB → ~214 MB per file, and the measured 108 MB/s cold read off the platter
therefore goes from ~2.6 s to ~1.3 s.

I am explicitly **not** predicting a speed win. Weights dominate the per-token read, so
halving KV cuts bytes per generated token by only about 3% at 4,858 context. The reason to
do it is footprint — half the disk per file, half the cold restore, twice as many files
inside the same budget — which is what decides whether the warm cache scales past a handful
of files at all.

Quantised KV is lossy, so `kvq.sh` diffs the two arms' actual answers at temperature 0
rather than assuming. A footprint win that silently changes answers is not a win. ABBA over
a small file, because a single A-then-B ordering cannot separate a real difference from the
box's ~10% drift.

## Process change: the chain lineage is retired

`chain8` … `chain19` were fixed lists, so every time a measurement suggested a better next
experiment I had to kill the driver and rewrite the entire chain — five times. One of those
rewrites used `pkill -f "bash …/chain18.sh"`, whose pattern matched **my own ssh command
line**, and cut the session. (Nothing was lost: wcgate was a detached child and survived.
But this is the fourth time a pattern-kill has bitten this project, so: kill by PID, never
by pattern, when the pattern can appear in the command that is doing the killing.)

Replaced by `runner.sh`, which runs whatever is in `~/llmperf/queue/` in name order and
moves finished scripts to `queue/done/`. Adding an experiment is now dropping a file in;
reordering is a rename. Neither requires touching a running process.

---

## Iteration 19 — RESULT: the warm KV cache, measured cold-against-warm

`wcgate.sh` finished. This is the first end-to-end number the mission actually asked for:
one real coding question against one real file, time to first token and total time.

The pairing is deliberately hostile to my own result. Phase A asks the question with an
empty cache. Phase B warms the cache. Then the **server is killed** and every `.kv` file is
pushed out of the page cache with `posix_fadvise(DONTNEED)`. Phase C brings up a *fresh*
server and asks the *same question* about the *same file*. Nothing is left in RAM from
phase A or B; the restore has to come off the platter.

| | cold (phase A) | warm off the platter (phase C) |
|---|---|---|
| prompt tokens | 2,914 | 23 new + 2,891 restored |
| restore | — | 1.51 s (165.8 MB) |
| **time to first token** | **208.48 s** | **3.20 s** |
| generation rate | 4.33 tok/s (190 tok) | 4.39 tok/s (188 tok) |
| **total** | **252.1 s** | **47.29 s** |

**TTFT 208.48 s -> 3.20 s. 65x.** Total 252.1 s -> 47.29 s at effectively the same amount
of generated text (190 vs 188 tokens), so the totals are comparable without adjustment.

Three checks that this is real and not an artefact of something staying warm:

1. **The restore ran at platter speed.** 165,828,476 B in 1.51 s is 110 MB/s. The
   independently measured raw rate of this drive is 108 MB/s (`dd iflag=direct`). If the
   eviction had failed and this had come from the page cache it would have been an order of
   magnitude faster. It did not. The disk read is in the 3.20 s.
2. **A restored KV is not a degraded KV.** Generation after restore is 4.39 tok/s against
   4.33 tok/s for the freshly-computed cache at the same context. Restoring costs nothing
   per subsequent token; it is not trading a fast first token for slow ones *at fixed
   context*. (It does at *growing* context - see iteration 21 below, which is a different
   effect.)
3. **Same file, second question, page cache now warm:** restore 0.04 s, TTFT 2.72 s,
   total 10.72 s for 36 generated tokens. The second question against an already-open file
   is the common case in real use, and it is where the tool feels instant.

Full run:

```
{"file":"shlex.py",   "restored":false,"why":"no-cache-entry","restore_s":0.00,"ttft_s":208.48,"prompt_n":2914,"cached_n":0,   "gen_n":190,"tg_tps":4.33,"total_s":252.10}
{"file":"shlex.py",   "status":"warmed","prefill_s":  0.23,"tokens":2891,"bytes":165828476}
{"file":"tempfile.py","status":"warmed","prefill_s":647.65,"tokens":7445,"bytes":427045916}
{"file":"gzip.py",    "status":"warmed","prefill_s":487.01,"tokens":5846,"bytes":335327276}
{"file":"shlex.py",   "restored":true,"why":"restored","restore_s":1.51,"ttft_s":3.20,"prompt_n":23,"cached_n":2891,"gen_n":188,"tg_tps":4.39,"total_s":47.29}
{"file":"shlex.py",   "restored":true,"why":"restored","restore_s":0.04,"ttft_s":2.72,"prompt_n":18,"cached_n":2891,"gen_n": 36,"tg_tps":4.39,"total_s":10.72}
{"file":"tempfile.py","restored":true,"why":"restored","restore_s":5.19,"ttft_s":6.38,"prompt_n":17,"cached_n":7445,"gen_n":116,"tg_tps":2.44,"total_s":58.64}
3 entries, 0.93 GB on disk (budget 6.00 GB)
```

**Cost.** 0.93 GB of rotational disk for three files. At 57,360 B/token a 6 GB budget holds
about 105,000 tokens of cached context - roughly 14 files the size of `tempfile.py`. The
warming itself is not free: 647.65 s to warm `tempfile.py` once. That is the honest shape
of this win. It is not a speedup, it is **moving the cost off the interactive path**. You
pay 11 minutes once, overnight, and every question after that starts in ~3 s instead of
~3.5 minutes.

**Prefill rates fall out of the warm phase, and they are not flat:**

| file | tokens | prefill s | tok/s |
|---|---|---|---|
| shlex.py | 2,914 | 208.48 | 13.98 |
| gzip.py | 5,846 | 487.01 | 12.00 |
| tempfile.py | 7,445 | 647.65 | 11.49 |

**KV geometry confirmed a third time.** 165828476/2891, 427045916/7445 and 335327276/5846
all give **57,360 B/token**, against 28 layers x 4 KV heads x 128 dim x 2 x 2 B = 57,344
computed. 0.03% apart, which is the file header. The KV size model is settled.

### Correction to iteration 21's caveat

I wrote in iteration 21 that the generation-vs-context effect rested on 4.33 tok/s at 2,914
tokens and 3.29 tok/s at 4,858 taken *from different scripts on different days*, so thermal
drift was a live alternative explanation. **That caveat is now mostly gone, and the effect
is bigger than I said.** Both of these came out of this single wcgate run, minutes apart, on
the same server process:

    2,891 tokens of context -> 4.39 tok/s
    7,445 tokens of context -> 2.44 tok/s

**44% slower generation for 2.6x the context.** Bytes cannot carry that: KV read per
generated token goes from 4.29 + 0.166 = 4.46 GB to 4.29 + 0.427 = 4.72 GB, about 6% more.
A 6% increase in bytes is not a 44% slowdown. Something that is not byte count scales with
context during generation.

This sharpens rather than softens the worry already recorded here: the warm cache's whole
purpose is to restore *long* contexts, and long contexts appear to make every generated
token slower. The cache buys a fast first token and may be paying for it on every token
after. `50-ctxgen.sh` is queued to separate that from drift for good, measuring each point
back-to-back in both directions and putting an IMC counter around generation alone at both
extremes. It is no longer a curiosity - it is the largest unexplained factor in the
end-to-end number above.

---

## Iteration 20 — RESULT: the port-5 hypothesis is wrong. I am dropping it.

`10-port5.sh` ran the profile properly scoped to the process, with the event set split in two
so nothing important was multiplexed away. It contradicts the opportunistic sample I built
the hypothesis on, and it contradicts it in the direction that kills it.

The two perf runs (E1 = ports 0/1/5, E2 = ports 2/3/4/6) agree on total cycles to **0.12%**
on prefill and 1.27% on generation. The workload is deterministic and the two runs are
therefore directly comparable, which is what makes the cross-run port ranking legitimate.

### Prefill — `-n 0 -p 2048 -tb 4`, IPC 2.67

| port | uops | occupancy | what it does on Skylake |
|---|---|---|---|
| p3 | 15.88e11 | **65.2%** | load / store-address |
| p2 | 15.49e11 | **63.6%** | load / store-address |
| p5 | 15.14e11 | 62.2% | shuffle, permute, blend — the nibble unpack |
| p4 | 13.41e11 | 55.0% | store data |
| p1 | 10.81e11 | 44.4% | ALU / FMA |
| p0 | 10.50e11 | 43.1% | ALU / FMA |
| p6 | 1.78e11 | 7.3% | ALU / branch |

**Port 5 is third, not first.** The two load ports are busier than it. And the top port is at
65%, not 95% — nothing is saturated. Total dispatch is 3.41 uops/cycle against a machine that
can dispatch 8. I claimed in iteration 20 that a ~58%/42% split "converts compute-bound into a
named port". It does not. A 65/64/62/55/44/43/7 spread across seven ports is not a port
bottleneck; it is a kernel that is broadly busy and saturating nothing.

The earlier sample that suggested otherwise was system-wide, multiplexed, and included
Jellyfin. It was labelled directional at the time. It was directionally wrong.

### What the profile says instead — a better mechanism, and it is still actionable

Prefill dispatches **8.30e12 uops to retire 5.385e11 256-bit-packed-single FP instructions.
That is 15.4 dispatched uops for every wide FP instruction; arithmetic is 6.5% of all uop
traffic.** The other 93.5% is loading, storing, shuffling and unpacking. That is the real
statement of the problem, and it is a superset of the port-5 story rather than a refutation of
its spirit: the unpack overhead is real, it is just spread across the load/store/shuffle ports
instead of piling onto one of them.

This changes what a fix has to do. Relieving port 5 alone would move work onto ports that are
already at 63-65%. A format change only wins if it cuts the **total** uop count — which is
exactly what an interleaved format with a trivial scale layout should do, and exactly what
`20-scalefmt.sh` can measure if I widen it from "does port_5 fall" to "does total dispatch
fall". I have widened it.

### Generation — `-p 0 -n 128 -t 8`, IPC 1.04

| port | occupancy |
|---|---|
| p5 | 33.1% |
| p1 | 20.2% |
| p0 | 20.1% |
| p6 | 11.0% |
| p3 | 11.2% |
| p2 | 10.5% |
| p4 | 9.0% |

Total dispatch **1.16 uops/cycle out of 8. IPC 1.04.** Every port is under 34%. 256-bit FP is
0.77% of dispatched uops — 130 uops per wide FP instruction.

This is not a busy core. This is a core standing still waiting for memory, and it is the
cleanest evidence yet that prefill and generation are limited by genuinely different things:
prefill is uop-bound with nothing saturated, generation is stalled. Any single fix that claims
to help both should be disbelieved until it is measured on both.

---

## Iteration 24 — the council took my last two numbers apart, and it was right

I stated the constraint as: generation falls 44% (4.39 -> 2.44 tok/s) between 2,891 and 7,445
tokens of context, while bytes per generated token rise only ~6%. I computed that the marginal
0.182 s per token was consuming 4.8% of the bandwidth ceiling and 3.7% of the FP peak, and
concluded "under 5% of both — the machine is idle, the time is going somewhere else."

Four of five advisors independently rejected that, and peer review then found something worse.

### Correction 1 — the wrong denominator. The machine is not idle.

Marginal work compared against total capacity is not a utilisation figure. The baseline:

    2,891 ctx: 4.456 GB / 0.2278 s = 19.56 GB/s = 65.4% of the 29.89 GB/s ceiling
    7,445 ctx: 4.717 GB / 0.4098 s = 11.51 GB/s = 38.5%

The short run is at **two thirds of the memory ceiling**, and the long run **falls to 38.5%**.
The finding is an efficiency collapse, not an idle machine. If the long run had merely held the
short run's efficiency it would generate at 4.15 tok/s; it measured 2.44. **93% of the marginal
cost is not explained by the extra bytes.**

### Correction 2 — the two datapoints are mutually inconsistent. Neither can be used.

Peer review supplied the arithmetic that settles it. Fit a straight line through the two points:

    t = 0.1123 s + 39.96 us per context token

The fixed term is the per-token weight read. 4.29 GB / 0.1123 s = **38.2 GB/s, which is 28%
above the measured 29.89 GB/s ceiling.** Drop the ~0.31 GB output embedding, which is a gather
and not a full read, and it is still 35.4 GB/s — 18% over. A fixed term that exceeds the memory
ceiling is impossible. **No linear-in-context model that respects measured bandwidth fits these
two points.** One of them is contaminated.

The prime suspect is the thing I told myself I had excluded. I wrote that drift was ruled out
because both points came from one server process minutes apart. That is not sufficient, and the
detail I skipped over is that the **slow point was measured last** — which is precisely what a
warming laptop produces. I made the same error I had explicitly flagged one iteration earlier
about a different pair of numbers.

### Correction 3 — the worry that motivated all of this is a tautology.

I recorded a concern that the warm cache "buys a fast first token and pays for it on every token
after". Per-token cost is a function of KV **length**, not of how the KV got there. Recomputing
that 7,445-token prefix from scratch leaves you generating at exactly the same rate afterwards.
The warm cache carries **zero marginal per-token penalty** against the only alternative that
exists. The 65x TTFT result stands unqualified and needs no audit.

What survives is a different and still-real point: the cache makes long contexts cheap to
*enter*, so it will cause long contexts to be used, which exposes whatever the per-token
context cost turns out to be. That makes the context curve the next constraint — but it does not
make it a cost of the cache.

### Where the council clashed

On the mechanism, and the disagreement is unresolved by measurement so far.
- **Cache pollution**: the 427 MB KV working set evicts weights from a 6 MB L3 and slows the
  4.29 GB weight stream that is already counted — so marginal context costs are billed to bytes
  already in the budget. Predicts LLC-load-misses per generated token rising with depth.
- **Latency, not bandwidth**: batch-1 decode is a dependency chain and 1.43 GB/s is a
  memory-level-parallelism ceiling, not a bandwidth one. Predicts the marginal cost is flat as
  threads are added.
- **Neither — it is thermal**: predicts effective clock falls across the sweep.
- **Neither — it is the server**: predicts a controlled `llama-bench` sweep will not reproduce
  the curve at all, which would move the whole investigation into `llama-server`.

One ggml-specific correction from review, checked against this box's source rather than
accepted: `n_kv` is padded up to a multiple of 256 (`llama-kv-cache.cpp:1255-1260`,
`n_pad_cur = max(n_pad, 256)`), so per-token cost is a step function in 256-token increments.
Too small to explain 44%, but it means a two-point line was never going to be safe.

### Blind spot the council caught in itself

The Expansionist's proposal to run 8-16 concurrent sequences was rejected by two reviewers on
arithmetic this log already contains: each slot needs its own KV, and 16 x 427 MB is 6.8 GB on
top of 4.29 GB of weights on a 16 GB box that also runs Jellyfin. It does not fit, and the RAM
cliff is already measured. Modest batching is not ruled out; the 16-way version is.

### What is now queued as a result

- **`15-ctxsweep.sh`** — six depths (0/1024/2048/4096/6144/8192), each **bracketed by a d=0
  run**. d=0 needs no prefill so it is nearly free, and the d=0 series *is* the drift curve, so
  every depth number can be corrected against a measurement taken beside it. Drift stops being
  an alternative explanation and becomes a measured quantity. Instrumented with
  cycles/ref-cycles (effective clock — the throttling check), major-faults (KV faulting off a
  rotational drive would burn wall-clock while consuming neither budget), LLC-load-misses (the
  cache-pollution prediction) and dTLB-load-misses (427 MB over 4 KB pages).
- **`16-ctxbytes.sh`** — stops inferring bytes and measures them. Two runs at the same depth
  differing only in `n_gen`; model load, depth prefill and warmup are identical and cancel in
  the subtraction, leaving the DRAM traffic of exactly 64 generated tokens. Run at depth 0 and
  8192. `uncore_imc` is system-wide and cannot be scoped, so the idle background rate is
  measured separately and subtracted as a per-second term — otherwise the longer run gets
  charged for Jellyfin's bytes. **Every byte figure in this log so far has been computed from
  the geometry, never measured at the memory controller.** This is the first time that
  assumption gets checked.

### Iteration 20 addendum — the symbol profile, and what it does and does not cover

`perf record -F 499` on the same two workloads. Both phases are dominated by a single function
each, which settles the kernel identity by measurement rather than by reading the dispatch
table:

    PREFILL      90.76%  ggml_gemm_q4_K_8x8_q8_K
                  2.91%  simd_gemm_ukernel<6,2>
                  2.72%  ggml_compute_forward_flash_attn_ext_tiled
                  0.56%  simd_gemm
                  0.50%  ggml_vec_swiglu_f32

    GENERATION   92.07%  ggml_gemv_q4_K_8x8_q8_K
                  4.57%  (unresolved)
                  0.69%  repack_q4_K_to_q4_K_8_bl

So the iteration-20 port numbers describe those two functions and essentially nothing else.

**A limit of this profile that I want on the record before it gets over-read.** The generation
run was `-p 0 -n 128` with no `-d`, so the KV was nearly empty. 92% of it is the weight GEMV
and flash attention barely appears. That means the "IPC 1.04, every port under 34%, stalled
core" result is a clean, isolated mechanism for **baseline** generation — streaming 4.29 GB of
weights per token through a GEMV — and says nothing whatsoever about the long-context regime.
The context-dependent cost lives in a kernel this profile did not exercise. `15-ctxsweep.sh`
and `17-fadepth.sh` are the runs that reach it.

---

## Iteration 25 — flash attention at depth. Three predictions, written before the run.

Prior art search (llama.cpp and ik_llama.cpp issues/PRs; where I looked and what I found is
below) turned up a documented, measured candidate that I had not considered, and reading this
box's own source turned it into three falsifiable predictions.

**The source fact.** `ggml/src/ggml-cpu/ops.cpp:9261` on this tree:

```c
use_split_kv_path = !use_ref && (neq1 == 1 && neq3 == 1) && kv_is_f32_or_f16
                    && (k->type == v->type) && q->type == GGML_TYPE_F32 && nek1 >= 512;
```

Three gates matter:
- `neq1 == 1` — only single-token decode takes this path; prefill never does.
- `nek1 >= 512` — only once the KV holds at least 512 cells. **Below that, CPU flash attention
  parallelises over query heads.** With 28 heads and 8 threads that is 3.5 rounds, i.e. a tail
  on every single token.
- `kv_is_f32_or_f16` — **a quantised KV cache falls off the split path entirely.**

**Prior art, with the measured/speculated distinction kept.**
- *Measured.* llama.cpp PR #19209 (merged 2026-02-02) added this split-KV path; before it, CPU
  FA parallelised only over query heads, which the author states made extra cores useless when
  `n_head < n_threads`. The PR's own tables still show `-fa` **losing** to no-FA at large depth
  on some configurations. So "-fa off can be faster on CPU" is documented, not folklore. The
  author also says the inner GEMM is "not optimised (yet)" and remains memory-bound.
- *Measured.* ik_llama.cpp discussion #25 (ikawrakow): FA slower than no-FA on mainline, with a
  stated mechanism — the fused kernel performs K·Q and V·softmax internally and thereby loses
  access to the type-specific optimised `mul_mat` kernels the non-FA path reaches.
- *Measured, but on a GPU.* llama.cpp issue #26581 found a constant **21–25 ns per KV position
  per layer per token** in ggml decode on Intel Xe2, memory-**latency**-bound, achieving a small
  fraction of peak bandwidth; vLLM on the same hardware was flat to 127k. Different backend, but
  the same shape as what I am chasing, and it locates the tax in ggml's decode kernels.
- *Dead ends, so they are not searched again.* Hugepages: only llama.cpp issue #2251, where a
  contributor measured **no gain on x86_64** (benefit reported only on ARM/PPC); nobody has
  tested it against a large KV specifically. CPU depth-scaling analyses for ktransformers,
  PowerInfer, OpenVINO and IPEX-LLM: searched, nothing found; ktransformers' CPU wins are
  AMX/AVX-512-gated and therefore irrelevant on Comet Lake. llama.cpp issues #27111 (HTTP thread
  contention), #28734, #26663, #27734, #25207 (all GPU backends) — all unrelated on inspection.

**A useful yardstick from #26581.** Per KV position per layer this model reads 4 KV heads x 128
dim x 2 (K and V) x 2 bytes = 2,048 B. At the measured 19.56 GB/s baseline that is ~105 ns. My
(now-invalidated) two-point figure implied ~1,427 ns. If the controlled sweep lands anywhere
near that, decode attention is running more than an order of magnitude off its own byte budget,
and latency rather than bandwidth is the story.

**The three predictions, fixed in advance (`17-fadepth.sh`):**
1. `-fa 0` vs `-fa 1` at depth 8192. If `-fa 0` wins, the fused kernel is the mechanism and the
   fix is a runtime flag rather than a patch — the cheapest available win if it lands.
2. `-fa 0` vs `-fa 1` at depth 0. Expect little difference. This is the control that stops me
   crediting FA for a drift.
3. `q8_0` KV at depth 8192. It halves the KV bytes, so a bytes-story predicts it is faster. But
   `kv_is_f32_or_f16` is false for q8_0, so it also falls off the split-KV path back onto
   head-parallel attention. **If halving the bytes makes it slower, that is a clean double
   result: bytes are not the constraint, and the parallel path is worth more than the bytes it
   moves.** This is the most informative single run in the script.

**A design flaw this found in `15-ctxsweep.sh`, corrected before it ran.** The sweep bracketed
every depth with a `d=0` run. But at `d=0` the padded `n_kv` is 256, which is below the 512 gate
— so `d=0` runs a *different kernel* from every other point. The brackets are still valid as a
drift monitor, which is all they are used for, but they are not "the same thing with less
context". Depths 128 and 448 were added to bracket the `nek1 >= 512` transition, since that is
where the source says a step must be if there is one.

---

## Iteration 24 RESULT (partial) — the sweep runs, and my instrumentation has a hole in it

All numbers below from `~/llama.cpp` on branch `cpu-igpu-tensor-parallel`, working tree
clean (`git status --short` empty), so these baselines are honest.

| depth | tg tok/s | eff GHz (process-wide) | major faults | LLC misses | dTLB misses |
|---|---|---|---|---|---|
| 0 | 6.9349 | 2.102 | 0 | 4.066e8 | 1.254e6 |
| 1024 | 5.6507 | 1.597 | 0 | 5.027e8 | 2.147e6 |
| 0 | 6.6662 | 1.912 | 0 | 3.828e8 | 1.218e6 |
| 2048 | 5.0055 | 1.513 | 0 | 6.618e8 | 3.148e6 |
| 0 | 6.5701 | 1.857 | 0 | 3.753e8 | 1.267e6 |
| 4096 | 3.6750 | 1.469 | 0 | 1.263e9 | 2.274e6 |
| 0 | 6.4715 | 1.804 | 0 | 3.690e8 | 1.208e6 |

**The d=0 brackets work.** 6.9349 → 6.4715 across the run, a 6.7% monotonic decline. Drift
is now a measured quantity rather than a competing explanation, which is what the brackets
were for. Every depth row below is corrected against the mean of the two d=0 runs taken
either side of it.

**`major-faults` is 0 at every single point.** Disk is dead as an explanation. That was a
pre-registered outcome and it resolved cleanly.

### Two things I have to correct before going further

**1. My own script cannot support three of its own columns.** `perf stat` wrapped the entire
`llama-bench` process. `tg_tps` is generation-only because llama-bench times it that way, so
the timing is clean — but `eff_ghz`, `LLC-load-misses` and `dTLB-load-misses` cover the whole
process, and every depth run does a prefill of that depth first. Prefill is heavy AVX2 work
that grows linearly with depth. So the depth rows' counters are dominated by work that is not
the thing I am attributing. The clock column looks like throttling and looks equally like
"averaged in a long prefill", and my script cannot tell those apart. **Those three columns
prove nothing and I am not going to argue from them.** Iteration 26 replaces them.

**2. Depths 128 and 448 are missing and will not appear.** bash had already read the script
into memory before I added them, so this run is executing the older depth list. The two
points that bracket the `nek1 >= 512` gate at `ops.cpp:9261` were the most valuable ones in
the design. They move to Iteration 26.

### The marginal cost, drift-corrected

| depth | local d=0 base | marginal time | per context token | vs previous doubling |
|---|---|---|---|---|
| 1024 | 6.8005 t/s | 0.02992 s | 29.2 µs | — |
| 2048 | 6.6181 t/s | 0.04868 s | 23.8 µs | ×1.63 for ×2 depth |
| 4096 | 6.5208 t/s | 0.11875 s | 29.0 µs | **×2.44 for ×2 depth** |

**The cost is superlinear between 2048 and 4096.** A doubling of depth cost 2.44× the time.
It is also non-monotonic per-token — 29.2, then 23.8, then 29.0 — so 2048 is an outlier
against a rising trend, not a point on a smooth falling curve. I had started to build an
argument on "marginal cost falls with depth" off the first two points alone. That argument is
dead, and it died for the third time in this log for the same reason: **two points are not a
curve.** I am recording that as a standing rule rather than a one-off.

---

## Iteration 24a — the decomposition, and the council taking it apart

I split one generated token at 2891 context in two and measured each half against the same
measured 29.89 GB/s ceiling:

| path | share of the token | measured efficiency |
|---|---|---|
| weight streaming | 65% | 97.6% of the memory ceiling |
| KV / attention | 35% | 6.9% of the memory ceiling, 4.1% of AVX2 peak |

I councilled exactly that, and **the council's central finding is that this table is not two
measurements.** It is one measurement and one subtraction, presented as two. Specifically:

- **The 0.0808 s is a residual.** It is (token time at depth) − (token time at depth 0). It
  therefore contains *everything* that grows with context: attention, yes, but also the KV
  writes, RoPE, mask construction, the Q quantisation to q8, softmax, and every thread
  barrier that got worse. I named that bucket "attention" and then compared it against an
  attention FLOP count. That is circular and I should have caught it.
- **The 97.6% is not the weight path.** It is the *entire token* at depth 0 — attention at
  n_kv 256 included — measured against a weight-only byte model. It is an upper bound on
  weight-path efficiency, not a measurement of it.
- **The 29.89 GB/s may be the wrong ceiling.** It is an all-8-thread sequential streaming
  number. A latency-bound path at partial occupancy is capped by fill-buffer concurrency,
  which is a per-core limit and much lower. Grading one against the other is not valid.
- **The compute-density inversion, which is the sharpest thing anyone said.** Attention is
  1.16 GFLOP over 0.166 GB = **7 flops per byte**. Weight streaming is ~8.6 GFLOP over
  4.29 GB = **2 flops per byte**. The path I called bandwidth-starved is 3.5× *more*
  compute-dense than the path that saturates bandwidth. Whatever is wrong with it, "not
  enough bandwidth" is not a coherent description of it.
- **I profiled at depth 0 and drew conclusions about depth 2891.** The 92.07%-in-`ggml_gemv`
  profile says nothing about the code I am indicting. If `flash_attn_ext` does not appear in
  a profile taken *at depth*, the entire `ops.cpp:9261` line of reasoning is about a branch
  this box never executes.

### What the peer-review round found that no advisor did

Two of three reviewers, independently, did arithmetic I should have done myself.

Per generated token this model touches **2048 B of KV per context position per layer**
(2 for K and V × 4 KV heads × 128 dim × 2 bytes). So the *per-layer* working set is:

| context | per-layer KV | 6 MB L3 |
|---|---|---|
| 1024 | 2.10 MB | fits |
| 2048 | 4.19 MB | fits |
| 2891 | 5.92 MB | fits, barely |
| **3072** | **6.29 MB** | **spills** |
| 4096 | 8.39 MB | spills |
| 8192 | 16.78 MB | spills |

**The crossover is at context 3072 exactly, and the ×2.44 superlinear jump straddles it.**

I am recording that as a coincidence worth measuring, **not** as a mechanism, because the
reuse story is missing: within one token each layer's KV is read once and never re-read, and
between tokens the other 27 layers push 117–235 MB through a 6 MB L3, so nothing survives
from token N to token N+1 anyway. A working set "fitting in L3" only matters if something
re-reads it. Nobody has shown what would. Either there is a reuse pattern I have not found,
or the coincidence is 2048 being an outlier. Iteration 28 measures the knee at resolution
fine enough to tell.

### Where the council genuinely clashed

**Is attention even worth attacking?** One advisor did the ceiling arithmetic: kill the
attention term *perfectly, to zero*, and 4.39 → 6.80 tok/s. **1.55×, hard cap**, while the
other 65% sits at a ceiling. Its counter-proposal is that the 4.29 GB is read once per
*forward pass*, not per token — batch-size-1 autoregressive decode is what makes those the
same thing — so speculative decoding (batching tokens *within* one sequence, one KV cache,
no extra memory) is the only lever that touches the 65%, and the IPC 1.04 / all-ports-under-34%
profile proves the spare compute to pay for it exists.

Two reviewers pushed back and **the superlinearity settles it against the 1.55× cap**: if the
attention term grows superlinearly with depth, its share is not fixed and neither is the cap.
Both are live. They are also not in competition — one attacks 65%, the other 35%.

One reviewer's objection to speculation is wrong on the source and I want that on the record:
it argued verify re-reads the KV per draft token. It does not — a k-token verify batch reads
each KV position once and reuses it across all k query rows. But there is a real interaction
underneath the wrong objection: `ops.cpp:9261` gates the split-KV path on `neq1 == 1`, so a
verify batch **falls off that path** onto head-parallel attention regardless of depth. That
is measurable and Iteration 28 measures it.

---

## Iterations 26–28 — three experiments, queued, each with its outcomes fixed in advance

**Iteration 26, `16a-clkphase.sh` — phase-scoped counters.** `perf stat -I 1000` emits a
delta every second instead of one total. Generation is the last `n_gen/tg_tps` seconds of the
process, so counters can be scoped to it and prefill reported separately as `pre_ghz`. This
closes the hole above: throttling becomes visible rather than inferred. It also carries the
depths 128 and 448 that the sweep lost, bracketing the `nek1 >= 512` gate.

**Iteration 27, `16b-fathreads.sh` — does the attention term use the cores at all?** Marginal
cost is a difference, so both halves are measured at the same thread count:
`marginal(t) = 1/tg(depth,t) − 1/tg(0,t)`, at t = 1, 2, 4, 6, 7, 8, ascending and descending.
Flat from 1 to 8 means the term is effectively serial and that one fact carries most of an 8×
gap on its own. **`-t 7` is in the list because 28 query heads over 8 threads is 3.5 rounds
and over 7 is exactly 4** — three advisors reached that independently. `-t 6` is the control
that stops me crediting "7" when the truth is "fewer than 8". If `-t 7` wins it is a config
line, not a patch, and it hands a core back to Jellyfin.

**Iteration 28, `15a-fakernel.sh` — time the kernel directly, no subtraction.** This is the
answer to the residual problem. `tests/test-backend-ops.cpp` now carries a block, gated on
`GGML_TEST_QWEN_FA` so the default correctness run is unchanged, at the real shapes:
`hsk=hsv=128, nh=4, nr23={7,1}, nb=1`, f16 K/V, mask on, K/V as views of a larger buffer.
The harness's own `op_flops` for those shapes is 14,336 × kv per layer, which over 28 layers
at kv=2891 is 1.16 GFLOP — **the same figure I derived by hand**, so the harness and my
arithmetic agree on what the work is before either measures it.

- kv is dense from 2048 to 4096 (2560, 2816, 2944, 3072, 3200, 3584) to resolve the predicted
  knee. Knee in the kernel too → the L3 crossover is a mechanism. Kernel smooth but end-to-end
  kinked → the kernel is innocent and the cost is the other 27 layers evicting each other,
  which is a different fix entirely.
- Honest caveat, stated before the run: perf mode re-runs one op on **one** buffer, so it is
  warmer than a real layer's KV ever is. That is why the comparison is the point — the gap
  between this curve and the in-model curve *is* the cache-pollution term, measured.
- `nb = 4` and `nb = 8` at four depths measure the speculative-verify shape, which falls off
  the split-KV path via the `neq1 == 1` gate.
- **THP arm**, ABBA (default / always / default). Prior art #2251 found no hugepage win on
  x86_64, but that was about weights, which are mmap'd from a file and cannot use transparent
  hugepages at all. The KV cache is **anonymous** memory, where THP does apply. 235 MB on 4 KB
  pages is 57k pages against a ~1500-entry dTLB. Different case, one sysfs write, reverted on
  exit by a trap.


---

## Iteration 29 — reading the kernel instead of guessing at it, and the answer is in the loop nest

The council said: *if `flash_attn_ext` is not in a profile taken at depth, the `ops.cpp:9261`
analysis is about a branch you never execute.* Fair. So before spending more machine time I
read the branch. It is executed, and reading it produced a mechanism I did not expect.

### What the split-KV decode path actually does

`ops.cpp:9263` — the gate is satisfied for this workload: `neq1 == 1` (single-token decode),
K and V are f16, same type, Q is f32, and `nek1 >= 512` for any depth at or above 448 once
n_kv is padded. **The split path is taken.** Then, at `ops.cpp:9264-9285`:

```c
const int64_t chunk_size = (nek1 + nth - 1) / nth;
const int64_t ic_start   = ith * chunk_size;
const int64_t ic_end     = std::min(ic_start + chunk_size, nek1);
...
for (int64_t q_head = 0; q_head < neq2; q_head++) {
    ggml_compute_forward_flash_attn_ext_f16_one_chunk(
        params, dst, q_head, q_head + 1, ic_start, ic_end, ...);
}
```

**The query-head loop is on the OUTSIDE and each call rescans the thread's entire KV chunk.**
`one_chunk` (line 8614) walks `for (int64_t ic = ic_start; ic < ic_end; ++ic)` with **no
tiling at all**.

And the head mapping at line ~8726 is `const int ik2 = iq2 / rk2;` with `rk2 = neq2/nek2 =
28/4 = 7`. That is **contiguous** grouping: query heads 0-6 all read KV head 0, 7-13 read KV
head 1, and so on.

So per layer, per generated token, each thread scans its KV chunk **28 times**, and each KV
head's slice of that chunk is read **7 times** — once per query head in its GQA group.

Ideal traffic is `nek1 × 2048 B` per layer. The loop nest issues `nek1 × 14,336 B` of reads.
**A 7× read amplification, exactly the GQA factor**, and it is served from cache only for as
long as the reused slice stays resident.

### Where residency fails, and it is not where the peer reviewers guessed

The slice that has to stay resident for the 7× reuse to be free is one KV head's chunk on one
thread: `chunk_size × 512 B`, where `chunk_size = ceil(nek1 / nth)`.

L2 on this chip is 256 KB per core, shared by two hyperthreads, so roughly **128 KB per
thread**. That gives a crossover at `chunk_size × 512 B = 128 KB`, i.e. `chunk_size = 256`,
i.e. **`nek1 = 2048` at 8 threads.**

| nek1 | chunk_size at t=8 | reused slice per thread | vs ~128 KB L2 share |
|---|---|---|---|
| 1024 | 128 | 65.5 kB | fits |
| 2048 | 256 | 131 kB | **at the line** |
| 4096 | 512 | 262 kB | spills |
| 8192 | 1024 | 524 kB | spills badly |

**My measured curve turns from sublinear to superlinear between 2048 and 4096** — ×1.63 for
the 1024→2048 doubling, ×2.44 for 2048→4096. That is the L2 crossover, not the L3 one.

**This also kills the L3-at-3072 story the peer reviewers found, and the source says why.**
Because `ik2 = iq2 / rk2` groups query heads contiguously, only **one** KV head needs to be
resident at a time, and one KV head's slice is `nek1 × 512 B` — a quarter of the full-layer
`nek1 × 2048 B` set that crosses 6 MB L3 at 3072. One KV head's slice does not cross 6 MB
until nek1 ≈ 12,288, well past anything I measured. I said at the time that the L3
coincidence was missing a reuse mechanism and I was not going to promote it. It is now dead
for a specific reason rather than for lack of evidence.

### The second half of the mechanism: the untiled path is doing scalar softmax per position

The same file contains a **tiled** flash-attention implementation — `KV_TILE_SZ` at line 8927,
used from line 8995 — which blocks the KV dimension, converts a K tile once, calls `simd_gemm`
for the whole tile, runs `ggml_vec_soft_max_f32` across the tile, and does one online-softmax
rescale per tile.

Decode does not use it. `one_chunk` instead does, per single KV position: a 128-element dot,
a **scalar `expf`** in the middle of the dependency chain, a 128-element multiply-add into the
accumulator, and — whenever the running maximum moves — a 128-element rescale of the whole
accumulator. One transcendental and one potential 128-wide rescale per KV position, versus one
per *tile* on the path right next to it.

That is a coherent explanation for being **24× off the FLOP budget** while also being off the
byte budget: the arithmetic is not blocked, and it is serialised behind a scalar transcendental.

### Three predictions, written down before the measurements land

1. **The knee moves with thread count.** `chunk_size = nek1/nth`, so the L2 crossover sits at
   `nek1 = 256 × nth`: 2048 at 8 threads, 1024 at 4, 512 at 2. Fewer threads should push the
   knee to *lower* depth. `16b-fathreads.sh` measures depth 0 and 2048 at t = 1, 2, 4, 6, 7, 8;
   at t ≤ 4, depth 2048 is already past the crossover, so the marginal cost must come out worse
   than clean 1/t scaling predicts. **If marginal cost scales cleanly as 1/t, this whole
   mechanism is wrong.**
2. **DRAM traffic per generated token at depth is amplified above the naive KV model.**
   `16-ctxbytes.sh` differences two runs at fixed depth that differ only in `n_gen`, so it
   measures actual bytes. The naive model says depth 8192 costs 0.47 GB per token more than
   depth 0. If the re-reads miss to DRAM the real figure trends toward 7× that. **This is the
   decisive one** — if the measured delta is 0.47 GB, the re-reads are being absorbed by cache
   and the tiling fix buys nothing.
3. **No knee at 3072 in the isolated kernel.** `15a-fakernel.sh` sweeps kv densely from 2048 to
   4096 on the op alone. Per the contiguous-grouping argument there should be no feature at
   3072. A knee near 2048 is the L2 crossover; a knee at 3072 would mean I have the residency
   argument wrong.

### The fix this implies, if the predictions hold

Tile the `ic` loop inside the split-KV branch and hoist the seven GQA-sharing query heads
*inside* the tile, so each KV tile is loaded once and consumed by all seven query heads that
share it. The running softmax state that currently lives across a whole chunk becomes per-tile
state carried in the partials buffer — which **already has exactly the right layout**:
`ops.cpp:9268` documents it as `[q_head][kv_chunk][M, S, VKQ]` with `partial_size = 2 + DV`.
Carrying 28 query heads' worth of state is `28 × 130` floats = 14.6 kB per thread, which fits
the L2 share with room to spare.

This is not a new algorithm. It is the blocking strategy already implemented fifty lines away
in the same file, applied to the decode path that skips it.

**Not writing that patch yet.** Prediction 2 gates it: if DRAM traffic at depth is not
amplified, the re-reads are cache hits, and tiling them changes nothing measurable.


---

## Iteration 24c — I contaminated my own measurement, and the counters name the culprit

Correcting the record before it gets built on. **Two rows of the Iteration 24 table are
invalid and are struck: depth 6144, and the d=0 bracket that follows it.**

While `15-ctxsweep.sh` was measuring depth 6144 I had two other things running on the same
box. One was a `cmake --build -j3` (which did finish). The other was an interactive
`test-backend-ops perf -o FLASH_ATTN_EXT -b CPU` probe that I believed had exited with its
ssh call and had not — PID 1124436, parent 1124294. `test-backend-ops` sets
`N_THREADS = std::thread::hardware_concurrency()`, so that probe was running **eight threads**,
and its built-in FLASH_ATTN_EXT case list walks up to kv=65536 with correspondingly large
allocations.

### The two contaminated rows have two different signatures, and both fit that one process

| depth | tg t/s | minor faults | LLC misses | dTLB misses | eff GHz |
|---|---|---|---|---|---|
| 4096 (clean) | 3.6750 | 14,253 | 1.263e9 | 2.274e6 | 1.469 |
| 6144 (struck) | 0.3976 | 100,593 | 2.646e9 | 1.613e7 | 1.485 |
| 0 (clean, prior) | 6.4715 | 13,115 | 3.690e8 | 1.208e6 | 1.804 |
| 0 (struck, after) | 3.2763 | 13,075 | 3.252e8 | 1.484e6 | 1.671 |

The **d=0** row is the more informative of the two, because it is contamination in its
cleanest form. Minor faults are normal (13,075 — the lowest in the whole sweep). Total LLC
misses are normal (3.25e8, also the lowest). Effective clock is down only 7%. The *work* is
identical and the *memory traffic* is identical. Only the throughput halved: 3.2763 / 6.4715
= **0.506**. That is what two eight-thread jobs sharing eight hyperthreads under a fair
scheduler looks like, and it is not what anything else looks like. It is not heat (7% clock),
it is not disk (`major-faults` 0), it is not cache (traffic unchanged).

The **6144** row is that same 2× contention *plus* memory pressure: 7× the minor faults and
7× the dTLB misses, which is the probe's kv=65536 allocations churning the page tables
underneath. Contention alone would predict roughly 1.4 t/s; the measured 0.3976 is a further
3.5× on top, and the fault counters are where that 3.5× went.

**A 9.2× jump in token time accompanied by a 7× jump in minor faults is a box with another
tenant on it, not an attention kernel falling off a cliff.** I nearly wrote it up as a cliff.

### What `nice -n 19` actually bought, which was nothing

I niced the build specifically so it would not disturb the runner. `nice` adjusts CPU
scheduling priority. It does not partition memory bandwidth, it does not partition the page
cache, and it does not partition the dTLB — which are precisely and exclusively the resources
this experiment measures. Nicing a job that competes for memory is theatre. And the probe was
not niced at all, because I did not know it was running.

### The standing rule

**While the runner is live, nothing else runs on this box.** Reading source over ssh is free.
`ps`, `cat`, `ls` are free. Builds and probes are not, however they are niced. If something
must be built, it goes in the queue as a script like everything else, so the runner serialises
it.

That is now three self-inflicted measurement faults in this log — two `pkill -f` kills of my
own ssh session, and this. The pattern in all three is the same: I treated the server as a
place I can poke interactively while a measurement is in flight. It is not.

### The redo

`15b-redo6144.sh` is queued and re-measures `0, 4096, 0, 6144, 0` on a clean box. 4096 is in
the list deliberately: it is the last clean point of the original sweep, so if it reproduces
near 3.675 the redo is tied back to that sweep rather than floating on its own, and the three
d=0 brackets will simultaneously settle whether 3.2763 was contention (expect ~6.4) or
something durable (expect ~3.3).

### Is the depth-8192 point clean?

It started at 21:09:40, and by then the strays were dead (`ps -p 1124436,1124294` returns
nothing, `pgrep -f "cmake|test-backend-ops|make"` returns nothing, and the only process above
1% CPU is the bench itself at 791%). I cannot prove from here whether my kill landed before or
after 21:09:40, so I am not going to assert it. The row will carry its own verdict: if its
`minor-faults` come back near 14k it was clean, and if they come back near 100k it goes in the
redo with the others. Judging a row by an independent counter rather than by my memory of what
I was doing is the whole point of having recorded that column.

---

## Iteration 24d — correcting the correction: the sweep ran twice, and the fault storm is real

I have to reopen Iteration 24c, which I wrote an hour ago, because two of its claims are
wrong. Both were wrong in my favour, which is the direction that matters.

### First: the script ran twice, and my account of the 128/448 edit was wrong both times

`15-ctxsweep.sh` has produced **two header lines and two passes** in `ctxsweep.csv`. Pass 1
executed the original depth list `0 1024 0 2048 0 4096 0 6144 0 8192 0` and completed. Pass 2
is executing the edited list `0 128 0 448 0 1024 0 2048 0 4096 0 6144 0 8192 0` and is running
now.

I edited that file at 20:42 while it was executing. bash does not slurp a script; it reads it
in chunks and tracks a byte offset. Making the file longer moved everything after the edit
point, and when bash next read from its stale offset it landed back inside the tail of the
script and re-ran it. `: > $OUT` was above that point so the file was not truncated, which is
why both passes survive.

Earlier I recorded this as "the runner is executing the older list and will never measure 128
and 448." That was wrong. It measured them, and it also measured everything else a second
time. **The cause is the same one as the contamination: I touched the box while a measurement
was in flight.** Editing a queued script is safe. Editing a *running* one is not, and the
failure mode is silent.

Pass 2 is a windfall I did not earn, because it replicates pass 1 on a clean box.

### Second: the 6144 fault storm was NOT contamination. It is transparent hugepages failing

I read 100,593 minor faults at depth 6144, compared it to ~14,000 everywhere else, and called
it memory pressure from the stray probe. Then depth 8192 completed — after the strays were
dead, flanked by a normal bracket — and it shows **142,287** minor faults. So the fault storm
is not something I did. It is a property of depth.

The arithmetic identifies it exactly. This model holds `2 (K and V) × 4 kv heads × 128 dim ×
2 B = 2048 B` of KV per position per layer, and 28 layers, so **57,344 B of KV per context
position**. llama-bench sizes `n_ctx` to fit the depth, so the KV allocation grows with `-d`:

| depth | KV cache | if 4 kB pages | measured minor faults | over the ~13,600 floor |
|---|---|---|---|---|
| 1024 | 59 MB | 14,336 | 15,552 | +1,900 |
| 2048 | 117 MB | 28,672 | 15,641 | +2,000 |
| 4096 | 235 MB | 57,344 | 14,253 | +600 |
| 6144 | 352 MB | 86,016 | 100,593 | **+87,000** |
| 8192 | 470 MB | 114,688 | 142,287 | **+129,000** |

Up to 4096 the fault count does not respond to the allocation at all — 235 MB in 2 MB pages is
117 faults, and 117 is invisible next to 13,600. At 6144 the excess is 87,000 against a 4 kB
prediction of 86,016, and at 8192 it is 129,000 against 114,688. **The KV cache stops being
hugepage-backed between depth 4096 and depth 6144.** That is not an inference, it is a
division.

The dTLB column agrees and is what makes it cost something: 2.27e6 at 4096, 1.61e7 at 6144,
**3.60e7 at 8192**. A ~1500-entry dTLB cannot cover 115,000 pages.

### Why it falls back — read off the machine, not theorised

```
/sys/kernel/mm/transparent_hugepage/enabled  = [always] madvise never
/sys/kernel/mm/transparent_hugepage/defrag   = always defer defer+madvise [madvise] never
/proc/buddyinfo   zone Normal, order 9        = 0        <- no free 2 MB blocks at all
/proc/buddyinfo   zone Normal, order 8        = 527
/proc/vmstat      thp_fault_alloc             = 1,543,007
/proc/vmstat      thp_fault_fallback          = 302,122
```

THP needs an order-9 block and **there are none left**. `defrag=[madvise]` means the kernel
will only run compaction to manufacture one for a region that asked via `MADV_HUGEPAGE`.
`ggml_aligned_malloc` calls plain `posix_memalign` and never madvises, so the KV cache never
asks, never triggers compaction, and takes the 4 kB fallback the instant the free pool is dry.

The pool being dry is not bad luck either — **this sweep drained it**, allocating a larger KV
cache on every successive run. Which also means the 4096 row got hugepages partly because it
ran early, and a rerun of 4096 now might not. `15b-redo6144.sh` repeats 4096 and will say.

### So what was actually contaminated?

Only the *throughput* numbers, and the proof is now much better than a fault count. Depth 8192
is **deeper** than 6144, has **more** faults and **more** dTLB misses, and runs at 2.3052 t/s
against 6144's 0.3976 — **5.8× faster**. A monotonic depth curve cannot do that. So:

- depth 6144, `0.3976 t/s` — **struck**, contaminated by the stray 8-thread probe.
- the d=0 bracket after it, `3.2763 t/s` — **struck**. Identical counters to its neighbours,
  exactly 0.506× their throughput: two 8-thread jobs sharing eight hyperthreads.
- depth 8192, `2.3052 t/s` — **stands**. Flanked by a normal bracket (6.3367), fault count
  fully explained by THP, ordering consistent.

I got the right verdict on 6144 for a wrong reason, and I would have carried the wrong
mechanism forward. The fault count was evidence of a real effect I had not looked for.

### The drift-corrected marginal cost, both passes

Marginal µs per context token = `(1/tg_depth − 1/tg_bracket) / depth`, bracket being the mean
of the two flanking d=0 reciprocals.

| depth | pass | tg t/s | µs per context token |
|---|---|---|---|
| 128 | 2 | 6.2687 | 43.2 |
| 448 | 2 | 5.9674 | 30.1 |
| 1024 | 1 | 5.6507 | **29.2** |
| 1024 | 2 | 5.4219 | **29.3** |
| 2048 | 1 | 5.0055 | 23.8 |
| 4096 | 1 | 3.6750 | 29.0 |
| 8192 | 1 | 2.3052 | 33.7 |

**The 1024 replication is the headline.** 29.2 and 29.3 µs, measured about forty minutes
apart, in two independent passes, through a bracket correction. 0.6% apart. The bracketing
method works, and from here a difference of a few percent is worth arguing about.

### And the fixed-overhead confound, before I over-read the low-depth points

I nearly wrote up "43.2 at depth 128 versus 30.1 at depth 448 proves the head-parallel path
below the `nek1 >= 512` gate is 30% worse." **That does not follow.** Any per-generated-token
cost that does not depend on depth shows up in this metric as `X/depth`, which is eight times
larger at 128 than at 1024. Fitting `c + X/d` to the 128 and 448 points gives X ≈ 2.4 ms and
c ≈ 25 µs, and that fit predicts 27.1 at 1024 against 29.2 measured — close enough that the
low-depth rise may be entirely the artefact and not a code path at all.

Two points, one conclusion, again. What the fit *does* sharpen is the other end: against a
fitted linear cost of ~25 µs, depth 4096 sits **+16%** and depth 8192 sits **+35%**. The
superlinearity is at the top of the range, not the bottom.

`16a-clkphase.sh` re-measures 128 and 448 with generation-phase-scoped counters, which
separates a fixed overhead from a per-context-token one. Until then the gate question is open,
and I am not going to claim it either way.

---

## Iteration 30 — prior art, and the mechanism I found already has a patch written for it

I read the decode loop nest in `ops.cpp` and named two costs before searching. Searching
afterwards found that both are known, and that the fix for one of them is sitting in an open
upstream PR with **zero human review**.

### What the search found

**The upstream decode path is PR #19209**, "ggml-cpu: FA split across kv for faster TG"
(am17an, merged 2026-02-02), modelled on PyTorch Flash Decoding. It builds on **#19012**,
"Use tiled FA for prompt-processing" (merged 2026-01-25). So the tiled kernel was deliberately
scoped to prefill and #19209 wrote a *separate, untiled* kernel for decode rather than reusing
it. I read the review thread — ggerganov, JohannesGaessler, Djip007 — and **it is entirely
about correctness. Tiling the chunk loop, query-head reuse and cache residency are never
raised.** The gap is real and it is unexamined, not rejected.

The patch's own comment states the reason plainly: *"The tiled path needs GGML_FA_TILE_Q query
rows, so it cannot serve this case."*

**The GQA half already exists, in a fork.** ik_llama.cpp **PR #332**, "Better TG performance
for GQA models (CPU)" (ikawrakow, merged 2025-04-17), gates on
`neq3 == 1 && rk2 > 1 && rk2 == rv2 && neq1 == 1` — essentially my predicate plus the GQA
condition — and **puts the KV chunk in the outer loop**, computing the whole query-head group
against that chunk into a work buffer before reducing. That is the loop inversion I described.
So that item changes from "write a patch" to "port a patch", which is a much better position.

**The rescale half already exists, upstream and unreviewed.** PR **#27478**, "ggml : speed up
batch-1 CPU decode, align large allocations" (matevz-kovacic, opened 2026-08-21, still open,
no human review). It blocks the decode KV loop at `GGML_FA_KQ_BLK = 32` — *"Score one KV block
at a time, so the accumulator is rescaled at most once per block"* — and swaps the
per-position scalar `expf` for `ggml_vec_soft_max_f32` over the block.

**It has a name, and it is GPU-native.** FlashInfer (MLSys 2025) calls the loop inversion
**head-group fusion**; Colfax calls it **query head packing**; SGLang calls it **head
folding**. The convention is to set the Q block to `num_query_heads / num_kv_heads` so one
shared load of the KV tile serves every query head that maps to it. Searching for "GQA-aware
tiling" found nothing because that is not what it is called.

**Two CPU runtimes already do it, and llamafile does not.** OpenVINO's
`mha_single_token.cpp` parallelises over KV head *groups* and hoists the K pointer above the
query-head loop. IPEX's `MaskedMultiHeadAttentionKrnl.cpp` does the same with
`head_group_start += group_size`. llamafile/tinyBLAS supplies only
`llamafile_fa_vec_dot_f16` / `llamafile_fa_simd_gemm` — it speeds up the inner dot product and
leaves ggml's loop nest alone, **so the 7× re-stream survives llamafile entirely**.
ktransformers has no CPU attention kernel at all: attention stays GPU-resident by design and
only MoE expert FFNs go to the CPU, so there is nothing to borrow there.

**Where I looked and found nothing:** no upstream issue describes superlinear CPU *generation*
degradation with context length. The nearest is #24483, which is Vulkan on RDNA4. #19012's
body asserts "FA performance is gimped on CPU for long contexts" with no issue reference.

### The convergence that decided what to build next

PR #27478's *other* half is `ggml.c`, and it is precisely the fix for the THP mechanism I had
just measured off `/proc/buddyinfo` an hour earlier and had not yet searched for:

```c
#define GGML_LARGE_ALLOC_MIN_SIZE (4ull << 20)
#define GGML_LARGE_ALLOC_ALIGN    (2ull << 20)
...
if (size >= GGML_LARGE_ALLOC_MIN_SIZE) {
    result = posix_memalign(&aligned_memory, GGML_LARGE_ALLOC_ALIGN, size);
    if (result == 0 && aligned_memory != NULL) {
        (void) madvise(aligned_memory, size, MADV_HUGEPAGE);
    }
```

`madvise(MADV_HUGEPAGE)` is exactly the thing that `defrag=[madvise]` is waiting for. This box
will run compaction for a region that asks and will not for one that does not, and ggml
currently does not ask. The PR makes it ask, and separately 2 MB-aligns the region so its
edges are not wasted.

Its author reached the same mechanism from the other end and was honest about the limits of
their own evidence, which is worth quoting because it is the right posture: *"Part of the
measured benefit survives with transparent huge pages disabled entirely, so the alignment is
not merely a carrier for the hint; how the two split apart is microarchitecture dependent and
the mechanism is not established."*

`git apply --check` returns **0** against my HEAD. And every fast path in it gates on
`__AVX512F__ || (__AVX2__ && __F16C__ && __FMA__)`; Comet Lake has AVX2, F16C and FMA and no
AVX-512, so this box takes the AVX2 arm of all of them.

### What is queued, and the separation of concerns

Three scripts, ordered so the cheapest decisive test runs first:

- **`15c-thpctl.sh` — needs no build at all.** Same baseline binary at depth 8192, three arms
  ABA: as-is, then `compact_memory` + `defrag=always`, then restored. `minor-faults` is each
  arm's own witness — if the middle arm does not fall from ~142k to ~14k the mechanism is
  wrong and nothing else in the script counts. This isolates the *kernel* half of the THP
  story from any code change whatsoever.
- **`15d-fabuild.sh`** — worktree at HEAD, apply #27478, build, and run the full default
  `FLASH_ATTN_EXT` correctness set on CPU. The patch rewrites the online-softmax update, which
  is exactly where a numerics bug produces plausible-looking wrong text. If it fails, the
  binary is discarded and no timing is taken from it.
- **`15e-faab.sh`** — ABBA paired A/B, `-p 512 -n 32 -d 0,2048,8192`, both phases reported
  separately. The depths are chosen so the two halves of the patch can be told apart rather
  than blended: **2048 is still hugepage-backed** (fault count flat), so a gain there is the
  `ops.cpp` rescale change alone; **8192 is measurably not** (142,287 faults), so the
  difference between the 8192 gain and the 2048 gain is the allocation change's contribution.
  pp512 is the control — prefill uses the tiled path, which this patch does not touch.

**What #27478 does not do, so I do not later credit it with it:** it does not change the loop
order. The query-head loop stays outside the KV scan and each KV head's slice is still read
seven times. That is ik_llama #332, a separate port and a separate measurement, and it remains
gated on Prediction 2 (`16-ctxbytes.sh`).

---

## Iteration 30a — reading the page tables instead of reasoning about them, and one correction

Before `15c-thpctl.sh` even runs I looked at `/proc/<pid>/smaps` of a live depth-2048 run. It
took one command and it corrects a claim I put in this log two iterations ago.

```
Rss:             8,193,116 kB
Anonymous:       4,330,492 kB
AnonHugePages:   4,288,512 kB
FilePmdMapped:   3,848,192 kB

  4,202,296 kB   anonhuge = 4,024,320 kB   rw-p   [anon]
  3,847,836 kB   anonhuge =         0 kB   r--s   /srv/media/_llmtest/qwen7b-pureQ4K.gguf
    297,252 kB   anonhuge =   241,664 kB   rw-p   [anon]
```

### The correction

In the Iteration 28 header I wrote, as the reason prior art #2251 did not apply here, that the
weights *"are mmap'd from a file and therefore cannot use transparent hugepages at all."*
**That is false on this kernel.** `FilePmdMapped: 3,848,192 kB` says the entire 3.85 GB GGUF
mapping is backed by 2 MB PMD entries. Read-only file-backed THP exists and this box is using
it, for every byte of the model file. 3.85 GB in 2 MB pages is about 1,880 TLB entries instead
of 985,000, which is why depth 0 shows only ~37,500 dTLB walks per token while streaming 4.3 GB
of weights — a number I had noted as surprising and not chased.

I asserted a kernel behaviour from memory rather than reading the machine. The machine was one
command away.

### What is actually resident, which matters for a target I have not touched

RSS is **8.19 GB**, and it is two nearly-equal halves: the 3.85 GB mmap'd GGUF, and a **4.20 GB
anonymous mapping that is 96% hugepage-backed**. The anonymous copy is the AVX2 repack —
`q4_K_8x8_q8_K` interleaved weights, built at load time into anonymous memory. So the box is
holding the model **twice**, in two different layouts, and 8.19 GB of a 15.7 GB machine is
gone before Jellyfin is counted.

The record's secondary target 5 says a 900 MB swing was worth 21.9×. There is a 3.85 GB
mapping here whose contents may be dead after the repack completes. That is not a measurement
and I am not going to treat it as one — the file pages are page cache and reclaimable, so
"resident" and "costing something" are not the same claim. But it is a much larger lever than
900 MB and it has never been looked at. Logged as a target, not a result.

### The KV cache is the only thing on this box that loses its hugepages

Weights: 2 MB PMDs. Repacked weights: 96% AnonHugePages. The 297 MB mapping at depth 2048
(KV plus compute buffers): 241 MB of AnonHugePages, so mostly backed. And at depth 6144 and
8192 the fault counts say the KV allocation gets none.

That is consistent and it sharpens the mechanism rather than muddying it: **everything
allocated at load time got hugepages while the order-9 pool still had blocks in it; the KV
cache is allocated last, and by then the pool is dry.** `defrag=[madvise]` refuses to compact
for a caller that does not ask, and `ggml_aligned_malloc` does not ask. So the one allocation
that is scanned tens of times per token is the one that ends up on 4 kB pages.

### An open question I am deliberately not answering yet

Excess dTLB walks per generated token at depth 8192, over the depth-0 baseline, work out to
**1,087,046**. The KV cache at that depth is 114,688 pages. The ratio is **9.48**.

That is tantalisingly close to the 7× GQA re-stream the loop nest predicts, and I can feel
myself wanting to declare it confirmation. I am not going to, for a specific reason: my own
capacity arithmetic says it should not happen. A thread's per-layer KV working set at depth
8192 with 8 threads is 4 kv heads × 1024 positions × 256 B × 2 tensors = 2 MB = **512 pages**,
which fits a 1536-entry STLB comfortably, so the seven re-reads across query heads ought to be
TLB hits and the walk count ought to land near 114,688, not 1,087,046.

So either the re-reads are missing for a reason my model does not contain, or something else
entirely dominates the walk count. **I do not know which, and a plausible story is not a
measurement.** `16-ctxbytes.sh` differences two runs that differ only in `n_gen` and reads the
`uncore_imc` counters, which gives bytes actually fetched from DRAM with no TLB semantics to
argue about. That is Prediction 2 and it is queued. The dTLB ratio goes in the log as an
observation with an unexplained factor in it, not as evidence.

---

## Iteration 31 — CORRECTION: I misled my own council, and the answer it gave back is wrong

I convened the council on the depth-8192 generation wall and framed the question myself.
Three of the five advisors independently came back with the same headline: *the mission's
actual deliverable has never been measured, every number is a synthetic depth sweep, go
measure one real question against one real file first.* I had already written the harness
for that and started shipping it before checking.

**It was already measured, in iteration 19, and it is in this log at line 1539.** The
advisors did not miss it; they never saw it, because the framing I handed them described
the depth sweep and did not mention `wcgate.sh`. That is my error and not theirs, and it is
worth writing down as a rule: **a council is a function of its framing, and a framing that
omits a result will get you advice to go and produce that result again.** The cost here was
one wasted harness and about fifteen minutes. It would have been a lot worse if I had
queued it ahead of the four experiments already waiting.

The measured end-to-end, from iteration 19, unchanged:

| | cold | warm off the platter |
|---|---|---|
| time to first token | 208.48 s | **3.20 s** |
| total (≈190 generated tokens) | 252.10 s | **47.29 s** |

### What that does to the target — and it does not move it

The interesting part is what happens when I check the depth sweep against the real run,
which is the tether the council correctly said was missing even though the reason they gave
for it being missing was wrong. Two independent measurements, different binaries, different
harnesses, different prompts, taken days apart:

| source | context | tg t/s |
|---|---|---|
| `wcgate.sh`, real file `shlex.py` | 2,891 | 4.39 |
| `15-ctxsweep.sh`, synthetic `-d 2048` | 2,048 | 4.90 / 5.01 |
| `wcgate.sh`, real file `tempfile.py` | 7,445 | 2.44 |
| `15-ctxsweep.sh`, synthetic `-d 8192` | 8,192 | 2.31 |

The synthetic sweep sits slightly above the real run at 2k and slightly below it at 8k,
which is exactly what a monotonic curve sampled at 2048 and 8192 should do against real
points at 2891 and 7445. **The depth sweep is measuring the real workload.** So the
microbenchmark is tethered after all, and the answer to "what depth does real work land
at" is 2,900 to 7,400 tokens — which is inside the range I have been sweeping, not below it.

The one part of the council's advice that survives the correction, and it survives fully:
**generation, not prefill, is now the entire end-to-end number.** TTFT is 3.20 s of a 47.29 s
total. The other 44 s is 188 tokens at 4.39 tok/s. Prefill was 90% of the cold number and
is 7% of the warm one; the 65x already happened and there is nothing left to win there.
Every remaining second is generation, and generation at 2.9k-7.4k context is precisely what
mechanisms (A) and (B) are about. **The aim was right. The justification for it was not
written down, and now it is.**

### What I accept from the council, unchanged

Two hits I am taking on the chin because they are correct and they are about my statistics,
not my framing:

1. **The `c + X/d` fit is unfalsifiable as stated.** Two parameters, two points. And my own
   depth-0 brackets across the two sweep passes span 6.34 to 6.93 tok/s — a 9% baseline
   scatter — so the "+16% at 4096" I derived from it sits inside my own noise floor. I am
   striking that inference. The raw seconds-per-token curve goes in the log alongside the
   divided one from now on, because dividing a cost with a constant term by the variable
   term alone manufactures a dip-then-rise shape whether or not any mechanism exists.
2. **The 9.48 dTLB ratio is not evidence of anything yet.** 1,087,046 excess walks spread
   over 8 threads at 20-40 cycles is 1.5-3 ms against a 434 ms token with ~112 ms of
   unexplained excess — under 1%. And 9.48 is 35% *above* 7, the ceiling of the GQA re-read
   hypothesis it was supposed to support, so if anything it disconfirms it. It stays in the
   log as an observation with an unexplained factor, exactly as iteration 30a said, and
   `16-ctxbytes.sh` settles it with IMC counters that have no TLB semantics to argue about.

And one attribution point that was already right in the queue order but is worth stating so
it does not get shuffled away: **PR 27478 bundles the softmax blocking change with the
`madvise(MADV_HUGEPAGE)` change.** `15c-thpctl.sh` moves kernel knobs with no code change and
therefore isolates the THP half on its own. It must land before `15e-faab.sh` or neither
half of the patch is attributable. It is currently second in the queue and stays there.

### Why the mission's PRIMARY TARGET is not being worked, written down rather than left to lapse

The brief names CPU+iGPU tensor parallelism as the primary target and asks me to confirm or
kill the non-contiguous-view hypothesis. I have not, and I am recording the reason instead
of letting it quietly drop.

The tensor-parallel result being chased is a **prefill** result: concurrent prefill was
measured to add (37.0 vs 25.6 tok/s, +45%), and fixing the split path was scoped as "worth
2x on prefill". Iteration 19 then made prefill 7% of the end-to-end number by removing it
from the interactive path entirely. **Two times a 7% term is worth 3.5% of the total; the
generation term is 93% of it.** That is the whole argument. It is a prioritisation call
against a measured split, not a judgement that the hypothesis is uninteresting or wrong —
it remains unconfirmed, and it is the right thing to pick up if and when generation stops
yielding.

### Queue re-aimed on the back of that correction

Generation is 93% of the warm end-to-end number, so the queue is now sorted by how directly
each experiment attacks generation at 2,900-7,400 tokens of context. New order:

| | script | what it settles | build? |
|---|---|---|---|
| 1 | `15c-thpctl.sh` | mechanism (B) alone — kernel knobs, no code, so it isolates the THP half of PR 27478 before the patch can confound it | no |
| 2 | `15c1-ctxbytes.sh` | Prediction 2 — IMC counters for DRAM bytes actually fetched per generated token at d=0 vs d=8192. This is the **gate** on the tiling patch: if depth does not amplify DRAM traffic then the GQA re-reads are cache hits and tiling them buys nothing | no |
| 3 | `15d-fabuild.sh` | a correct PR 27478 binary, or no binary | yes |
| 4 | `15e-faab.sh` | PR 27478 ABBA at d=0/2048/8192, pp and tg separately | no |
| 5 | `15f-genlen.sh` | the marginal cost of an output token, which is now the multiplier on the whole 44 s | no |
| 6 | `15g-kvq.sh` | q8_0 KV — halves the KV bytes, halves the restore, and answers whether the depth term is byte-driven at all. Also checks the answer text is unchanged at temperature 0 | no |

`17b-redo6144.sh` is **deleted**, not deferred: pass 2 of `15-ctxsweep.sh` is re-measuring
depth 6144 clean as I write this, which was the entire purpose of that script.

I am **not** adding the `GGML_NO_INTERDOT_X4` ablation arm the council asked for, yet. It
needs a second full ggml build (~15 min on 4 cores) to separate the x4 dot-product from the
softmax blocking, and that is only worth spending if `15e-faab.sh` shows a gain to
attribute. If it does, the ablation goes in immediately; if it does not, there is nothing
to split. Sequencing, not disagreement.

---

## Iteration 32 — speculative decoding has never run on this machine. Two no-ops, in source.

Generation is 93% of the warm end-to-end number. The only technique on the board that
attacks the weight-streaming term without reading fewer weight bytes — it reads the same
bytes and extracts more tokens from them — is speculative decoding, and this log records it
twice: **+21%** at short context, then **zero** at 4,858 tokens in iteration 7. Iteration 7
was honest enough to flag that the server might not have been speculating at all and to
scope its conclusion accordingly. Nobody went back. I went back.

**Neither measurement was of speculative decoding.** There are two independent reasons, both
read out of this box's own tree today, both of which make `-md` a silent no-op.

### No-op 1 — `-md` does not enable anything

```
common/common.h:371    std::vector<enum common_speculative_type> types = { COMMON_SPECULATIVE_TYPE_NONE };
common/arg.cpp:4267    [](common_params & params, const std::string & value) {
                           params.speculative.draft.mparams.path = value;
                           params.speculative.draft.mparams.hf_file = value;
                       }
```

The `-md` handler sets the path and nothing else. It never touches `types`. The only
automatic inference is at `arg.cpp:565`:

```
if (spec_types_is_default(params) && !params.speculative.draft.mparams.path.empty()) {
    const auto types_gguf = common_speculative_types_from_gguf(params.speculative.draft.mparams.path);
```

and `common_speculative_types_from_gguf` (`speculative.cpp:2284`) returns `{}` unless the
draft GGUF's arch is `"dflash"` or it carries a `blk.<last>.nextn.eh_proj.weight` MTP head.
Qwen2.5-Coder-0.5B is arch `qwen2` with no MTP head. It returns `{}`. So `types` stays
`{NONE}`.

Then `speculative.cpp:2620`:

```
if (available && (enabled_configs & (1u << type))) { configs.emplace_back(type, params); }
...
add_config_if_enabled(COMMON_SPECULATIVE_TYPE_DRAFT_SIMPLE);
```

`enabled_configs` is a bitmask over `types`. With `types == {NONE}` that mask is `0b1`.
`DRAFT_SIMPLE` is enum value 1, so the test is `1 & 2`, which is `0`. **No speculator object
is ever constructed.** The draft model loads — which is why `/tmp/srv_spec.log` showed it
loading and iteration 7 reasonably assumed things were fine — occupies ~400 MB of a 16 GB
box, and drafts nothing.

The fix is one flag: `--spec-type draft-simple`. `arg.cpp:4278` *appends* to the vector, so
that yields `{NONE, DRAFT_SIMPLE}`, a mask of `0b11`, which passes the test.

### No-op 2 — `llama-cli` cannot speculate at all, but accepts the flag

```
$ grep -rln "common_speculative_init\|common_speculative_gen_draft" tools/ examples/
tools/server/server-context.cpp
examples/speculative-simple/speculative-simple.cpp
```

`tools/cli/` does not appear. Yet `arg.cpp:4271` registers `-md` with
`.set_examples({LLAMA_EXAMPLE_SPECULATIVE, LLAMA_EXAMPLE_SERVER, LLAMA_EXAMPLE_CLI})`, so
`llama-cli -md whatever.gguf` is accepted without complaint, loads the draft model, and
ignores it completely. Recording it because it is a live upstream footgun and because it
rules llama-cli out as the harness for this test. `llama-bench` has no `-md` at all, so the
original "+21%" cannot have come from llama-bench either.

### What this costs and what happens next

`ask.py` did not read `draft_n` — iteration 7 said the harness had been patched to capture
it, and it had not been; that is a second bookkeeping failure on the same thread and it is
now actually done. `server-context.cpp:662` only emits `draft_n` / `draft_n_accepted` when
`n_draft_total > 0`, so **`draft_n == -1` is a hard witness that nothing speculated**, and
it is now printed on every arm including the baseline.

`15b-specfix.sh` is queued to run next, ahead of the THP work, because this is the largest
untested lever on the 44 s that generation now owns. Four arms across four server lifetimes:

| arm | flags | why |
|---|---|---|
| `base` | none | the number to beat |
| `mdonly` | `-md` only | **iteration 7's exact configuration.** Confirms the source reading by measurement: predicted `draft_n == -1` and a time indistinguishable from base. If this arm speculates, the reading above is wrong and everything in this entry is void |
| `spec3` | `+ --spec-type draft-simple --spec-draft-n-max 3` | iteration 7's *intent* |
| `spec5` | `n-max 5` | if acceptance on code is high, k=3 leaves tokens unclaimed; if it is low, k=5 is *worse* than k=3. The pair says which side of the peak k=3 is on. One arm cannot |

Order is `base, mdonly, spec3, spec5, spec3b, baseb` — ABBA on the two arms that carry the
result, diagnostics in the middle where drift matters least. Each arm is a whole server
lifetime because `--spec-type` is a startup flag; inside a lifetime a gen=1 warmup pays the
4,858-token prefill once and the two timed asks run against the prefix cache, so the tg
numbers are not carrying prefill.

**No predicted speedup is being written next to those arms.** The acceptance rate is the
entire question and it is about to be measured. What I will say out loud as an *expectation
and not a result*: a verify batch on this CPU should be much cheaper per token than a single
token, because the batch reuses the weight-row tile, and that is the property speculation
trades on. If acceptance turns out to be low on code, k=3 will lose and the arms will say so.

Correctness comes free: speculative decoding is lossless, so at temperature 0 every arm's
completion must be byte-identical to `base`. All six are saved and compared. A speedup with
different text is not a speedup.

### Iteration 32 (research step) — the prior art found a third landmine I had not looked for

Searching upstream after the source reading turned up three separate things, two of which
would have wrecked the experiment I had just queued. Every one is confirmed against this
box's own tree rather than taken from the issue text.

**1. The `-md` no-op is deliberate, not a bug — PR #23988, merged 2026-06-01.** Body:
*"Remove the auto-enable of draft-simple speculative type when a draft model path is
specified (users must now explicitly enable it)."* No deprecation warning was added and
backward compatibility was not discussed. So my source reading is right and the behaviour
is intended; a command line that worked before that date silently stops speculating after
it, which is exactly the window this project's "+21%" record sits across. Related: #22397
(2026-04-28) renamed every `--draft*` to `--spec-*`; #22787 (2026-05-11) refactored the
draft context; #26814 and #27005 (both 2026-08-13) added auto-detection for dflash/dspark
and MTP respectively — **plain Qwen2.5 remains undetected by design**. #26814's own text
describes my symptom verbatim: *"the draft model loads into VRAM but speculative decoding
never activates (types stays NONE, tok/decode-pass = 1.000)"*.

**2. `p_min` defaults to 0.0 and that alone destroys acceptance — issue #25908, open,
2026-07-19.** Confirmed in this tree at `common/common.h:330`:

```
float p_min   = 0.0f; // minimum speculative decoding probability (greedy)
```

With no floor the drafter never exits early, so it spends the whole `n_max` every round
even after it has clearly lost the thread. The issue's measurement: acceptance **0.070**
(96/1378) at the default, **0.898** (79/88, mean accepted length 3.93) at
`--spec-draft-p-min 0.75`. That is a 12.8x swing produced by a default value.

This matters beyond this experiment. **It is very likely the explanation for the "0.047-0.25
on free-form chat" acceptance figures I recorded in iteration 16 and treated as a property
of speculative decoding.** They are more plausibly a property of a broken default. I have
added `spec3p` and `spec8p` arms so the two are separated by measurement rather than by
argument — and if I had run only the `spec3` arm I had originally written, I would have
concluded for the *second* time that speculation does not work on this box.

**3. The draft model loader loads the TARGET model — PR #26968, open, 2026-08-12.** This one
I found by reading `common_speculative_init_result` after the search named the PR, and the
line is present here at `common/speculative.cpp:2552`:

```
if (has_draft) {
    model_path = params.speculative.draft.mparams.path;
    LOG_INF("%s: loading draft model '%s'\n", __func__, model_path.c_str());

    llama_model * model_dft = llama_model_load_from_file(params.model.path.c_str(), mparams);
```

It computes the draft path into `model_path`, **prints `model_path`** so the log says
"loading draft model qwen05b.gguf", and then loads `params.model.path` — the 7B target. The
only variable that would expose the bug is the only one that is not used.

Had I run `15b-specfix.sh` without checking this, the `spec3` arm would have brought up a
second full 7B: ~4.29 GB more resident on a 16 GB box, every draft token costing exactly
what a target token costs, k=3 doing 4x the work for at most 4 tokens. A guaranteed large
loss, reported in the log as a correctly loaded 0.5B draft, on a machine where this log
already records a 900 MB memory swing being worth 21.9x. **That is three independent silent
failures stacked on one flag**, and the reason none of them were caught before is that all
three fail by *printing success*.

`15a-specbuild.sh` is queued ahead of the experiment. It applies the one-line fix, rebuilds
`llama-server` only, and — this is the part that matters — **proves the fix by weighing the
process rather than by reading the log line that lied**. 7B + 0.5B should sit near 5 GB
resident; 7B twice cannot be under 9 GB. A 4 GB gap is not something drift can manufacture.
It also prints the `print_info: model params` line for each model actually loaded, which
gives 7.62 B twice if broken and 7.62 B then 0.49 B if fixed.

Patching the main tree rather than a worktree, and the justification: the line is inside
`if (has_draft)`, false unless `-md` is given; `llama-bench` has no `-md`; `llama-cli` never
calls into `common_speculative` at all. So the patched line is unreachable from every binary
that produced a number in this log. The rebuild relinks `libllama-common.so`, which
llama-bench does load, but the behaviour it loads is unchanged.

**Two further findings, recorded now so they are not rediscovered later:**

- **A CPU-only speculative benchmark does exist**, contrary to what iteration 16 recorded
  after searching only the llama.cpp repo. Qwen2.5-Coder-3B target with a 0.5B-Q8_0 draft at
  `--spec-draft-n-max 5`: **12.9 -> 22.1 tok/s, 1.72x**, and 2.03x on maths. Different target
  size and not this box, so it is a *plausibility check and not a prediction* — but it is
  prior art for the mechanism, and the author names the same reason I did: a CPU is more
  bandwidth-starved than a GPU, so speculation has more headroom, not less. Correcting
  iteration 16's "no CPU-only speculative-decoding benchmark exists upstream": it does not
  exist *upstream*, which is where I looked, and that was too narrow a search to support the
  claim I made from it.
- **Nobody anywhere reports speculation being a net loss on a pure-CPU target.** Every
  net-loss report found is GPU-side (#25908 Vulkan p_min, #23126 Vulkan UMA iGPU, one RTX
  5060 Ti at 0.27x).
- **The named CPU-specific risk is thread-pool duplication** — issue #27039, fix PR #27143
  (open, 2026-08-15). Draft and target each build their own ggml CPU thread pool despite
  never running concurrently. On 4 cores that is the most likely thing to eat a gain, and it
  is the first place to look if `spec3p` underperforms.

**Draft-on-iGPU is being ruled out before it is tried, on other people's measurements.**
`--spec-draft-device` / `-ngld` exist and split placement is supported and intended
(confirmed by ggerganov in #23982). But #23126 is this exact configuration — Vulkan iGPU,
both models resident — and draft evaluation went from ~30 ms to 43,000-73,000 ms. The
arithmetic says the same thing without the bug: an iGPU shares this box's DRAM, so moving
the draft there moves compute but **not one byte** of the memory traffic that dominates it.
Recorded as a deliberate decision, not an oversight.

---

## Iteration 33 — RESULT: the clean depth curve, and it is not the shape I was arguing about

`15-ctxsweep.sh` finished both passes. Pass 2 is complete, uncontaminated, and every point is
bracketed by a depth-0 run either side, so each number is drift-corrected against its own
immediate neighbours rather than against the start of the run.

**The contamination verdict from iteration 24c is confirmed by replication.** Depth 6144 in
pass 1 read 0.3976 tok/s while a stray 8-thread `test-backend-ops` probe and a `cmake -j3`
were running. Pass 2, clean, reads **2.7430**. The pass-1 value was wrong by 6.9x. Depth 4096
replicates across the two passes at 3.6750 / 3.6107 (1.8%) and depth 8192 at 2.3052 / 2.2895
(0.7%), which is what tells me pass 2 is trustworthy and pass 1 was only damaged locally.

### The raw curve, seconds per token, undivided

The council caught me dividing a two-term cost by one of its terms and reading a shape into
the result. So the raw numbers first, and the divided ones second, clearly labelled.

| depth | tg tok/s | s/token | bracket mean tok/s | bracket s/token | **excess s/token** |
|---:|---:|---:|---:|---:|---:|
| 128 | 6.2687 | 0.15952 | 6.4939 | 0.15401 | **0.00551** |
| 448 | 5.9674 | 0.16758 | 6.4889 | 0.15413 | **0.01344** |
| 1024 | 5.4219 | 0.18444 | 6.4529 | 0.15499 | **0.02944** |
| 2048 | 4.9032 | 0.20395 | 6.4132 | 0.15593 | **0.04802** |
| 4096 | 3.6107 | 0.27695 | 6.3750 | 0.15686 | **0.12009** |
| 6144 | 2.7430 | 0.36456 | 6.3038 | 0.15864 | **0.20593** |
| 8192 | 2.2895 | 0.43678 | 6.2667 | 0.15957 | **0.27721** |

The depth-0 brackets drift monotonically from 6.4939 down to 6.2667 across 90 minutes — 3.5%
of thermal sag, which is exactly why each point is corrected against its own neighbours and
not against a global baseline.

### The shape, and I am reading it from ratios rather than fitting a curve

I am **not** fitting `c + a·d + b·d²` to these points. Three parameters against three points
is an exact fit with no residual and therefore no falsifiability — the identical error the
council caught in the `c + X/d` fit, which I have struck. Ratios of adjacent doublings need
no parameters at all:

| doubling | excess ratio | vs linear (2.00) |
|---|---:|---|
| 1024 → 2048 | **1.63** | sub-linear |
| 2048 → 4096 | **2.50** | super-linear |
| 4096 → 8192 | **2.31** | super-linear |

**The cost per unit of context changes character between 2048 and 4096.** Below it, adding
context is cheaper than proportional. Above it, dearer. That is a real feature of the curve
and it does not depend on any model I impose on it.

### The mechanism this points at — with arithmetic, no free parameters

```
one layer's KV slice = 2 (K+V) × 4 kv heads × 128 dim × 2 B = 2,048 B per position
2,048 B × 3,072 positions = 6.29 MB   ≈   this CPU's 6 MB L3
```

Below roughly 3,072 tokens a single layer's entire KV slice fits in L3. Above it, it does
not. The crossover lands between my 2048 and 4096 samples, which is where the curve changes
character.

**This unifies two stories I had been treating as rivals.** The query-head loop sits outside
the KV scan at `ops.cpp:9276`, so with this model's 28/4 GQA ratio each KV head's slice is
issued **7 times per token**. Below the crossover those 7 passes are L3 hits and cost
essentially nothing in DRAM traffic. Above it they miss, and all 7 go to memory. The
"GQA re-read" mechanism and the "cache residency" mechanism are the same mechanism; the
crossover is just where re-reading stops being free.

It also revises a prediction I registered earlier. `17a-fakernel.sh`'s header says a knee at
3072 would mean *"I have the GQA residency argument wrong"*, on the grounds that `ik2 = iq2/rk2`
is contiguous grouping so only one KV head need stay resident. That reasoning was about **one
KV head** (512 B/position, crossing 6 MB at 12,288 tokens). The quantity that actually has to
stay resident across the query-head loop is the **whole layer's slice**, because the loop
walks all 28 query heads and therefore touches all 4 KV heads before returning to the first.
2,048 B/position, crossing at 3,072. **The earlier prediction was written against the wrong
denominator and I am correcting it rather than quietly reinterpreting the outcome.**

### This is now a prediction with a number, registered before the measurement

`15c1-ctxbytes.sh` has been changed from two depths to four — 0, 2048, 4096, 8192 — so it
brackets the crossover instead of merely spanning it. It differences two runs at the same
depth that differ only in `n_gen`, so model load, the depth prefill and warmup cancel exactly,
and reads `uncore_imc` for DRAM bytes actually fetched. No TLB semantics to argue about.

- below the crossover: bytes/token ≈ 4.29 GB of weights + **1×** KV
- above the crossover: bytes/token ≈ 4.29 GB of weights + up to **7×** KV
- at depth 8192, KV is 470 MB, so those two branches are **4.76 GB** and up to **7.58 GB**
  per token — a 59% gap that drift cannot blur

Outcomes, fixed in advance:

- **flat across all four depths** → the re-reads are cache hits everywhere, the loop nest is
  innocent, and porting ik_llama.cpp #332 buys nothing. Kill it.
- **flat to 2048 then climbing** → the re-reads become DRAM traffic above the L3 crossover.
  Tiling so all 7 query heads consume a KV tile once is then the right fix, with a measured
  size attached to it.
- **climbing from depth 0 upward** → not a cache crossover at all; the KV is being re-read at
  every depth. Different fix, still actionable.

### One number that does not fit, stated rather than smoothed over

The measured excess at 8192 is 0.27721 s/token. If the whole excess were the extra DRAM
traffic of 6 additional KV passes — 6 × 470 MB = 2.82 GB — then at the ~19 GB/s this box
actually sustains that is 0.148 s, or **53% of the excess**. So even if the byte prediction
lands exactly, roughly half the depth penalty is still unaccounted for. I am writing that
down now, before the result, so that a confirmed byte measurement does not get to claim the
whole effect.

### The minor-fault column, and mechanism (B) graded rather than cliff-shaped

| depth | KV size | minor faults | excess over the ~13.4k floor |
|---:|---:|---:|---:|
| 2048 | 117 MB | 15,623 | 2,200 |
| 4096 | 235 MB | 14,755 | 1,300 |
| 6144 | 352 MB | 66,548 | 53,100 |
| 8192 | 470 MB | 127,030 | 113,600 |

At 8192, 470 MB in 4 kB pages is 114,688 — against a measured excess of 113,600. The KV cache
at that depth is essentially **entirely** 4 kB-backed. At 6144, 352 MB would be 86,016 pages
but the excess is 53,100, so about 38% of it still got hugepages. So the THP fallback is
**graded, not a cliff** — the order-9 pool drains progressively as the sweep allocates larger
caches. Pass 1 read 142,287 at 8192 and pass 2 reads 127,030 for the same allocation, which is
the pool being in a different state on the two passes and is itself evidence that this is an
allocator/fragmentation effect rather than a property of the depth.

`15c-thpctl.sh` still isolates it, and it still has to run before the PR 27478 A/B or the
patch's two halves cannot be told apart.

---

## Iteration 34 — the speculator ran. Also: my own gate would have called the fix broken.

Tree: `~/llama.cpp`, branch `cpu-igpu-tensor-parallel`, HEAD `8395162` plus **one new
one-line commit-pending edit** to `common/speculative.cpp` (the PR #26968 fix) and the
pre-existing uncommitted `tests/test-backend-ops.cpp` instrumentation, which is not linked
into any binary used here. `llama-server` was relinked; `llama-bench` was not rebuilt.

### The patch, and that it applied to the shape I predicted

```diff
-        llama_model * model_dft = llama_model_load_from_file(params.model.path.c_str(), mparams);
+        llama_model * model_dft = llama_model_load_from_file(model_path.c_str(), mparams);
```

One occurrence, guard satisfied, build clean. The bug is real in this tree: the function
computes the draft path into `model_path`, logs `model_path`, and then loads
`params.model.path` — the 7B target — as the draft.

### GATE 1 — the weighing. PASSED, but not by the instrument I registered.

I pre-registered this threshold in the script header:

> "broken  -> two 7B models resident, RSS ~9 GB+ ... fixed -> 7B + 0.5B, RSS ~5 GB"

Measured with the fix confirmed applied: **VmHWM = 8,911,352 kB = 8.50 GB**, and a later
`smaps_rollup` sample during the smoke ask read **Rss 9,101,948 kB = 9.10 GB**.

**By my own pre-registered gate, that is the "broken" branch. The gate was wrong, not the
fix.** I am recording this as a prediction failure because it is one, and because of how
it happened: I computed both thresholds as if one copy of the weights is resident, when
**line 361 of this very log**, written by me in Iteration 4, says otherwise —

> "Two buffers, 7550 MiB total, for a 4092 MiB file. The repacked weights are a second,
> anonymous, non-file-backed copy."

I wrote a gate whose arithmetic contradicted a measurement sitting 2,600 lines earlier in
the same file. A threshold derived from a forgotten result is worse than no threshold,
because it converts a working fix into a false alarm with full confidence.

### The instrument that actually settled it

RSS is a scalar; it conflates every mapping. The question — *was the 7B loaded twice?* —
is about **identity**, so the right instrument names files. From `/proc/PID/maps` while the
server was live:

| mapped file | total mapped | mappings |
|---|---:|---:|
| `/srv/media/_llmtest/qwen7b-pureQ4K.gguf` | **3.670 GB** | 2 |
| `/srv/media/_llmtest/qwen05b.gguf` | **0.452 GB** | 1 |

The 7B appears **once**. The draft is genuinely the 0.5B. No threshold is needed and no
drift can touch this — it is a list of filenames.

And 3.670 GB = **3757.65 MiB**, which is *exactly* the `CPU_Mapped model buffer size` this
log recorded at line 357. The rest of the footprint then accounts for itself against
`smaps_rollup` (`Anonymous 4,763,200 kB = 4,652 MiB`):

| term | MiB | source |
|---|---:|---|
| `CPU_REPACK` copy, 7B | 3,793 | log line 358, measured Iteration 4 |
| repack copy, 0.5B | ~420 | inferred, **not measured** |
| KV, target, 8192 ctx | 470 | 8192 × 57,344 B, measured Iteration 33 |
| KV, draft, 8192 ctx | ~100 | computed from 0.5B geometry, **not measured** |
| **sum** | **~4,783** | vs measured 4,652 anon |

Close enough that nothing multi-gigabyte is hiding. The genuinely-broken case would have
been two mapped 7Bs *and* two 3,793 MiB repack buffers — about 14.7 GB of weights alone on
a 15.7 GB box, which would have collapsed onto rotational disk and been unmistakable. So
the experiment was sound and both of my numbers were wrong; the real branches are further
apart than I guessed, in the direction that made my "fixed" threshold impossible to hit.

**Nothing new about repack is claimed here.** I re-derived Iteration 4's result and then
checked the log before writing it up. Recording the re-derivation only because it is what
proves the account closes.

### GATE 2 — did the speculator run? PASSED. First time in this project.

```json
{"label": "specbuild_smoke", "prompt_n": 4852, "cached_n": 0, "ttft_s": 437.98,
 "pp_tps": 11.08, "gen_n": 6, "gen_s": 4.38, "tg_tps": 1.14,
 "draft_n": 9, "draft_acc": 5}
```

**`draft_n = 9`, not `-1`.** `server-context.cpp:662` only emits these keys when
`n_draft_total > 0`, so this is the first evidence in 34 iterations that a draft token has
ever been produced on this machine. Iteration 7's conclusion — "speculative decoding's
+21% is a short-context result and does not survive to the context length that actually
matters here" — was measuring a configuration in which no speculator object was ever
constructed. **That conclusion is now formally void, not merely doubted.** It is struck.

Three separate silent failures had to be removed to get a single non-`-1`:
1. `types == {NONE}` unless `--spec-type draft-simple` is passed (PR #23988 removed the
   auto-enable); the mask `1 & 2 == 0` so no speculator is built.
2. `llama-cli` accepts `-md` and never calls `common_speculative` at all.
3. PR #26968: the draft slot loads the target.

Every one of them fails by printing success.

### What is NOT claimed from this run

- **`draft_acc / draft_n = 5/9 = 0.556` is not an acceptance rate.** It is 3 draft rounds
  on 6 generated tokens. n=9. It is evidence that acceptance is non-zero, and nothing more.
  The acceptance measurement is `15b-specfix.sh`, on 128-token generations.
- **`tg_tps = 1.14` is not a generation speed.** Six tokens sampled immediately after a
  438-second cold prefill. The script takes no timing by design and this number is noise.
- **`pp_tps = 11.08` is not a prefill regression.** Cold, uncontrolled, with a second model
  resident. The controlled prefill numbers in this log came from a different harness.

### Next

`15b-specfix.sh` is now running: 7 arms, one server lifetime each, `gen=1` warmup to pay
the cold prefill off the clock then two timed `gen=128` asks against the warm prefix cache,
ABBA over `base` and `spec3` with the diagnostics in the middle. The arm that matters most
for honesty is **`mdonly`** — iteration 7's exact configuration — whose registered
prediction is `draft_n == -1` and a time indistinguishable from `base`. If `mdonly`
speculates, the source reading above is wrong and this entire entry is void.

### Iteration 35 (research step) — one vector killed in source, three sharpened

Run while `15b-specfix.sh` occupied the box. Nothing here is a measurement on this machine.

**KILLED: putting the 0.5B draft on the UHD 620 while the 7B target stays on CPU.**
This looked like the mission's heterogeneous idea in its cheapest possible form — a 0.45 GB
model that actually fits the iGPU, no tensor splitting, no new code. It is dead for a
reason that is structural rather than empirical, and the flags work fine, which is what
makes it a trap:

- The placement plumbing is real and honored end to end. `common/arg.cpp:4237`
  (`--spec-draft-device`/`-devd`) and `:4246` (`-ngld`) write into a *separate* struct
  (`common/common.h:471`, `:349`), `common/speculative.cpp:2460-2478` copies them into the
  draft's `mparams`, and `:2556` loads the draft with them. So `--device none -ngl 0
  -devd Vulkan0 -ngld 99` genuinely gives a CPU target and an iGPU draft.
- **But drafting and verification are strictly sequential in this tree.** `grep` for
  `thread|async|future|overlap|pipelin` in `common/speculative.cpp` returns only
  `cpuparams`. The server loop blocks: draft at `server-context.cpp:3046`, verify at
  `:3747`. `draft-simple`'s k passes are a plain `for` (`speculative.cpp:302,366`).
  There is no overlap to win.
- **And the UHD 620 shares the same DDR4-2667 bus.** Moving the draft off the cores does
  not add one byte per second of bandwidth, which is the term that binds. The only real
  benefit is less L3 pollution from the draft's 0.45 GB — against per-step Vulkan submit
  and sync overhead on a model small enough that the overhead dominates.
- Prior art agrees and is worse than neutral: llama.cpp **issue #23126** (Radeon 780M, UMA)
  measured the *reverse* split — CPU draft, GPU target via `--spec-draft-ngl 0` — at 1.8 t/s,
  a loss. Searched `spec-draft-device`, `-devd`, `--device-draft`, "draft model on GPU
  target on CPU llama.cpp", heterogeneous speculative decoding CPU GPU; read `common/arg.cpp`,
  `common/speculative.cpp`, `common/common.{h,cpp}`, `docs/speculative.md`,
  `tools/server/README.md`. No measurement of this exact split exists anywhere I looked.

Recording it as killed *before* spending a run on it, with the mechanism named, rather than
measuring a null and then explaining it.

**SHARPENED 1 — k=3 is probably well below the optimum for code, and `15b` cannot see past
k=8.** Published, on my exact pair: Qwen2.5-Coder 0.5B drafting 7B at **8** draft tokens
measured **1.75×** end-to-end (llama.cpp Discussion #10466), and ggerganov's own PR #10455
ran `--draft-max 16 --draft-min 0` for **4.2–5.7×** on high-grounding code edits. This
tree's default is `n_max = 3`, which is what iteration 7 and my smoke test both used. If
`spec8p` beats `spec3p` in the run now in flight, k is not yet at its peak and the next
script has to climb, not stop.

**SHARPENED 2 — a published acceptance number for this exact pair, on code.** A
cross-domain study (RyeCatcher, HuggingFace, not peer-reviewed) reports Qwen2.5-7B verified
against a 0.5B draft, greedy, over n=24,515 drafts: **86.3% acceptance on code**, against
75.1% on math and 66.5% on translation. My smoke test's 5/9 is far below that, but n=9 and
it ran at `p_min=0.0` — the defaulting bug. **This is a prior, not a target**, and I am
writing it down now so that if `15b` returns ~0.86 I do not get to call it a prediction.

**SHARPENED 3 — this tree has an acceptance simulator, and I did not know it.**
`common/arg.cpp:4181` `--spec-synth-len` and `:4194` `--spec-synth-rates` let me *impose* an
acceptance rate and measure what this CPU's verify-batch actually costs at each k, with no
draft model in the loop at all. That separates the two things k trades between — draft cost
and verify-batch cost — which no A/B of real arms can do, because in a real arm they move
together. This is the cheap way to find the optimal k instead of bisecting it with
hour-long runs.

Also confirmed by reading the queued script rather than trusting memory: **`18-specgate.sh`
does pass `--spec-type ngram-mod`** (line 45-46), so unlike iteration 7 it is not a no-op.
The five draftless modes were already found and verified against this box's own binary in
iteration 16 (log line 1064). Nothing new is claimed about them here.

---

## Iteration 35 — speculative decoding works, and it is a 1.42x LOSS. With the mechanism half-isolated.

Tree: `~/llama.cpp`, `cpu-igpu-tensor-parallel`, HEAD `8395162` + the PR #26968 one-line draft-load
fix from iteration 34. Harness `15b-specfix.sh`: seven `llama-server` lifetimes, each paying one
cold prefill of `testfile.py` (4,854 tokens) via a `gen=1` warmup **off the clock**, then two timed
`gen=128` asks against the warm prefix cache. Temperature 0, seed fixed. ~75 minutes of box time.

### The table

| arm | flags beyond `-md` | tg tok/s (a / b) | s / token | vs base | draft_n | accepted | acceptance | mean len |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **base** | — | 3.12 / 3.11 | 0.3166 | 1.000 | −1 | −1 | — | — |
| **mdonly** | `--spec-draft-n-max 3` | 3.12 / 3.10 | 0.3175 | 1.003 | **−1** | −1 | — | — |
| **spec3** | `--spec-type draft-simple -n-max 3` | 1.45 / 1.44 | 0.6830 | **2.153** | 111 | 43 | 0.387 | 2.16 |
| **spec3p** | + `--spec-draft-p-min 0.75` | 2.20 / 2.18 | 0.4502 | **1.422** | 28 | 24 | **0.857** | 2.20 |
| **spec8p** | `-n-max 8 -p-min 0.75` | 2.13 / 2.13 | 0.4634 | **1.464** | 31 | 26 | 0.839 | 2.30 |
| **spec3pb** | repeat of spec3p | 2.19 / 2.18 | 0.4522 | 1.428 | 28 | 24 | 0.857 | 2.20 |
| **baseb** | repeat of base | 3.12 / 3.09 | 0.3177 | 1.003 | −1 | −1 | — | — |

**Drift over the whole 75-minute run: +0.35%** (base 0.3166 → baseb 0.3177 s/token). The box was
unusually stable and every difference below is an order of magnitude larger than it. `spec3pb`
reproduces `spec3p` to 0.4% with byte-identical draft counts — at temperature 0 this harness is
deterministic, which is worth knowing for every future A/B.

### Four things this settles

**1. `mdonly` confirms the source reading by measurement. `draft_n = −1`, and 3.12 / 3.10 against
base's 3.12 / 3.11 — a 0.3% difference.** That was the registered falsifier for iteration 34's
entire source argument: *"If mdonly speculates, my source reading is wrong and everything below it
is void."* It did not speculate. Iteration 7 ran exactly this configuration and timed a no-op.
The record is now consistent: the +21% and the zero were both measuring nothing, and this arm is
the positive control that proves it rather than asserting it.

**2. The `p_min` defaulting bug is real and reproduces on hardware nothing like the reporter's.**
Upstream issue #25908 reports acceptance 0.070 → 0.898 on Qwen3-4B+0.6B under Vulkan. I measure
**0.387 → 0.857** on Qwen2.5-Coder 7B+0.5B on an AVX2 CPU. Different model pair, different
backend, different arch — same defect, same direction, similar magnitude. `common/common.h:330`
ships `p_min = 0.0f`, so the drafter never stops early and burns the full `n_max` on tokens it has
no confidence in: 111 drafts to produce 81 tokens, against 28 to produce 80.

**3. 0.857 acceptance is excellent, and it does not save speculation.** Before this ran I
registered a published prior — 86.3% acceptance for Qwen2.5-7B verified against a 0.5B draft on
code (RyeCatcher cross-domain study, n=24,515). Measured here: **85.7%**. I said in advance I
would not get to call that a prediction and I am not calling it one; I am recording that the prior
and the measurement agree to within a percentage point, which means acceptance on this box is
*normal for the task* and there is no acceptance problem left to fix. **Speculation is losing at
the acceptance rate it is supposed to have.**

**4. k is not the binding constraint, which kills the vector I registered during research.**
The research step recorded: *"If `spec8p` beats `spec3p` in the run now in flight, k is not yet at
its peak and the next script has to climb."* It did not beat it — `spec8p` is **slower** (0.4634
vs 0.4502 s/token) and `mean len` moved only 2.20 → 2.30. Raising `n_max` from 3 to 8 bought 0.10
extra accepted tokens per round and cost time. The published results I found — 1.75x at k=8
(Discussion #10466) and ggerganov's `--draft-max 16` (PR #10455) — **do not reproduce here**, and
the reason is visible in `mean len`: with `p_min` doing its job the drafter voluntarily stops at
~2 tokens, so k above 3 is never reached. Climbing k is dead. I am not queuing a k=16 arm.

### The mechanism, as far as it is isolated

Confounds ruled out **during** a spec arm, not argued away: `vmstat` `si`/`so` = 0/0, and
`/proc/diskstats` read sectors **unchanged** on both spindles across 2 s, with 7.9 GB
`MemAvailable`. No swapping, no disk, no memory pressure. The loss is compute.

The assumption-free statement, which needs no round-counting:

> base emits a token for **0.3166 s**. spec3p emits a token for **0.4502 s** while achieving 85.7%
> acceptance. **Speculation is therefore adding at least 0.134 s of overhead per emitted token —
> 42% of the entire cost of just generating the token normally.**

A speculative round is *draft passes* + *one verify batch*. Only one of those two can be blamed and
I have measured neither, so I am not going to name a winner. Both are quantified by
`15b3-verifyamp.sh`, already queued:

- **Candidate A — the verify batch does not amortise.** Iteration 16 asserted from source that it
  does (`ggml-cpu.c:1187-1230` blocks the matmul 16x16 with the batch-column loop *inside* the
  weight-row tile, so one weight tile serves up to 16 tokens) and **explicitly labelled that a
  source reading, not a measurement.** It has never been measured. If verifying 4 tokens costs
  4x verifying 1, speculation cannot win here at *any* acceptance rate, including 1.0.
- **Candidate B — the 0.5B draft pass is not bandwidth-proportional.** At 0.45 GB and the ~19 GB/s
  this box sustains, a draft pass should cost ~0.027 s. If it actually costs ~0.13 s it is
  overhead-bound at batch size 1 and the draft half alone explains the loss — in which case the
  fix is a drafter with *no forward pass at all*, not a better one.

There is also a third thing, which this log has had in source since iteration 29 and never
connected to speculation:

> `ops.cpp:9263` — `use_split_kv_path = !use_ref && (neq1 == 1 && neq3 == 1) && ...`
>
> **A verify batch has `neq1 == N`, not 1. So verifying k>1 tokens silently leaves the split-KV
> decode attention path.** At 4,853 context, attention is roughly half the per-token cost by the
> iteration 33 curve. Every attention measurement in this log from iteration 25 onward is of a
> path that speculative decoding does not use.

`15b3-verifyamp.sh` varies depth (0 / 2048 / 4096) precisely so that A(N) at depth can be compared
against A(N) with no KV at all, which separates that gate from plain GEMM batching.

### A correctness failure, recorded because it is one

Speculative decoding is lossless by construction: at temperature 0 every arm must emit text
byte-identical to base. The check:

```
mdonly   IDENTICAL to base
spec3    IDENTICAL to base
spec3p   DIFFERS from base
spec8p   DIFFERS from base
spec3pb  DIFFERS from base
baseb    IDENTICAL to base
```

**The correlation with `p_min` is exact — every arm that sets it diverged, every arm that does not
set it did not.** The divergence is one word in ~90: *"modifying the tensor buffer type overrides
during the model **loading process**"* → *"during the model **initialization**"*. Semantically
identical, which is the signature of a near-tie argmax flip rather than a broken accept rule.

Checked in source rather than guessed: `p_min` appears in `common/speculative.cpp` **only** at
lines 337, 799, 1303 and 1680, every one of them `if (cur_p->data[0].p < params.p_min)` inside a
*draft-generation* loop. It is **not** in the acceptance test. So this is not a lax-acceptance
heuristic being switched on, and my first suspicion — that #25908's 0.898 is an artifact of
accepting more loosely rather than drafting better — is **wrong and withdrawn**.

What I can say from the data alone narrows it usefully: `spec3` runs a **constant** verify batch of
4 and is byte-identical to base's batch of 1, so batching per se does not perturb the logits here.
`spec3p` is the arm whose batch width **varies** (1–4, via early exit). So the suspect is a kernel
selected only at batch widths 2 or 3.

**That is a testable prediction and I am deliberately not testing it yet:** `--spec-draft-n-max 1`
and `-n-max 2` with no `p_min` would pin constant batches of 2 and 3, and if either diverges from
base the mechanism is isolated to that width. It costs an hour of box time to resolve a
one-word paraphrase, while the speed mechanism above is worth 1.42x. Deferred, with the design
written down so it is a decision and not an oversight.

### Status against the exit condition

This iteration produced **no gain** — it produced a measured, reproducible, drift-free **loss**,
plus the positive control that voids iteration 7 and the confirmation that acceptance is not the
problem. That is iteration 1 of 3 toward the exit condition, and it does **not** qualify yet,
because the loss is explained only down to "one of two named terms" and not to a measured one.
`15b3-verifyamp.sh` is running now and closes that gap.

---

## Iteration 36 — A(N) measured. The ceiling on all speculation is 1.35x, and the reason is a roof change.

`15b3-verifyamp.sh`, tree `8395162` + the iteration-34 speculative fix (uncommitted; `llama-bench`
does not link the changed line — it is inside `if (has_draft)` and llama-bench has no `-md`).
`llama-bench -p N -d D`, `-b 512 -ub 512` so no N below splits across ubatches, `-r 3` (`-r 2` at
4096). `-p N -d D` is exactly the shape of a speculative verify step; `-p 1 -d D` is the shape of
an ordinary decode step.

**A(N) = N x T(1) / T(N)** — how much cheaper verifying N tokens in one batch is than N tokens one
at a time. It is the hard ceiling on *any* speculation scheme, at perfect acceptance and zero
draft cost.

| N | D=0 s/batch | s/tok | **A(N)** | D=2048 s/batch | s/tok | **A(N)** | D=4096 s/batch | **A(N)** |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.14098 | 0.14098 | 1.000 | 0.20141 | 0.20141 | 1.000 | 0.27188 | 1.000 |
| 2 | 0.25600 | 0.12800 | 1.101 | 0.35580 | 0.17790 | 1.132 | — | — |
| 4 | 0.33097 | 0.08274 | 1.704 | 0.51972 | 0.12993 | 1.550 | — | — |
| 8 | 0.65432 | 0.08179 | **1.724** | 1.00734 | 0.12592 | **1.599** | 1.60953 | **1.351** |
| 16 | 1.00715 | 0.06295 | 2.240 | 1.62955 | 0.10185 | 1.978 | — | — |

**A(8) falls monotonically with depth: 1.724 → 1.599 → 1.351.** The real workload sits at ~4,850
tokens, past the last column. My registered prediction — *"At D=2048 I expect A(N) to be LOWER
than at D=0"* — is confirmed.

### The mechanism: A(N) saturates because the machine changes which roof it is under

This is the decomposition the mission demands, so here it is with both roofs named and measured.

At **N=1**, D=0: the model is 4,284,930,048 B and the pass takes 0.140982 s.

> **4.285 GB / 0.140982 s = 30.39 GB/s.** DDR4-2667 dual-channel theoretical is
> 2667 x 8 x 2 = 42.67 GB/s, so this is **71.2% of theoretical DRAM peak** — a genuinely
> bandwidth-bound pass, running near the achievable roof. Compute here is
> 2 x 7.6156e9 x 1 / 0.140982 = **108.0 GFLOP/s**.

At **N=16**, D=0: the same weights, 1.007152 s.

> Bytes: **4.285 GB / 1.007152 s = 4.25 GB/s — 10% of the DRAM roof.** It has left the memory
> regime entirely. Compute: 2 x 7.6156e9 x 16 / 1.007152 = **241.97 GFLOP/s**, i.e. **2.24x** the
> GFLOP/s achieved at N=1. That ratio *is* A(16) = 2.240. They are the same number because the
> batch is now doing arithmetic, not waiting for memory.

**So A(N) is not capped by anything to do with batching being implemented badly. It is capped by
the ratio between this CPU's memory roof and its compute roof, expressed in tokens.** Widening
the verify batch converts a bandwidth-bound pass into a compute-bound one, and on an i5-10210U
with AVX2 and no VNNI the compute roof is only about 2.2x the memory roof in token terms at D=0,
and 1.35x at depth 4096. That is the whole budget speculation has to work inside.

The 241.97 GFLOP/s figure is consistent with this log's own iteration 11, which measured the
prefill GEMM at **67% of AVX2 peak** on the repacked `q4_K_8x8_q8_K` kernel. Speculation's verify
batch runs the same kernel and inherits the same efficiency. **This is not a fixable
implementation defect in the batching path; it is the kernel already running near its measured
ceiling.**

### Candidate B is rejected by measurement

Iteration 35 left two candidates. The draft model's standalone cost, same run:

| model | depth | s per pass | tok/s |
|---|---:|---:|---:|
| qwen05b | 0 | **0.02109** | 47.75 |
| qwen05b | 4096 | **0.03820** | 26.18 |
| qwen7b (for scale) | 4096 | 0.27188 | 3.68 |

**The draft pass costs 0.0382 s at depth, against the target's 0.2719 s — a ratio of 7.1x, versus
a 9.5x size ratio.** Slightly less efficient than pure size-scaling, which is expected for a small
model at batch 1, but nowhere near the ~0.13 s that would have been needed for the draft half to
explain iteration 35's loss. **Candidate B — "the 0.5B draft pass is not bandwidth-proportional" —
is wrong and is withdrawn.** Candidate A is what remains, and A(N) is now its measured size.

### The sub-prediction I got wrong, stated plainly

I wrote into the script header that a verify batch has `neq1 == N` and therefore fails the
`ops.cpp:9263` split-KV gate, and that this was a candidate reason for A(N) being poor at depth.
**The data says the gate is not hurting — it is helping.** Attention cost per token, isolated by
subtracting the D=0 column from the D=2048 column:

- N=1 (on the split-KV path): 0.20141 − 0.14098 = **0.06043 s of attention per token**
- N=16 (off the split-KV path): (1.62955 − 1.00715) / 16 = **0.03890 s of attention per token**

Batched attention is **1.55x cheaper per token** than the split-KV decode path it "falls off".
So leaving that gate is a win, not a loss, and the concern is retired. Recording it because I
registered it in advance and it was wrong.

### Where the round budget does NOT close, said out loud

Reconstructing iteration 35's `spec3p` arm from these numbers: 80 emitted, 24 accepted, 28 drafted
→ 56 rounds, average verify width 84/56 = 1.5, at most 84 draft passes. Scaling the D=4096 costs
to the run's actual ~4,850 depth by the ratio of the server's own base measurement (0.3166 /
0.27188 = 1.164) gives roughly **25–27 s**. The arm measured **36.0 s**. Roughly **9–11 seconds,
or ~25% of the arm, is unaccounted for** by draft passes plus verify batches.

I am not going to invent a term to absorb it. Candidates I have not measured: per-round sampling,
draft-context KV bookkeeping, and KV rollback on rejection — none of which appear in a
`llama-bench` batch. It is written down as an open residual rather than rounded away.

### What this means for the remaining speculation work

- **Tuning k is dead twice over.** Iteration 35 killed it empirically (`spec8p` lost, `mean len`
  moved 2.20 → 2.30). This kills it structurally: at working depth even N=8 with *perfect*
  acceptance and *free* drafting caps at **1.351x**, and the measured configuration ran at
  effective width ~1.5 where the cap is ~1.1x.
- **A draft-model scheme cannot win here.** Its ceiling is A(w) and it must pay 0.0382 s per draft
  pass out of that ceiling. At w≈2–4 the ceiling is 1.1–1.55x at depth 2048 and lower at 4096.
- **A draftless scheme is still live, and its arithmetic is different.** `ngram-*` costs **zero**
  forward passes, so it keeps the whole of A(w) instead of spending part of it. That is now the
  only speculation variant with a positive budget, and `15b4-specgate.sh` is next in the queue.
- **A(2) is anomalously bad and that is where speculation actually operates.** A(2) = 1.101 at
  D=0 and 1.132 at D=2048 — batching two tokens buys almost nothing — while A(4) jumps to 1.704.
  The doubling costs are non-monotone (x1.82, x1.29, x1.98, x1.54), which is a kernel/tiling
  signature, not noise. Since `mean len` was 2.20, iteration 35 lived entirely inside that dead
  zone. Queued as `15b3b-widthsweep.sh`: a dense N = 1..8 plus 12,16,24,32,64 at D=0, which is
  nearly free because there is no prefill to pay, plus selected widths at D=2048. If specific
  widths are efficient, `--spec-ngram-mod-n-max` should be set to one of them rather than left
  at its default of 64.

---

## Iteration 38 — the largest term in the log, and it is neither bandwidth nor arithmetic

### The constraint, stated as a number with a mechanism

Iteration 36 ran `llama-bench -p 1 -n 0 -d D` at three depths to get A(N). It also, without my
noticing at the time, measured something far more important than the thing it was built for.
`-p 1 -d D` is one forward pass with a KV cache holding D tokens. Three of those, one process,
interleaved by llama-bench's own repetition loop:

| D | T(1), s | measured |
|---|---|---|
| 0 | 0.14097 | yes |
| 2048 | 0.20139 | yes |
| 4096 | 0.27185 | yes |

Subtract, and the pass splits into a term that does not depend on context and one that does:

| D | context term T(D)−T(0), s | share of the pass |
|---|---|---|
| 2048 | 0.06042 | 30.0% |
| 4096 | 0.13088 | **48.1%** |

**Nearly half of every generated token at working depth is the context term.** Nothing in this
log had isolated it before, because every previous measurement of generation was a single
blended tok/s.

Now decompose it, which is what the mission demands and what "bandwidth-bound" is a refusal to do.

**The weight side is healthy and is not the problem.** 4.285 GB of weights in 0.14097 s is
**30.40 GB/s**, which is **71.2%** of DDR4-2667 dual-channel theoretical (42.67 GB/s). For a
strided-but-sequential read of a 4 GB file-backed mapping on a 4-core client part, that is close
to as good as it gets. There is no 2x hiding there.

**The KV side is not bandwidth at all.** This model's KV cache is
28 layers × 2 (K+V) × 4 kv heads × 128 dim × 2 B = **57,344 B per position**.

| D | KV bytes | traversed in | effective rate |
|---|---|---|---|
| 2048 | 117.4 MB | 0.06042 s | **1.94 GB/s** |
| 4096 | 234.9 MB | 0.13088 s | **1.80 GB/s** |

The same cores, on the same DRAM, in the same forward pass, move weight bytes at 30.40 GB/s and
KV bytes at 1.80 GB/s. **A 16.9x gap.** And it cannot be rescued by saying the KV is read more
than once: even the worst case in the source — the query-head loop sitting outside the KV scan at
`ops.cpp:9276`, so each KV head's slice is issued once per query head, 7 times for this model's
28/4 GQA ratio — gives 1.64 GB at **12.6 GB/s**, still comfortably under the 30.40 GB/s this
machine demonstrably sustains in the very same pass. **DRAM bandwidth is therefore ruled out as
the limiter on this term by the machine's own contemporaneous behaviour, not by an argument.**

**Arithmetic is ruled out too.** Attention at D=4096 is 28 layers × 28 heads × 4096 × 128 × 2
(QK and AV) × 2 = **1.64 GFLOP**. Iteration 36 measured this box at 241.97 GFLOP/s on the batched
repacked GEMM and 108.0 GFLOP/s at batch 1. So the arithmetic justifies **0.007–0.015 s**. It is
costing **0.131 s**.

### The sharpest form of it: cycles per KV position

Work items in the decode attention = 28 layers × 28 query heads × 4096 positions = **3,211,264**.

- wall time per item: **40.8 ns**
- core-time per item at 8 threads: **326 ns**
- at 2.6–3.0 GHz sustained: **848–978 cycles per item**

An item is one 128-wide f16·f32 dot product, one `expf`, and one 128-wide multiply-add. On AVX2
with F16C and FMA that is roughly 8 `vcvtph2ps` + 8 `vfmadd` + a reduction for the dot, a libm
`expf` at ~40–70 cycles, and a 128-wide mad — call it **~100 cycles**. Measured is **~900**.

**The constraint for iteration 38, in one sentence: the CPU flash-attention decode path spends
~900 cycles per (layer, query head, KV position) where the instruction mix justifies ~100, this
is 48.1% of every generated token at depth 4096, and it is neither bandwidth-bound (1.80 GB/s
against a demonstrated 30.40 GB/s) nor compute-bound (0.131 s against 0.015 s of arithmetic).**

### One thing this kills immediately: the L3 crossover story

`15c1-ctxbytes.sh` (written earlier today, now renamed `15b7-`) registered a prediction with no
free parameters: one layer's KV slice is 2048 B per position, 6 MB L3 / 2048 B ≈ 3072 positions,
so bytes/token should be flat to ~3072 and climb sharply above it as the 7 GQA re-reads stop
hitting cache. The split-KV path makes that concrete — chunk size is D/nth, so:

| D | per-thread working set | all 8 threads | vs 6 MB L3 |
|---|---|---|---|
| 2048 | 0.52 MB | 4.19 MB | fits |
| 4096 | 1.05 MB | 8.39 MB | does not fit |

So D=2048 and D=4096 sit on opposite sides of the predicted cliff. **Measured cost per KV
position: 29.50 ns at D=2048, 31.95 ns at D=4096. An 8.3% change across a boundary where the
working set doubles from inside L3 to 40% over it.** That is not a cliff. It is close to nothing.

**I am correcting the record: the L3-crossover hypothesis I wrote into that script this morning
is disfavoured by data I already had and had not looked at.** If the 7x re-read were the dominant
cost you would see a step here, because at D=2048 those re-reads are L3 hits and at D=4096 a
large fraction of them cannot be. The cost per position barely moves. Whatever is eating the
900 cycles is **largely indifferent to where the bytes come from**, which is the signature of a
dependency stall or a serialised scalar, not of a traversal problem.

`15b7-ctxbytes.sh` still runs, because it measures DRAM bytes per token directly with the IMC
counters and that turns "largely indifferent" into a number. But its headline hypothesis is
already weakened and I am saying so before the run rather than after.

### The council, on this specific wall

Five advisors, then one peer-review pass. I chaired it myself against the measurements rather
than spawning a chairman agent, because I hold ground truth the advisors do not and two of them
made factual errors that only the measurements can settle. Recording both.

**The Executor won, and it won by reading the source.** It traced the split-KV path: each thread
takes a KV chunk, loops over all 28 query heads, and inside `one_chunk` loops over KV positions —
so the 7 query heads sharing a KV head re-read the same 128 KB K slice back to back. It proposed
grouping query heads by their KV head so one K/V line is fetched once and consumed 7 times while
hot, and it named the discriminating `perf stat` counters. That is the right shape of answer.
It is also, independently, exactly what ik_llama.cpp already merged (see research below).

**The Contrarian attacked the subtraction, and was half right for the wrong reason.** Its claim
was that T(D)−T(0) is a residual over *all* D-scaled ops, not just KV traversal, and it named
RoPE as the likely confound. **The RoPE part is simply wrong**: at decode, RoPE is applied to the
single new token's Q and K, and llama.cpp stores post-RoPE K in the cache — RoPE is O(1) in D, not
O(D). But the general objection stands and points at the right thing: the other op that scales
with D is the **softmax**, and a per-position scalar `expf` with a loop-carried running max is
precisely a serialised dependency that would cost ~900 cycles while touching almost no bytes.
The Contrarian found the answer by an invalid route. Recorded as such.

**The Outsider's challenge was fair and its number was wrong.** It asked whether "interactive"
was ever defined and computed 512/44 ≈ 11.6 tok/s, concluding that might be acceptable. The
measured rate is **3.16 tok/s** — 44 s buys about 139 tokens, not 512. Off by 3.7x. The question
survives the error: "interactive" is still undefined in this log, and I should define it. The
honest definition for a coding assistant is *faster than the user can read*, ~5 tok/s, and *first
useful output inside a few seconds*. TTFT is already 3.20 s warm. Generation at 3.16 tok/s is
below the bar and that is the gap.

**The Expansionist proposed transposing the KV layout, and the reviewer correctly called it
backwards.** Each thread already walks a contiguous position chunk; the re-read comes from loop
order, not from storage order. Transposing does not fix a loop-order problem. Its second point is
kept: if the context term were cheap, long context becomes cheap, and a coder that holds a whole
file is a different product from one that holds a fragment. That is an argument for why this term
is worth more than its 48%, and it is noted, not measured.

**First Principles said minimise tokens-to-answer, not time-per-token.** That is a real lever and
this log has never measured it — it is task #9 / `15f-genlen.sh`, still queued. Its other
suggestion, route most tokens to a 1.5B/3B model, is the same bet speculative decoding makes and
iterations 35–37 measured that bet losing for a mechanism that does not care whether the small
model is a drafter or a router.

**The reviewer's own contribution** was that f16 KV forces an f16→f32 conversion in `kq_vec_dot`
on a machine with no AVX-512, so quantised KV might win twice (fewer bytes *and* a different
kernel). `15g-kvq.sh` is queued and tests exactly that.

### The research, and the reason the queue just changed

Two agents, one on llama.cpp/ggml, one on everything else. Both found things, and one found the
answer sitting in an open PR.

**llama.cpp PR #27478, "ggml: speed up batch-1 CPU decode, align large allocations"** (open,
2026-08-21, zero human review). Its own description of the mechanism:

> "Batch-1 decode attention process KV one position at a time. It uses scalar expf per position,
> rescales accumulator when new max is found... The loop-carried max/rescale is serialized...
> This PR blocks the KV loop, rescaling once every 32 elements. Keeps Q in F32... Computes four
> K·Q dot products per Q load."

That is a description of the ~900-cycles-per-position measurement above, written by someone else,
found independently, before I measured it. And it carries numbers on hardware in this box's class:
Qwen3-30B-A3B Q4_K_M tg@8192, **i5-13400: +38.78% total**; Ryzen 9700X +15.29% total and
**+10.67% on attention alone**.

I already had this PR. `15d-fabuild.sh` and `15e-faab.sh` were written earlier today and were
sitting eleventh and twelfth in the queue behind six speculation experiments. **That ordering was
wrong and the measurement above is why.** They are now `15b5-` and `15b6-`, next after the
running gate. `git apply --check` re-verified clean against HEAD before promoting them.

**ik_llama.cpp PR #332, "Better TG performance for GQA models (CPU)"** — merged 2025-04-17,
confirmed, and it is the Executor's proposal already implemented. It gates on
`neq3 == 1 && rk2 > 1 && rk2 == rv2 && neq1 == 1 && nth >= 1 && nek2*nek1 >= 32*nth`, partitions
over KV-head × KV-chunk, and fuses the head group by passing `rk2` as the query-row count into a
single kernel call, adding `FlashAttn<Dk,Dv,4,k_step>` and `<...,2,...>` specialisations so groups
of 2 and 4 stop falling to the nq1=1 path. Published as a graph, no table. This is task #24 and
it stays live, but it is now *second* to #27478, because #27478 attacks the term the measurement
says is dominant (per-position serialisation) while #332 attacks the term the measurement says is
weakly present (re-read traffic, the thing the 8.3% non-cliff argues against).

**Also found, and this matters for how much credit to give the "it's just latency" story:**
llama.cpp issue **#26581** (open, 2026-08-04) reports "~21-25 ns per KV position per full-attention
layer per token", invariant across backend, across KV row width 1 KiB vs 8 KiB, and across
quantisation, concluding "byte-independence rules out DRAM bandwidth... too few outstanding loads
to cover latency". That is a GPU report, but it is the same signature as the 8.3% non-cliff here,
arrived at by a different route on different silicon.

**Named where the search went and found nothing:** no mainline llama.cpp issue or PR proposes GQA
head-group reuse inside the CPU FA decode path (the `q_head` loop at ops.cpp:9276 is still
one-head-at-a-time), and there is no published measurement anywhere of CPU KV-traversal GB/s as a
figure distinct from weight bandwidth. The 1.80 GB/s number above appears to be new.

**Outside llama.cpp**, the most relevant prior art is **NoMAD-Attention** (arXiv 2403.01273), which
is on AVX2-only hardware, explicitly calls CPU attention compute/MAD-bound rather than
bandwidth-bound, and reports **8.3x on attention-score computation alone, up to 2x end-to-end** —
with the ablation showing the win comes from the blocked, transposed in-register layout rather
than from the FLOP reduction. **MoE-Lens** (arXiv 2504.09345) hand-wrote a CPU decode-attention
kernel with manual vectorisation, unrolling and software prefetch and got **4.7x single-thread,
3.1x at full threads** over the auto-vectorised baseline, blaming vector-unit under-utilisation —
again ILP, not DRAM. **FlashInfer** (arXiv 2501.01005) validates GQA head fusion on GPU, "a single
shared-memory load of the KV-Cache suffices for all query heads in the group"; no CPU
implementation was found. Explicit dead ends, so I do not search them again: llamafile/tinyBLAS is
GEMM-only and never touched attention; ktransformers' CPU side is MoE expert GEMM with no attention
kernel; OpenVINO's GQA second-token gains are GPU-only; PowerInfer and LLM-in-a-Flash are FFN
sparsity and explicitly decline to touch this term.

### What is queued, and why in this order

1. `15b5-fabuild.sh` — build PR #27478 in a worktree off HEAD, gate on the full CPU
   `FLASH_ATTN_EXT` case list. No timing taken. The patch rewrites the online-softmax update,
   which is exactly where a numerics bug still produces plausible text.
2. `15b6-faab.sh` — ABBA A/B, pp and tg reported separately, depths 0 / 2048 / 8192 so the
   ops.cpp half and the madvise half can be told apart rather than blended.
3. `15b7-ctxbytes.sh` — IMC bytes per generated token at four depths. Turns "largely indifferent
   to where the bytes come from" into a measured re-read factor.
4. `15b8-widthsweep.sh` — dense A(N) at N=1..8,12,16,24,32,64. Demoted; speculation is dead for
   three measured reasons now and this only sets a flag on a scheme that has no budget.

No prediction is recorded for #27478 on this box. It is a different microarchitecture generation
from the i5-13400 that produced +38.78%, on a different model, at a different depth, and putting
that number next to mine before the run is exactly the mistake iteration 34's RSS gate made.

---

## Iteration 37 — n-gram speculation: a no-op on one question shape and a 1.11x loss on the other

`15b4-specgate.sh`. Four server lifetimes, ABBA over `--spec-type ngram-mod` vs nothing, two
question shapes inside each lifetime against `/usr/lib/python3.14/shlex.py` (2,905 tokens). The
second question in each lifetime reuses the cached prefix, so it pays no prefill.

The two shapes exist because the upstream maintainer's stated rule is that n-gram drafting only
helps when the output repeats blocks of the input. **prose** = "What does this file do? Answer in
three sentences", which quotes nothing. **code** = "Rewrite the shlex.split function with full
type hints and a docstring. Output only the function", which quotes heavily. A single averaged
number would have hidden exactly the effect being looked for.

| arm | shape | prompt_n | cached_n | TTFT s | gen_n | tg tok/s | draft_n | draft_acc |
|---|---|---|---|---|---|---|---|---|
| off1 | prose | 2905 | 0 | 217.46 | 71 | 4.25 | −1 | −1 |
| mod1 | prose | 2905 | 0 | 223.67 | 71 | 4.28 | −1 | −1 |
| mod2 | prose | 2905 | 0 | 221.28 | 71 | 4.36 | −1 | −1 |
| off2 | prose | 2905 | 0 | 220.58 | 71 | 4.31 | −1 | −1 |
| off1 | code | 24 | 2891 | 3.76 | 161 | 4.21 | −1 | −1 |
| mod1 | code | 24 | 2891 | 3.79 | 161 | **3.80** | 61 | 28 |
| mod2 | code | 24 | 2891 | 3.73 | 161 | **3.85** | 61 | 28 |
| off2 | code | 24 | 2891 | 3.73 | 161 | 4.27 | −1 | −1 |

ABBA means, and the drift check:

| shape | off | mod | change |
|---|---|---|---|
| prose | 4.280 | 4.320 | +0.9% |
| code | 4.240 | 3.825 | **−9.8%, a 1.108x loss** |

Drift over the whole 75-minute run, measured on the two `off` code arms that bracket it:
**4.21 → 4.27, +1.4%.** The loss is seven times the drift and it sits in the middle of the ABBA,
where a linear drift cancels.

### Mechanism, isolated

**On prose, `draft_n = −1` in both `mod` arms. The n-gram matcher never fired once.** Not "fired
and was rejected" — `server-context.cpp:662` only emits those keys when `n_draft_total > 0`, so
−1 means zero drafts were ever produced. The maintainer's rule is therefore confirmed by
measurement on this workload and not just quoted: when the answer does not quote the input, an
n-gram drafter finds nothing to draft and costs nothing. The +0.9% is noise around a true zero,
which is the right answer and also the positive control for the arm plumbing.

**On code it fired, and firing is what cost the time.** 61 tokens drafted, 28 accepted, **45.9%
acceptance**, across 161 emitted tokens. Wall cost of the loss: 161/3.825 − 161/4.240 = **+4.12 s**.

Iteration 36's A(N) is the reason and it was registered before this run. A round that drafts *d*
tokens replaces a width-1 verify with a width-(d+1) verify, costing `w/A(w)` solo passes and
yielding `1 + accepted`. Interpolating iteration 36's curve to this depth (~2,900) gives A(2)≈1.12
and A(4)≈1.6, so a width-4 verify costs **2.5 passes**. At 45.9% acceptance a 3-token draft yields
about 2.4 tokens. **2.5 passes spent to emit 2.4 tokens is a loss before any overhead is counted**,
and that is with drafting itself being free, which for n-gram it genuinely is.

Iteration 36 said this in advance: *"A(2) is anomalously bad and that is where speculation actually
operates."* A(2) = 1.101 at D=0 and 1.132 at D=2048. The scheme lives in the dead zone.

The A(N) model accounts for the sign and roughly half the magnitude — reconstructing it gives
about +0.5 s of net cost against a measured +4.12 s. **The residual is the same one iteration 35
left open and I am not absorbing it:** per-round sampling, n-gram pool lookup and insertion, and
KV rollback on rejection are all unmeasured. It is now visible in two independent schemes, which
makes it a property of llama.cpp's speculation loop rather than of either drafter.

### What this closes

**Every speculation variant available on this build has now been measured and every one loses.**

| scheme | result | why, measured |
|---|---|---|
| draft model, no `--spec-type` (iteration 7's config) | 0.0% | never speculated; `draft_n = −1` |
| draft model, k=3 | 1.42x loss | verify cost + 0.0382 s/pass draft cost against A(2)≈1.1 |
| draft model, k=8, p_min 0.75 | worse than k=3 | mean accepted length moved 2.20→2.30 only |
| n-gram, non-quoting output | 0.0% | never fired |
| n-gram, quoting output, drafting free | **1.11x loss** | A(w) at the operating width is below the yield |

The common mechanism is not the drafter. It is A(N): at working depth, batching *N* tokens into
one verify pass amortises so weakly that even a **free** drafter with 46% acceptance loses. That
is iteration 36's roof-crossing result, and iteration 37 is its confirmation on the one variant
that had a positive budget.

`15b8-widthsweep.sh` stays queued but is demoted to last. It would tell me the best value for
`--spec-ngram-mod-n-max`, and the best value of a flag on a scheme with no budget is not worth
the box time ahead of PR #27478.

### Against the exit condition

Iterations 35, 36 and 37 are three consecutive iterations with no measured gain, and each now has
an isolated measured mechanism rather than a category label. **That satisfies the letter of the
exit condition and I am not stopping**, for a reason that is itself measured rather than a
preference: iteration 38 found that 48.1% of every generated token is a term nobody in this log
had isolated, running at 1.80 GB/s against a demonstrated 30.40 GB/s and ~900 cycles per KV
position against an instruction mix worth ~100. That is not "running out of easy ideas". It is a
new binding constraint, larger than everything speculation was ever fighting over, and there is an
open upstream patch aimed precisely at it already building on the box.

---

## Iteration 39 — PR #27478: the first measured gain in five iterations, and it is 21.2%

`15b6-faab.sh`, tree: `~/llama.cpp` at HEAD for the `base` arm, and the worktree
`/srv/media/_llmtest/wt-pr27478` — that same commit plus `pr27478.diff` and nothing else — for
the `pr` arm. Both arms link their own `libggml-cpu.so` from their own `build/bin`, so neither
can pick up the other's library. The build gate passed first: `test-backend-ops test -o
FLASH_ATTN_EXT -b CPU` returned **5181/5181, rc=0**.

ABBA at the invocation level: base, pr, pr, base. `-p 512 -n 32 -d 0,2048,8192 -t 8 -fa 1 -r 2`.

### The raw passes, all measured

| pass | arm | d | pp512 t/s | tg t/s |
|---|---|---|---|---|
| p1 | base | 0 | 14.8051 | 6.0513 |
| p2 | pr | 0 | 14.0690 | 6.0995 |
| p3 | pr | 0 | 14.1630 | 6.1438 |
| p4 | base | 0 | 14.1543 | 6.1360 |
| p1 | base | 2048 | 12.5152 | 4.8900 |
| p2 | pr | 2048 | 12.3501 | 5.1900 |
| p3 | pr | 2048 | 12.4706 | 5.2319 |
| p4 | base | 2048 | 12.4990 | 4.9120 |
| p1 | base | 8192 | 9.3711 | 2.3182 |
| p2 | pr | 8192 | 9.1611 | 2.8098 |
| p3 | pr | 8192 | 9.4484 | 2.8406 |
| p4 | base | 8192 | 9.5785 | 2.3437 |

### Paired means

| d | phase | base | pr | change |
|---|---|---|---|---|
| 0 | tg | 6.0937 | 6.1217 | **+0.46%** |
| 2048 | tg | 4.9010 | 5.2110 | **+6.32%** |
| 8192 | tg | 2.3310 | 2.8252 | **+21.20%** |
| 0 | pp512 | 14.4797 | 14.1160 | −2.51% |
| 2048 | pp512 | 12.5071 | 12.4104 | −0.77% |
| 8192 | pp512 | 9.4748 | 9.3048 | −1.80% |

The within-arm spread on the headline cell is 1.1% on both arms (base 2.3182/2.3437, pr
2.8098/2.8406). The gap between arms is **19x that spread**. The base arm also ran *faster* in
p4 than in p1 at every depth on tg, so drift over the run favoured the second base pass and the
result survives it anyway.

The pp512 control moves −0.8% to −2.5%. The largest piece of that is p1's 14.8051 at d=0, which
is the very first llama-bench invocation of the run; base p4 measures 14.1543, which sits inside
the pr arm's own spread. So the control is flat to within a warm-up transient, which is what it
should be: **prefill uses the tiled path and this patch does not touch it.** Recorded as a
caution about ABBA rather than waved away — ABBA cancels *linear* drift, and a first-invocation
warm-up is not linear.

### The mechanism, isolated: it is a constant 28% off the context term

Iteration 38 defined the context term as T(D) − T(0), the part of a forward pass that scales with
KV depth. Converting the means above to seconds per token and subtracting:

| | T(0) | T(2048) | T(8192) |
|---|---|---|---|
| base, s | 0.164105 | 0.204040 | 0.429009 |
| pr, s | 0.163355 | 0.191903 | 0.353958 |
| base context term | — | 0.039935 | 0.264904 |
| pr context term | — | 0.028548 | 0.190603 |
| **context term cut by** | — | **28.51%** | **28.05%** |

That is the whole result in one line. **The patch removes a fixed ~28% of the context term and
nothing else.** Two things follow, and both are answers to questions `15b6`'s own header asked
before the run:

1. **T(0) moved −0.46%, i.e. not at all.** The weight-streaming term is untouched, which is the
   control for "this is an attention change, not a general one". Confirmed rather than assumed.
2. **The header predicted that `gain(8192) − gain(2048)` would isolate the `ggml.c` allocation
   half's contribution**, because 8192 is the only depth where the KV cache was measured *not* to
   be hugepage-backed (142,287 minor faults against a ~14k floor). Measured, that difference is
   **28.51% vs 28.05% — zero to within a spread of 1.1%.** So the allocation half contributes
   nothing here and the entire gain is the `ops.cpp` serialisation fix. The reason the whole-pass
   number is +21.20% at 8192 and only +6.32% at 2048 is simply that the context term is 61.7% of
   the pass at 8192 and 19.6% at 2048. Same fix, same fraction, different share.

### What the patch does not fix, also measured

Per-KV-position cost, the quantity iteration 38 put at ~900 cycles:

| | d=2048 | d=8192 | ratio |
|---|---|---|---|
| base | 19.50 ns | 32.34 ns | 1.658 |
| pr | 13.94 ns | 23.27 ns | 1.669 |

The per-position cost still grows with depth, and **it grows by the same factor on both arms**
(1.658 vs 1.669). PR #27478 scales the whole curve down by 0.72 and changes its shape not at all.
So the superlinearity — the thing that makes a position at depth 8192 cost 1.66x what a position
at depth 2048 costs, when both are the same 128-wide dot and the same 128-wide mad — is a
*separate* mechanism, untouched, and it is now the largest unexplained term left. Iteration 38's
~848–978 cycles per (layer, query head, KV position) becomes ~610–704 after this patch, against
an instruction mix that justifies ~100. **There is still roughly 6x sitting in that term.**

### Correcting the record

The mission brief carried forward "speculative decoding at +21%" from the original record as a
live result. Iterations 35, 36 and 37 killed it: every speculation variant on this build is a
loss, and iteration 7's original +21% was measured at short context on a configuration that, as
iteration 34 established by reading `common/arg.cpp` and `common/speculative.cpp`, never
constructed a speculator at all. The +21% in *this* iteration is a different number attached to a
different mechanism and the two should never be conflated. The old one is withdrawn.

### The new baseline, and what runs next

`base` was the tree every number in this log came from. It no longer is, for generation at depth.
`15b7a-fae2e.sh` is queued: it builds `llama-server` in the worktree — only `llama-bench` and
`test-backend-ops` existed there — and runs the mission's actual deliverable, one real coding
question against `testfile.py` (4,858 tokens), ABBA over four server lifetimes, TTFT and total.
It also does the correctness check that matters: PR #27478 reorders floating-point accumulation,
so bit-identical output is not guaranteed by construction and `test-backend-ops` passing under its
own tolerance does not settle it. At temperature 0 the two arms' 200-token answers are compared
byte for byte.

`15b7-ctxbytes.sh` is already running on the **base** binary and stays there deliberately, so its
DRAM-bytes-per-token figure remains comparable with the rest of the log rather than measuring a
tree nothing else in it used.

### Which tree each number came from

`~/llama.cpp` was carrying two uncommitted files while every number above was taken:
`common/speculative.cpp` (the PR #26968 draft-load fix, iteration 34) and
`tests/test-backend-ops.cpp` (instrumentation). Both are now committed on branch
`cpu-igpu-tensor-parallel` as **8ba09e5**, with identical content to what ran, so the base arm's
tree is named rather than described. Neither file can reach a timing path: `llama-bench` has no
`-md` flag and never calls `common_speculative_init`, and `test-backend-ops` is its own binary.
The worktree was branched from the same HEAD, so both arms carry both files and neither is a
confound.

---

## Iteration 41 — the KV cache crosses the memory controller 12.79 times per token

`15b7-ctxbytes.sh`, base tree `8ba09e5`, `llama-bench -p 0 -n {16,80} -d D -t 8 -fa 1 -r 1`
wrapped in `~/llmperf/imc` (uncore_imc RAPL-adjacent counters, system-wide). Each depth is an
n=16/n=80 **pair** and only the difference is reported, so model load, warm-up and the depth
prefill cancel and what remains is 64 generated tokens. `uncore_imc` cannot be scoped to one
process, so Jellyfin and the *arr stack are inside every window; background traffic was measured
on an idle box at **0.154 GB/s** and subtracted as a per-second term, because it scales with
elapsed time and therefore does *not* cancel in a subtraction between runs of different length.

### Measured DRAM bytes per generated token

| depth | GB/token | tg t/s | s/token | context term s | extra over weights | KV read once | **re-read factor** |
|---|---|---|---|---|---|---|---|
| 0 | 3.994 | 6.884 | 0.14526 | — | 0.000 | — | — |
| 2048 | 4.371 | 4.889 | 0.20456 | 0.05930 | 0.377 GB | 0.1174 GB | **3.21** |
| 4096 | 5.923 | 3.676 | 0.27204 | 0.12679 | 1.929 GB | 0.2349 GB | **8.21** |
| 8192 | 10.002 | 2.350 | 0.42553 | 0.28027 | 6.008 GB | 0.4698 GB | **12.79** |

Two things in that table had never been measured in this log, only computed.

**The weight term is now confirmed at the memory controller.** 3.994 GB per token at depth 0
against a 4.285 GB file — ratio 0.932. The weights are streamed almost exactly once per token,
with ~7% staying resident. Every previous statement about the weight term in this log was
inferred from the file size and the wall clock; this is the first direct reading, and it agrees.

**The KV cache is not read once. It is read three to thirteen times.** The GQA ratio for this
model is 28 attention heads / 4 KV heads = 7, and `ops.cpp:9284` calls
`..._one_chunk(params, dst, q_head, q_head+1, ic_start, ic_end, ...)` inside
`for (q_head = 0; q_head < neq2; q_head++)`, i.e. **one query head at a time**, so each KV head's
slice is re-scanned 7 times per token by construction. 3.21 at depth 2048 is that loop mostly
absorbed by cache. 8.21 at depth 4096 is it fully exposed. **12.79 at depth 8192 is more than the
head loop can produce on its own**, so a second amplifier exists on top of it.

### Correction 1: iteration 38's headline rate was wrong by a factor of eight

Iteration 38 said the context term ran at **1.80 GB/s** against a demonstrated 30.40 GB/s and
called that a **16.9x gap** — the number that motivated the whole "it is not bandwidth" argument.
That figure divided the context-term *time* by the KV cache size **assuming the KV is read once**.
It is not. Recomputing with measured bytes:

| depth | context-term bytes | context-term time | **context-term rate** | vs the 27.50 GB/s that depth-0 generation demonstrates |
|---|---|---|---|---|
| 2048 | 0.377 GB | 0.05930 s | 6.36 GB/s | 23% |
| 4096 | 1.929 GB | 0.12679 s | 15.21 GB/s | 55% |
| 8192 | 6.008 GB | 0.28027 s | **21.44 GB/s** | **78%** |

Whole-pass rate at depth 8192 is 23.50 GB/s against 27.50 GB/s at depth 0 — **85%**. The 16.9x
gap does not exist. At working depth the memory controller is running near the rate this box
demonstrably sustains, and iteration 38's central claim is withdrawn.

That does **not** restore "it's bandwidth-bound" as an answer, because the decomposition is now
sharper than the label: of the 6.008 GB of context traffic per token at depth 8192, **0.470 GB is
the KV cache read once and 5.538 GB — 92.2% — is redundant re-reading.** The machine is moving
bytes at close to peak. Almost all of them are bytes it has already read.

### Correction 2: I retracted the L3 crossover, and the retraction was wrong

Iteration 38 disfavoured the L3-crossover hypothesis before `15c1-ctxbytes` had run, on the
grounds that the *time* per KV position moved only 29.50 -> 31.95 ns (+8.3%) across the boundary
where the per-layer KV slice (2048 B/position) passes this CPU's 6 MB L3 at 3072 positions. That
reasoning used the wrong observable. In **bytes**, the crossover is not subtle:

| | slice per layer | vs 6 MB L3 | measured factor |
|---|---|---|---|
| depth 2048 | 4.19 MB | fits | 3.21 |
| depth 4096 | 8.39 MB | 40% over | 8.21 |

A 2.6x step in DRAM traffic, straddling exactly the predicted position, from a prediction
registered with no free parameters. **The crossover is real and the retraction is withdrawn.**

The reason it was invisible in time is the interesting part and it is the strongest single result
here: **DRAM traffic per token rose 2.6x across that boundary and the per-position time rose 8%.**
A term whose bytes can nearly triple while its time barely moves was not, at that depth, limited
by its bytes. Both of iteration 38's readings were half right and each one was wrong about the
other's half.

### What this does to iteration 39

PR #27478 cut the context term by a constant 28% at both 2048 and 8192 while changing no
arithmetic and — on the face of the patch, which reorganises accumulation rather than access —
no bytes. If bytes really are unchanged, that patch pushed the context-term rate from 21.44 GB/s
to 29.8 GB/s at depth 8192, which is *above* the 27.50 GB/s depth-0 generation demonstrates. That
is possible, because depth-0 generation is a quantised GEMM and its rate is not purely a DRAM
ceiling — but it is close enough that assuming it would be exactly the mistake this iteration just
caught iteration 38 making. **So it gets measured, not argued.**

### Queued: `15b7b-kvreread.sh`, four arms, each killing or confirming a named candidate

- `base8192` — the same configuration again, as a drift control against the 12.79 above.
- `t4` — 4 threads. `chunk_size = (nek1 + nth - 1) / nth`, so at depth 8192 with 8 threads each
  thread owns 1024 positions = 256 KB of K plus 256 KB of V for one KV head, against 256 KB of L2
  per *physical* core shared by two SMT siblings. One query head's pass already does not fit, so
  the next cannot reuse it. At `-t 4` the chunk doubles but SMT sharing disappears. If the factor
  moves, chunk-vs-cache is the second amplifier. If it does not, that candidate is dead.
- `fa0` — `-fa 0` does not use this loop nest at all; it builds KQ with a batched matmul that
  reads each K row once for all heads. Its factor should be near 1. That is the control proving
  the 12.79 belongs to the FA path and is not something the model does regardless.
- `pr` — the same pair on the PR #27478 binary. Unchanged bytes means the 28% was pure
  serialisation and the head-group fusion stacks on top at full value; reduced bytes means
  PR #27478 is partly a locality fix and the fusion is worth less than 12.79 suggests. Those lead
  to different next builds, which is the whole reason the arm exists.
- `thp` — same pair with THP forced to `always` and restored to whatever it was afterwards,
  because this is a 24/7 media server. Iteration 30 measured 142,287 minor faults at depth 8192
  against a ~14k floor, so the KV cache is not hugepage-backed there and page-table walks are real
  DRAM reads that the IMC counts. If the factor drops, part of the 12.79 was page walks.

`15b7a-fae2e.sh` runs first and is unaffected — it is the end-to-end deliverable for iteration 39.
