# TurboQuant Repo Audit
Date: 2026-04-24
Hardware: RTX 4050 (SM89), Arch Linux 6.19.11-arch1-1
Agent: claude-sonnet-4-6 (Claude Code)

---

## System Prerequisites

| Component | Version / Status |
|-----------|-----------------|
| nvidia-smi | FAILED — driver not loaded (see Errors) |
| nvcc | 13.2.78 — at `/opt/cuda/bin/nvcc` (NOT on default PATH) |
| CUDA Toolkit | 13.2.1-1 — installed at `/opt/cuda` |
| cuDNN | 9.21.1.3-1 — installed |
| cmake | 4.3.1 |
| GCC | 15.2.1 (2026-02-09) |
| G++ | 15.2.1 |
| Python | 3.12.13 |
| GPU compute cap | UNKNOWN — nvidia-smi failed to query |
| NCCL | NOT INSTALLED |
| /usr/local/cuda symlink | ABSENT — must pass `-DCMAKE_CUDA_COMPILER=/opt/cuda/bin/nvcc` or set PATH |

---

## Repos Attempted

| Repo | URL | Branch | Cloned | TurboQuant Refs | CMake OK |
|------|-----|--------|--------|-----------------|----------|
| TheTom fork | github.com/TheTom/llama.cpp | feature/turboquant-kv-cache | ❌ FAILED | N/A | N/A |
| Main llama.cpp | github.com/ggerganov/llama.cpp | default (main) | ✅ | 0 refs | ✅ |
| tonbistudio pytorch | github.com/tonbistudio/turboquant-pytorch | default | ✅ | 75 refs | N/A (Python) |
| ggml-org | github.com/ggml-org/llama.cpp | default | ✅ | 0 refs | ✅ |

---

## Errors Found and Root Causes

### ERROR 1: nvidia-smi FAILED — "couldn't communicate with the NVIDIA driver"

**Root cause: Kernel version mismatch between running kernel and installed driver modules.**

- Running kernel: `6.19.11-arch1-1`
- nvidia-open modules installed for: `6.19.14-arch1-1`
- Both kernel versions exist under `/usr/lib/modules/` — the system was updated (to 6.19.14) but NOT rebooted
- The GPU driver `.ko` files (`nvidia.ko`, `nvidia-uvm.ko`, `nvidia-drm.ko`, `nvidia-modeset.ko`) are built against 6.19.14 and cannot load into 6.19.11
- `modinfo nvidia` returns "Module nvidia not found" — confirmed: no matching .ko for the running kernel
- `lsmod | grep nvidia` shows only `nvidia_wmi_ec_backlight` (a backlight helper, not the GPU driver)
- **Impact**: GPU is completely inaccessible. All CUDA runtime operations fail silently or are skipped.
- **This is a reboot-fix situation, not a software bug.**

### ERROR 2: repo-thetom clone FAILED — "could not read Username for 'https://github.com'"

**Root cause: The repository `github.com/TheTom/llama.cpp` does not exist.**

- `git clone` returned exit code 128 with credential prompt error
- `git ls-remote` with `GIT_TERMINAL_PROMPT=0` confirmed the same failure
- `curl -s -o /dev/null -w "%{http_code}" https://github.com/TheTom/llama.cpp` returned **HTTP 404**
- The repo was never created, has been deleted, or the URL is incorrect
- The branch `feature/turboquant-kv-cache` does not exist because the repo itself doesn't exist
- There is no TheTom fork of llama.cpp with TurboQuant KV-cache on GitHub as of 2026-04-24

### ERROR 3: nvcc not on system PATH

**Root cause: CUDA is installed at `/opt/cuda`, not the conventional `/usr/local/cuda`, and no symlink exists.**

- `which nvcc` returns "command not found" with default PATH
- `nvcc` lives at `/opt/cuda/bin/nvcc`
- Many build scripts and cmake invocations assume `/usr/local/cuda` or that `nvcc` is in PATH
- cmake configure only succeeded because we manually prepended `/opt/cuda/bin` to PATH
- Any automated build script that does not set `PATH` or `CUDA_PATH` will fail at CUDA detection

### ERROR 4: NCCL not installed

**Root cause: NCCL (NVIDIA Collective Communications Library) is not present.**

- cmake configure for both llama.cpp repos printed: `Could NOT find NCCL (missing: NCCL_LIBRARY NCCL_INCLUDE_DIR)`
- cmake continues with a warning, not a hard failure: "performance for multiple CUDA GPUs will be suboptimal"
- NCCL is only needed for multi-GPU setups; RTX 4050 is single-GPU so this is a non-blocking warning
- `pacman -Qs nccl` returns nothing — package not installed from any repo

### ERROR 5: PyTorch repo import fails without deps — "No module named 'torch'"

**Root cause: PyTorch and scipy are not installed in the system Python environment.**

- System `python3` has no `torch` installed
- The `.triton_venv` virtualenv at `/home/shawn/luminos-os/.triton_venv` has `torch 2.11.0+cpu` but is missing `scipy`
- Import fails at `from .lloyd_max import LloydMaxCodebook` → `from scipy import integrate, special`
- After installing `requirements.txt` into `.triton_venv`, all imports succeed
- **Additional issue**: The installed torch is CPU-only (`torch 2.11.0+cpu`). The GPU benchmark test (Test 7) was skipped because `torch.cuda.is_available()` returns False — this is caused by ERROR 1 (GPU driver not loaded), not a packaging problem.

### ERROR 6: repo-main and repo-ggml are identical repos — no TurboQuant

**Root cause: `github.com/ggerganov/llama.cpp` and `github.com/ggml-org/llama.cpp` are mirrors.**

- Both repos cloned to the same commit: `0adede8 parser: fix structured output bug (#22302)`
- Both report 0 TurboQuant references under any search pattern
- This is expected: TurboQuant KV-cache compression has NOT been merged into mainline llama.cpp as of 2026-04-24
- The `GGML_CUDA_FA_ALL_QUANTS` cmake flag exists in mainline (for FlashAttention quant coverage) but is unrelated to TurboQuant

### WARNING: GCC 15.2.1 — CUDA support unconfirmed

**Root cause: GCC 15.2.1 was released in early 2026; official CUDA 13.2 support matrix only listed through GCC 14.**

- cmake configure completed without error — CUDA 13.2 accepted GCC 15.2.1 as host compiler
- This is the first indication that CUDA 13.2 (built March 2026) has expanded GCC support
- However, actual CUDA kernel compilation has not been tested — compile-time failures remain possible
- If actual `cmake --build` fails with host compiler errors, adding `-DCMAKE_CUDA_HOST_COMPILER=$(which gcc)` or installing `gcc14` as an alternative compiler may be required

---

## Repo Comparison: TurboQuant Content

| Repo | What it contains | TurboQuant completeness |
|------|-----------------|------------------------|
| **repo-pytorch** | Full Python reference: TurboQuantV2, V3, Lloyd-Max codebook, MSE compressor, QJL correction, KV-cache wrapper, validation suite | ⭐ MOST COMPLETE — all algorithms, all tests passing on CPU |
| repo-main / repo-ggml | Mainline llama.cpp + ggml CUDA backend, FlashAttention support | Zero TurboQuant code — needs custom integration |
| repo-thetom | Does not exist | N/A |

---

## Test Results Summary

### repo-pytorch (turboquant/test_turboquant.py)
Run via: `.triton_venv/bin/python3 turboquant/test_turboquant.py`

| Test | Result |
|------|--------|
| TEST 1: Lloyd-Max Codebook Properties | PASSED |
| TEST 2: MSE Quantizer Distortion | PASSED (all bit depths: 1–4) |
| TEST 3: Inner Product Unbiasedness (QJL Correction) | PASSED |
| TEST 4: MSE-Only Inner Product Bias | PASSED |
| TEST 5: KV Cache Compression Ratios | PASSED (3.94x–7.76x compression measured) |
| TEST 6: Needle-in-Haystack Retrieval | PASSED — EXACT match at 2K, 4K, 8K context for 2/3/4-bit |
| TEST 7: GPU Benchmark | SKIPPED — CUDA not available (GPU driver not loaded) |

### CMake configure (llama.cpp repos)
Both `repo-main` and `repo-ggml` — cmake exits 0 with:
- CUDA Toolkit 13.2.78 detected
- CUDA architecture SM89 registered
- `GGML_CUDA_FA_ALL_QUANTS=ON` confirmed in cache
- NCCL warning (non-fatal)
- "No CUDA devices found" warning (non-fatal — expected with driver not loaded)

---

## Build Requirements: What Is Missing Before `cmake --build`

| Requirement | Status | Notes |
|-------------|--------|-------|
| CUDA Toolkit (nvcc) | ✅ Installed | `/opt/cuda` — must add to PATH |
| cuDNN | ✅ Installed | 9.21.1.3 |
| NVIDIA GPU driver | ❌ NOT LOADED | Kernel version mismatch — reboot required |
| NCCL | ❌ Not installed | Non-blocking for single-GPU; install `nccl` from AUR if needed |
| /usr/local/cuda symlink | ❌ Absent | Scripts expect it at this path; `ln -s /opt/cuda /usr/local/cuda` would fix |
| GCC compatibility at compile time | ⚠️ Untested | cmake passes; actual CUDA kernel compile not yet tested with GCC 15 |
| ccache | ⚠️ Missing | Non-blocking — just slower rebuilds |

---

## Best Repo for Luminos

**`repo-pytorch` (tonbistudio/turboquant-pytorch)** is the only repository with actual TurboQuant implementation.

- 75 references to TurboQuant algorithms, all three generations (V1/V2/V3) implemented
- All core tests pass on CPU right now — no GPU required to verify algorithm correctness
- Implements the key insight from 8+ community implementations: V3 (MSE-only + asymmetric + residual window) outperforms the paper's QJL variant in practice
- The paper's K6/V4 with rw=128 achieves ~2x compression with perfect output — practical target
- The mainline llama.cpp repos (`repo-main`/`repo-ggml`) are the correct integration target — no TurboQuant code yet, but cmake configures cleanly with CUDA 13.2 + SM89

---

## Recommendation for Next Step

**Describe only — no code:**

1. **Reboot the system** to load the `nvidia-open 595.58.03` driver built for kernel 6.19.14-arch1-1. After reboot, `nvidia-smi` should work and GPU tests can be re-run.

2. **Create the `/usr/local/cuda` symlink** pointing to `/opt/cuda` so standard tooling finds CUDA without PATH manipulation.

3. **Study `repo-pytorch/turboquant/`** to understand the V3 algorithm before attempting any llama.cpp integration. The `turboquant.py`, `compressors_v3.py`, and `lloyd_max.py` files contain the full algorithm.

4. **Decide on integration approach**: TurboQuant KV compression can be implemented either (a) as a Python-level HuggingFace cache hook (like `TurboQuantKVCacheV3` in repo-pytorch) for prototype speed, or (b) as a CUDA kernel in ggml's CUDA backend for production performance. Option (a) requires no C++ changes; option (b) requires implementing the quantization codebook lookup as a `.cu` file in `ggml/src/ggml-cuda/`.

5. **Install NCCL** only if multi-GPU operation is planned. Single RTX 4050 does not need it.
