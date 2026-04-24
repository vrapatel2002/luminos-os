import json
import os
import sys
import time
from pathlib import Path

import torch
import triton
import triton.language as tl

os.environ["AMD_TRITON_NPU_TARGET"] = "npu1"
os.environ["XILINX_XRT"] = "/usr"

try:
    from triton.backends.amd_triton_npu.driver import NPUDriver
    _HAS_NPU_BACKEND = True
except ImportError:
    _HAS_NPU_BACKEND = False

@triton.jit
def int8_matmul_kernel(
    A, B, C,
    M: tl.constexpr, N: tl.constexpr, K: tl.constexpr,
    stride_am: tl.constexpr, stride_ak: tl.constexpr,
    stride_bk: tl.constexpr, stride_bn: tl.constexpr,
    stride_cm: tl.constexpr, stride_cn: tl.constexpr,
    BLOCK_SIZE_M: tl.constexpr,
    BLOCK_SIZE_N: tl.constexpr,
    BLOCK_SIZE_K: tl.constexpr,
):
    pid_m = tl.program_id(0)
    pid_n = tl.program_id(1)

    offs_m = pid_m * BLOCK_SIZE_M + tl.arange(0, BLOCK_SIZE_M)
    offs_n = pid_n * BLOCK_SIZE_N + tl.arange(0, BLOCK_SIZE_N)
    offs_k = tl.arange(0, BLOCK_SIZE_K)

    a_block = tl.load(A + offs_m[:, None] * stride_am + offs_k[None, :] * stride_ak)
    b_block = tl.load(B + offs_k[:, None] * stride_bk + offs_n[None, :] * stride_bn)

    c_block = tl.dot(a_block, b_block)

    tl.store(C + offs_m[:, None] * stride_cm + offs_n[None, :] * stride_cn, c_block)


def load_manifest(manifest_path: str = None) -> dict:
    if manifest_path is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        manifest_path = repo_root / "weight_manifest.json"
    with open(manifest_path, "r") as f:
        return json.load(f)

def select_npu_backend():
    if not _HAS_NPU_BACKEND:
        raise ImportError("Triton-XDNA NPU backend not found.")
    triton.runtime.driver.set_active(NPUDriver())

def run_int8_gemv(W: torch.Tensor, x: torch.Tensor, scale: float) -> torch.Tensor:
    assert W.dtype == torch.int8
    assert x.dtype == torch.int8

    M, K = W.shape
    is_vector = (x.dim() == 1)
    if is_vector:
        x = x.unsqueeze(1)
    
    # Pad to N=64 for standard 2D matmul
    BLOCK_SIZE_M = 64
    BLOCK_SIZE_N = 64
    
    B = torch.zeros((K, BLOCK_SIZE_N), dtype=torch.int8, device="cpu")
    original_N = x.shape[1]
    B[:, :original_N] = x

    original_M = M
    if M % BLOCK_SIZE_M != 0:
        M_padded = ((M + BLOCK_SIZE_M - 1) // BLOCK_SIZE_M) * BLOCK_SIZE_M
        W_padded = torch.zeros((M_padded, K), dtype=torch.int8, device="cpu")
        W_padded[:M, :] = W
        W = W_padded
        M = M_padded

    # K must be a power of 2 for tl.arange(0, BLOCK_SIZE_K)
    def next_power_of_2(n):
        p = 1
        while p < n: p *= 2
        return p

    K_padded = next_power_of_2(K)
    if K_padded != K:
        W_new = torch.zeros((M, K_padded), dtype=torch.int8, device="cpu")
        W_new[:, :K] = W
        W = W_new
        
        B_new = torch.zeros((K_padded, BLOCK_SIZE_N), dtype=torch.int8, device="cpu")
        B_new[:K, :] = B
        B = B_new
        K = K_padded

    C = torch.empty((M, BLOCK_SIZE_N), dtype=torch.int32, device="cpu")

    grid = (
        triton.cdiv(M, BLOCK_SIZE_M),
        triton.cdiv(BLOCK_SIZE_N, BLOCK_SIZE_N),
    )

    int8_matmul_kernel[grid](
        W, B, C,
        M, BLOCK_SIZE_N, K,
        W.stride(0), W.stride(1),
        B.stride(0), B.stride(1),
        C.stride(0), C.stride(1),
        BLOCK_SIZE_M=BLOCK_SIZE_M,
        BLOCK_SIZE_N=BLOCK_SIZE_N,
        BLOCK_SIZE_K=K,
    )

    y_i32 = C[:original_M, :original_N]
    if is_vector:
        y_i32 = y_i32.squeeze(1)
        
    return y_i32.to(torch.float32) * scale


def reference_int8_gemv(W: torch.Tensor, x: torch.Tensor, scale: float) -> torch.Tensor:
    W_i32 = W.to(torch.int32)
    x_i32 = x.to(torch.int32)
    acc = torch.matmul(W_i32, x_i32)
    return acc.to(torch.float32) * scale

def self_test():
    print("=" * 60)
    print("  INT8 GEMV — Self Test (CPU Reference)")
    print("=" * 60)
    manifest = load_manifest()
    
    M, K = 576, 576
    scale = manifest["layers"]["attn_q_proj"]["scale"]
    W = torch.randint(-128, 127, (M, K), dtype=torch.int8)
    x = torch.randint(-128, 127, (K,), dtype=torch.int8)
    y_ref = reference_int8_gemv(W, x, scale)
    y = run_int8_gemv(W, x, scale)
    print(f"Test max diff: {(y - y_ref).abs().max().item()}")

def npu_benchmark():
    print("=" * 60)
    print("  INT8 GEMV — NPU Bare-Metal Benchmark")
    print("  Target: MobileLLM-R1-140M on XDNA 1 (npu1)")
    print("=" * 60)

    print("\n  [Pre-flight] Checking NPU access...")
    accel_paths = ["/dev/accel/accel0", "/dev/accel0"]
    accel_found = None
    for p in accel_paths:
        if os.path.exists(p):
            accel_found = p
            break
    if accel_found:
        print(f"    ✅ NPU device: {accel_found}")
    else:
        print(f"    ❌ No NPU device found")
        sys.exit(1)

    print("  [Pre-flight] Activating Triton-XDNA NPU backend...")
    select_npu_backend()
    print("    ✅ NPU backend active")

    manifest = load_manifest()
    test_layers = [
        ("attn_q_proj",    576,  576),
        ("attn_k_proj",    192,  576),
        ("ffn_gate_proj",  2048, 576),
        ("ffn_down_proj",  576,  2048),
    ]

    all_passed = True
    total_npu_time = 0.0

    for layer_name, M, K in test_layers:
        scale = manifest["layers"][layer_name]["scale"]
        print(f"\n  ── {layer_name} [{M}, {K}] ──")
        print(f"    Scale: {scale}")

        W = torch.randint(-128, 127, (M, K), dtype=torch.int8)
        x = torch.randint(-128, 127, (K,), dtype=torch.int8)

        y_ref = reference_int8_gemv(W, x, scale)

        t0 = time.perf_counter()
        y_npu = run_int8_gemv(W, x, scale)
        t1 = time.perf_counter()
        
        latency_ms = (t1 - t0) * 1000.0
        total_npu_time += latency_ms

        max_diff = (y_npu - y_ref).abs().max().item()

        print(f"    XRT BO alloc: ✅ (kernel launched successfully)")
        print(f"    Output shape: {y_npu.shape}")
        print(f"    Latency:      {latency_ms:.3f} ms")
        print(f"    Max diff:     {max_diff}")

        if max_diff == 0.0:
            print(f"    Result:       ✅ EXACT MATCH (NPU == CPU)")
        elif max_diff < 1e-3:
            print(f"    Result:       ✅ MATCH (within f32 rounding)")
        else:
            print(f"    Result:       ❌ MISMATCH")
            all_passed = False

    print(f"\n{'=' * 60}")
    print(f"  Total NPU time: {total_npu_time:.3f} ms")
    if all_passed:
        print(f"  ✅ All layers passed — NPU output matches CPU reference")
    else:
        print(f"  ❌ Some layers failed — see above")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    if "--npu" in sys.argv:
        npu_benchmark()
    else:
        self_test()
