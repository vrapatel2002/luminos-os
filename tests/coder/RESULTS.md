# luminos-coder — measured results (G14 GA403UU, RTX 4050 6 GB, 15.6 GiB RAM)
<!-- [CHANGE: claude-code | 2026-10-23] DECISION 157 -->

All numbers from `tests/coder/bench-run.sh` / `bench.py` (llama-server's own `timings`), llama.cpp-cuda b10452
(`/usr/bin/llama-server`), always through `dgpu-exec-v2`. Raw lines: `~/.local/state/luminos/coder/bench-results.jsonl`.
Prompt = real Go source from `cmd/` (varied text — a repeated paragraph breaks MoE output, see project_moe_expert_offload).

## Writer — Qwen3.6-35B-A3B UD-Q3_K_XL (16.1 GB, MoE 3B active)
| config | VRAM | prompt t/s | gen t/s | note |
|---|---|---|---|---|
| ctx 32K, default batch (ub 512) | 4712 MiB | 80–87 | — | (killed by BUG-212 before gen) |
| ctx 32K, `-b 2048 -ub 2048` | 4630 MiB | 198 | 18.4 | |
| **ctx 32K, `-b 4096 -ub 4096`** | 4664 MiB | **328** | **18.7** | |
| ctx 128K, ub 4096 | 4698 MiB | 232 | 9.5 | bigger KV pushes experts to CPU |
| ctx 128K, **49 092-token prompt** | 4698 MiB | 277 | 6.4 | long context works; gen slows with depth |
Gateway default: ctx 65 536, ub 4096, `-fitt 256` (`CODER_WRITER_CTX` overrides).

## Reviewer — Qwen3.8-27B (dense)
| quant / load | locked RAM | prompt t/s | gen t/s | MTP accepted | note |
|---|---|---|---|---|---|
| UD-IQ4_XS 13.6 GB, mmap, ub 512 | — | 47 | < 1 | — | **thrash**: 68 k major faults / 6 s, NVMe 600 MB/s, desktop swapping |
| UD-IQ3_XXS 10.4 GB, mmap, ub 2048 | — | 223 | 2.1 | 177/243 | |
| UD-IQ3_XXS, `-lm mlock` | 7.5 GB | 323 | 1.7 | — | faults gone, still slow → not I/O |
| **UD-Q2_K_XL 9.4 GB, `-lm mlock`** | 6.3 GB | **272** | **2.4** | 180/237 | **chosen** |
| UD-Q3_K_XL 12.5 GB, `-lm mlock` | — | — | — | — | **OOM-killed at load** (9.6 GB shmem) |
| **UD-Q3_K_XL, `-lm mlock`, 2026-10-24** (after Baloo off + shared MCP + reaper; 10.4 GB available before) | 9.4 GB | 273 | **2.35** | 70/114 | **loads now**; min available 405 MB, swap 2.5 GB, no OOM |
| **UD-IQ4_XS 14.3 GB, `-lm mlock`, 2026-10-24** | 10.5 GB | 194 | **2.67** | 73/106 | loads, but min available **81 MB**, swap 3.8 GB — earlyoom (`-m 5 -s 90`) was ~0.3 GB of swap from firing |
Why ~2.4 t/s is the ceiling: ~60 % of every token is computed on the CPU, and during generation the CPU sits at
**28 W of its 30 W dGPU-busy ceiling and 80.5 °C of the 82 °C target** (spectrum, DECISION 146). More watts would hit the
temperature limit next. The quant type does not change it (IQ3 1.7, Q2_K 2.4).
While the reviewer is loaded, ~6.3 GB is pinned: MemAvailable falls to ~0.4 GB and the desktop is pushed into
zram/pagefile — expect the desktop to feel slower during a review. The gateway unloads it after the next writer request.

## Power (verified)
- Model load → `nvidia-powerd` unmasked + started (Dynamic Boost; `nvidia-smi -pl` is a no-op here, BUG-069).
- Gateway stop / 15 min idle → model unloaded, `nvidia-powerd` stopped + **masked** → `runtime_status = suspended` 25 s later.
- PCIe link during inference: Gen4 x8 (`pcie.link.gen.current = 4`), GPU 2055 MHz SM, 16–25 W.
- Fan curve untouched (EC curve v6 stays in charge).

## Proof — does the Qwen3.8 review make the code pass?
Task: `tests/coder/proof/TASK.md` (custom "LUMA" version-range spec, deliberately not npm — memorisation does not help).
107 hidden tests (`test_hidden.py`), validated 107/107 on `reference.py`. All arms start from the SAME Qwen3.6 solution
(run A initial = 91/107: hyphen ranges crash, `1.x`/`1.2.*` upper bounds wrong, `>*`/`<*` wrong, include_pre upper-bound
exclusion missing, `v1.2.3` in a range rejected, `>=1.2.3.4` / `>=` accepted). Then each review goes back to Qwen3.6 to fix.

| arm | review settings | hidden tests |
|---|---|---|
| initial (Qwen3.6 alone) | — | 91 / 107 |
| Qwen3.6 re-check, no reviewer | — | 95 / 107 |
| Qwen3.6 self-review | no penalty → **looped on one sentence until max_tokens** | 92 / 107 |
| Qwen3.6 self-review | presence_penalty 1.5 | 93 / 107 |
| Qwen3.6 self-review | + quote filter | 92 / 107 |
| **Qwen3.8-Q2 cross-review** | thinking 1024, free-form | **86 / 107** (worse) |
| **Qwen3.8-Q2 cross-review** | thinking 2048 + SPEC-quote rule + code quote filter | **95 / 107** |

**Honest verdict:** with the Qwen3.8 that fits this laptop (UD-Q2_K_XL, CPU-bound at ~2 t/s), the review is NOT
reliably smarter than Qwen3.6. Free-form, it mixed real defects (pre-release upper bound, hyphen partial upper ends,
max_satisfying swallowing errors) with invented rules (">* must raise" — the spec says it "matches NOTHING"; "a middle
empty `||` side must raise" — the spec says it is NOT invalid), and the writer applied both: 91 → 86. Forcing a verbatim
spec quote and dropping unverifiable claims in code (BUG-109 rule) turned it into a net gain (95, best cross arm, beats
every self-review arm) — but it only ties a plain re-check, and it missed the biggest bugs (hyphen ranges crash).
No arm reached 107. The task is "out of 3.6's reach"; on this hardware the available 3.8 does not close the gap.
What would: a better-quantised Qwen3.8 (Q4: needs ~10 GB more free RAM — e.g. the 32 GB SPD mod, or closing apps; baloo
alone holds 2 GB), or a cloud reviewer (declined by Shawn).

## Claude Desktop end-to-end (Code tab) — PASSED 2026-10-24 01:34–02:31
"Claude (Local Qwen)" → Code tab → folder `tests/coder/demo`, task: `parse_duration` (h/m/s, order, at most once,
ValueError on malformed). What the local pair did, all inside the Desktop app:
1. Qwen3.6 wrote `duration.py`, spotted its own empty-string bug, fixed it, wrote `test_duration.py`.
2. `luminos-coder: run_tests` (MCP) → 3/7, it diagnosed all 4 (one wrong expectation in its own test, missing `import
   pytest`, None → TypeError), fixed both files → 7/7.
3. `review_start` → gateway swapped to Qwen3.8 (ready 19.6 s) → review 1024 s → "no verified defects", note: dead
   `all(g is None)` branch → swap back (22 s) → `review_wait` → removed the dead code → 7/7 → final answer.
Independent check by me afterwards (22 cases incl. `1m2h`, `5s5s`, `1.5h`, `-1h`, `1H`, whitespace): **22/22**.
Wall time 53 min (prompt re-reads after each swap dominate). Costs found and fixed on the way: Claude Code request is
74 348 tokens → ctx 131072 (64K gave HTTP 400); stream silent > ~90 s is dropped → gateway SSE pings (21 on the first
turn); a turn queued behind the 17-min review hit Claude Code's 600 s API timeout and retried by itself →
`luminos-claude-local` now exports `API_TIMEOUT_MS=3600000`. Each luminos-coder tool asks permission once (Always allow).
