"""
src/npu/quantize_int8.py
MobileLLM-R1-140M INT8 Symmetric Quantization for HATS NPU inference.

Extracts MatMul weights from ONNX model, applies per-tensor symmetric INT8
quantization (scale = max(|W|) / 127), and saves binary weight + scale files.

Output directory: ~/.local/share/luminos/models/mobilellm-r1-140m/quantized_weights/
Output files:     <safe_name>.bin (int8 raw bytes) + <safe_name>.scale (float32)
Manifest:         weight_manifest.json (flat array mapping names to files)

Target: compress FP32 model (~1GB) to ~64MB INT8 weights.
Memory budget: 800MB hard limit for HATS runtime.

Run this once before starting sentinel or compat router.
Quantization is idempotent — re-running overwrites existing weights.

[CHANGE: claude-code | 2026-04-24]
"""

import json
import os
import sys

import numpy as np

# Onnx is installed in the triton_venv
import glob
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
_TRITON_VENV = os.path.join(_REPO_ROOT, ".triton_venv")
for _sp in glob.glob(os.path.join(_TRITON_VENV, "lib/python*/site-packages")):
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

try:
    import onnx
    from onnx import numpy_helper
except ImportError:
    print("ERROR: onnx not found. Activate .triton_venv or install onnx.")
    sys.exit(1)

MODEL_PATH = os.path.expanduser(
    "~/.local/share/luminos/models/mobilellm-r1-140m/model.onnx"
)
OUTPUT_DIR = os.path.expanduser(
    "~/.local/share/luminos/models/mobilellm-r1-140m/quantized_weights/"
)
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "weight_manifest.json")


def quantize(model_path: str = MODEL_PATH, output_dir: str = OUTPUT_DIR) -> str:
    """
    Quantize MobileLLM-R1-140M ONNX model to INT8.

    Args:
        model_path: Path to model.onnx
        output_dir: Directory to write .bin/.scale files + manifest

    Returns:
        Path to written weight_manifest.json
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, "weight_manifest.json")

    print(f"Loading {model_path}...")
    model = onnx.load(model_path)
    initializers = {init.name: init for init in model.graph.initializer}

    weight_names = set()
    for node in model.graph.node:
        if node.op_type in ("MatMul", "Gemm") and len(node.input) > 1:
            weight_names.add(node.input[1])

    print(f"Found {len(weight_names)} MatMul weight tensors — quantizing...")

    manifest = []
    total_orig = 0
    total_quant = 0

    for name in sorted(weight_names):
        if name not in initializers:
            continue
        weight = numpy_helper.to_array(initializers[name])
        if weight.dtype != np.float32:
            continue

        shape = list(weight.shape)
        total_orig += weight.nbytes

        # Symmetric per-tensor quantization: scale = max(|W|) / 127
        max_val = float(np.max(np.abs(weight)))
        scale = (max_val / 127.0) if max_val > 0 else 1.0
        quant = np.clip(weight / scale, -128, 127).round().astype(np.int8)

        safe_name = name.replace("/", "_").replace(".", "_")
        bin_file = f"{safe_name}.bin"
        scale_file = f"{safe_name}.scale"

        with open(os.path.join(output_dir, bin_file), "wb") as f:
            f.write(quant.tobytes())
        with open(os.path.join(output_dir, scale_file), "wb") as f:
            f.write(np.array([scale], dtype=np.float32).tobytes())

        quant_bytes = quant.nbytes
        total_quant += quant_bytes

        manifest.append({
            "name": name,
            "shape": shape,
            "bin": bin_file,
            "scale": scale_file,
            "original_size_bytes": weight.nbytes,
            "quantized_size_bytes": quant_bytes,
        })

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nQuantization complete.")
    print(f"  Weights: {len(manifest)}")
    print(f"  Original: {total_orig / 1024 / 1024:.1f}MB")
    print(f"  Quantized: {total_quant / 1024 / 1024:.1f}MB")
    print(f"  Saved: {(total_orig - total_quant) / 1024 / 1024:.1f}MB")
    print(f"  Manifest: {manifest_path}")
    return manifest_path


if __name__ == "__main__":
    quantize()
