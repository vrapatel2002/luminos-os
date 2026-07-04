# NPU Investigation — Can Sentinel/HATS run int8 on our NPU?
<!-- [CHANGE: claude-code | 2026-07-01] -->

**TL;DR:** The Triton-XDNA NPU compile+execute path **works on our hardware** — but only
for **bf16** matmul. **int8 matmul does not compile for our NPU** (`npu1` / AIE2 /
Hawk Point). int8 acceleration is an **NPU2 (AIE2P / Strix)** feature in this toolchain.
Therefore the HATS/Sentinel CPU fallback is **correct for this silicon**, not a bug to fix.

---

## Hardware

- Device: `RyzenAI-npu1` (`/dev/accel/accel0`, PCI `0000:66:00.1`, driver `amdxdna`)
- SoC: Ryzen 7 8845HS (Hawk Point) — Phoenix-generation **AIE2** tile array
- This is **npu1**, NOT npu2. That distinction is the whole story below.

## What was tested (all on-silicon, 2026-07-01)

| Test | Path | Result |
|------|------|--------|
| Vendor `matmul_bf16_m64_n64_k64` on npu1 | Triton→MLIR→AIR→Peano→aircc→XRT→NPU | ✅ **PASS** — fresh xclbins compiled, `assert_close` vs CPU passed at M,N,K ∈ {256,1024,4096} |
| `src/kernels/npu_int8_gemv.py --npu` on npu1 | same | ❌ aircc fails: `operand #0 does not dominate this use` (degenerate N=64 GEMV) |
| Vendor `matmul_i8_m64_n64_k64` (square) on npu1 | same | ❌ aiecc fails: `Resource allocation pipeline failed` |

Plus a structural fact: the vendor examples ship int8 transform scripts **only** as
`transform_aie2p.mlir` (npu2). No `transform_aie2.mlir` (npu1) exists for any int8 example.
The vendor never validated int8 on AIE2.

**Conclusion:** bf16 matmul is supported on npu1; int8 matmul is not. int8 needs npu2 silicon.

## The working recipe (bf16 on npu1)

The path was previously thought "broken / falling back to CUDA." That was wrong. The real
blockers were three misconfigurations, now identified:

1. **mlir_air version.** Must be `0.0.1.2026041318+e279756.no.rtti` (the repo pin in
   `reference_code/Triton-XDNA/utils/mlir-air-hash.txt`, and exactly what
   `triton-xdna`'s own `Requires-Dist` declares). The venv had drifted to `c8ec089`
   (Apr-22). Fixed by force-reinstalling the pinned wheel from
   `https://github.com/Xilinx/mlir-air/releases/expanded_assets/latest-air-wheels-no-rtti`.

2. **Transform tiling script.** The driver's hardcoded fallback transform-IR string emits
   stale transform-dialect ops that current mlir_air rejects with
   `MLIRError: expected ':'` at `_ttshared_to_air`. You MUST set
   `AIR_TRANSFORM_TILING_SCRIPT` to a real script, e.g.
   `reference_code/Triton-XDNA/examples/matmul_bf16_m64_n64_k64/transform_aie2.mlir`,
   or generate one:
   ```
   python reference_code/Triton-XDNA/examples/matmul_transform.py \
     --l1-m 64 --l1-n 64 --l2-k 64 --pack-sizes 8 8 8 \
     --accum-type i32 --contract-input-type i16 -o transform_i8.mlir   # int8 variant
   ```

3. **Toolchain on PATH.** `aircc` invokes `aiecc` by bare name, so `.triton_venv/bin` must
   be on `PATH`, and `PEANO_INSTALL_DIR` must point at
   `.triton_venv/lib/python3.12/site-packages/llvm-aie`.

Full invocation that works (bf16):
```bash
VENV=~/luminos-os/.triton_venv
PATH="$VENV/bin:$PATH" \
PEANO_INSTALL_DIR="$VENV/lib/python3.12/site-packages/llvm-aie" \
AIR_TRANSFORM_TILING_SCRIPT="$VENV/../reference_code/Triton-XDNA/examples/matmul_bf16_m64_n64_k64/transform_aie2.mlir" \
AMD_TRITON_NPU_TARGET=npu1 XILINX_XRT=/usr \
"$VENV/bin/python" reference_code/Triton-XDNA/examples/matmul_bf16_m64_n64_k64/matmul_bf16_m64_n64_k64.py
# exits 0, assert_close passes → NPU produced correct result
```

Applying the same recipe to `npu_int8_gemv.py --npu` gets **further than ever before**
(clears the transform parse, clears AIR lowering) but dies in the AIE backend — because
int8 is not lowerable for AIE2.

## What this means for Sentinel / HATS

- `hats_kernel._hats_linear`'s CPU fallback is the **correct** behavior on this box. It is
  not masking a fixable NPU bug.
- The only way to actually offload Sentinel to *this* NPU is to run it in **bf16**, not
  int8 (bf16 matmul compiles and runs correctly on npu1). That requires a bf16 weight path
  and kernel — meaningful work, tracked as a future decision, not done here.
- Real int8 numbers to quote remain the **CPU** figures (~250–290 classifications/sec).

## Option 3 tested: int8-store → bf16-NPU-compute at Qwen2.5-0.5B shapes (2026-07-02)

Probe: `/tmp/probe_qwen_npu.py` — stores int8 weights, dequantizes to bf16 on host,
runs bf16 matmul on npu1 at Qwen2.5-0.5B layer shapes (hidden=896, inter=4864, 24 layers).

**The mechanism works** (k_proj/v_proj matched CPU exactly), **but it is not viable for an LLM**
on this stack, for three independent reasons:

1. **Per-call dispatch overhead dominates: ~52 ms *flat* per matmul launch.** The floor is
   identical (52–56 ms) whether the matmul is 256×1024×256 or 4864×1024×256 — so it's fixed
   XRT buffer-object allocation + xclbin-context + DMA-setup cost per `bare_matmul[grid](...)`,
   not compute. **CPU does the same matmuls in 0.7–14 ms** → the NPU path is **10–70× slower**.
   A Qwen forward pass is 7 matmuls × 24 layers = 168 launches × 52 ms ≈ **8.7 s/token**
   (≈0.11 tok/s decode). CPU wins by two orders of magnitude.
2. **Geometry constraint:** small-N (single-tile, N≤64) fails AIR lowering
   (`operand does not dominate`) for *any* dtype — including bf16. Only N≥256 tiles compile.
   Single-token decode is inherently N=1 → must pad to 256, wasting 256× compute.
3. **General-shape correctness/compile gaps:** multi-M-tile shapes (q/o/gate/up_proj) returned
   wrong results with the vendor bf16 `transform_aie2.mlir` (it isn't general for arbitrary M);
   down_proj (K=4864→pow2 8192) exceeds a single `tl.dot` K-tile and won't compile.

**Verdict:** the ~52 ms/launch overhead alone kills the LLM use case. Real NPU LLM inference
would need a persistent XRT runtime (register xclbin once, reuse hw_context, batch/pipeline
launches to amortize DMA) — i.e. bypass Triton's per-call Python launcher entirely. That's a
large custom-runtime effort, and even then you fight fixed DMA/sync cost and the npu1 int8
compute wall. For Sentinel-class bursty work, CPU remains the right choice.

## Reversibility notes

- Pre-change venv snapshot: `/tmp/triton_venv_freeze_20260701.txt` (pip freeze) and
  `/tmp/mlir_air_snapshot_c8ec089_20260701.tar.gz` (the replaced Apr-22 mlir_air package).
- The only durable change made to the venv: mlir_air realigned c8ec089 → e279756 (the pin).
- Build debris (`air_project/`, `tt.shared.mlir`, `~/.triton/cache/*`) is regenerated per run.
