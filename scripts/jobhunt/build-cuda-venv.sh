#!/usr/bin/env bash
# Build a CUDA-enabled llama-cpp-python in an ISOLATED venv for jobhunt.
# [CHANGE: claude-code | 2026-08-05] Phase 0 of scripts/jobhunt/PLAN.md
#
# WHY A SEPARATE VENV: /opt/luminos/venv is HIVE's. A failed CUDA rebuild there
# takes HIVE down with it. This script must never write to that path.
#
# WHY g++-15: CUDA 13.3's /opt/cuda/include/crt/host_config.h rejects __GNUC__ > 15
# and the system gcc is 16.1.1. gcc15 is already installed; nothing to install.
#
# WHY PYTHONNOUSERSITE=1: BUG-093 — user-site packages shadow pacman's and
# silently poison builds.
set -euo pipefail

VENV=/opt/luminos/venv-jobhunt
HIVE_VENV=/opt/luminos/venv
# Version is a parameter because the vendored llama.cpp is what has to be
# compatible with the installed CUDA, and that pairing changes release to release.
# 0.3.20 (the version HIVE uses) does NOT build against CUDA 13.3: its
# vendor/llama.cpp/ggml/src/ggml-cuda/argsort.cu calls cuda::make_counting_iterator
# and cuda::make_strided_iterator, which this CCCL does not provide.
LCP_VERSION="${1:-0.3.34}"

# Refuse to run if anything would touch HIVE's venv.
case "$VENV" in
  "$HIVE_VENV"|"$HIVE_VENV"/*) echo "REFUSING: target is HIVE's venv"; exit 1 ;;
esac

echo "=== [1/4] creating venv at $VENV"
rm -rf "$VENV"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip -q install --upgrade pip wheel setuptools

echo "=== [2/4] building llama-cpp-python with CUDA (this is the slow part)"
export PYTHONNOUSERSITE=1
export CUDACXX=/opt/cuda/bin/nvcc
export CMAKE_BUILD_PARALLEL_LEVEL=4   # 14 GB RAM total; nvcc is memory-hungry
export CMAKE_ARGS="-DGGML_CUDA=on \
-DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-15 \
-DCMAKE_CUDA_ARCHITECTURES=89 \
-DLLAMA_CURL=OFF"
# sm_89 = Ada / RTX 4050 Laptop. Pinning it cuts build time and size sharply
# versus compiling every architecture.

echo "    building llama-cpp-python==$LCP_VERSION"
"$VENV/bin/pip" install --no-cache-dir --verbose "llama-cpp-python==$LCP_VERSION"

echo "=== [3/4] checking the build reports GPU support"
"$VENV/bin/python" - <<'PY'
import llama_cpp, sys
ok = llama_cpp.llama_supports_gpu_offload()
print("llama_cpp", llama_cpp.__version__, "supports_gpu_offload =", ok)
sys.exit(0 if ok else 1)
PY

echo "=== [4/4] build flag is NOT proof — a CUDA build falls back to CPU silently"
echo "    when the device is denied. Real-inference test is run separately,"
echo "    through dgpu-exec-v2, by verify-cuda-venv.sh."
echo "OK: $VENV built."
