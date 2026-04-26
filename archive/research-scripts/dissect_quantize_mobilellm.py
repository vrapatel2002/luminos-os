# [CHANGE: gemini-cli | 2026-04-22] MobileLLM INT8 Quantization for NPU HATS.
import onnx
import numpy as np
import os
import json
import sys
from onnx import numpy_helper

MODEL_PATH = os.path.expanduser("~/.local/share/luminos/models/mobilellm-r1-140m/model.onnx")
OUTPUT_DIR = os.path.expanduser("~/.local/share/luminos/models/mobilellm-r1-140m/quantized_weights/")
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "weight_manifest.json")

def main():
    print(f"Loading ONNX model from {MODEL_PATH}...")
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file not found at {MODEL_PATH}")
        sys.exit(1)
        
    model = onnx.load(MODEL_PATH)
    initializers = {init.name: init for init in model.graph.initializer}
    
    # Map nodes to find weights used in MatMul/Linear
    # MobileLLM uses MatMul for its linear layers.
    weight_names = set()
    for node in model.graph.node:
        if node.op_type in ["MatMul", "Gemm"]:
            # Typically input 1 is the weight
            if len(node.input) > 1:
                weight_names.add(node.input[1])

    manifest = []
    total_original_bytes = 0
    total_quantized_bytes = 0

    print(f"Dissecting model. Found {len(weight_names)} potential weight tensors.")

    for name in sorted(weight_names):
        if name not in initializers:
            continue
            
        init = initializers[name]
        weight = numpy_helper.to_array(init)
        
        # We only care about weights that are likely 2D (Linear) or 1D (Bias/Embedding)
        # but let's focus on the big ones.
        if weight.dtype != np.float32:
            print(f"Skipping {name}: non-fp32 type ({weight.dtype})")
            continue

        shape = list(weight.shape)
        original_bytes = weight.nbytes
        total_original_bytes += original_bytes

        # STEP: Calculate Scale factor
        # Using symmetric quantization: scale = max(abs(x)) / 127
        max_val = np.max(np.abs(weight))
        if max_val == 0:
            scale = 1.0
        else:
            scale = max_val / 127.0
            
        # STEP: Quantize
        quant_weight = (weight / scale).round().clip(-128, 127).astype(np.int8)
        
        # STEP: Save files
        safe_name = name.replace("/", "_").replace(".", "_")
        bin_filename = f"{safe_name}.bin"
        scale_filename = f"{safe_name}.scale"
        
        bin_path = os.path.join(OUTPUT_DIR, bin_filename)
        scale_path = os.path.join(OUTPUT_DIR, scale_filename)
        
        try:
            with open(bin_path, "wb") as f:
                f.write(quant_weight.tobytes())
            
            with open(scale_path, "wb") as f:
                # Save scale as float32
                f.write(np.array([scale], dtype=np.float32).tobytes())
        except Exception as e:
            print(f"ERROR: Failed to write files for {name}: {e}")
            sys.exit(1)

        quant_bytes = quant_weight.nbytes
        total_quantized_bytes += quant_bytes

        manifest.append({
            "name": name,
            "shape": shape,
            "bin": bin_filename,
            "scale": scale_filename,
            "original_size_bytes": original_bytes,
            "quantized_size_bytes": quant_bytes
        })
        
        # Progress indicator for big files
        if original_bytes > 10 * 1024 * 1024:
            print(f"Quantized large weight: {name} ({shape}) -> {quant_bytes/1024/1024:.2f}MB")

    # Save manifest
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print("\nQuantization Complete.")
    print(f"Weights Quantized: {len(manifest)}")
    print(f"Original Weight Memory: {total_original_bytes/1024/1024:.2f}MB")
    print(f"Quantized Weight Memory: {total_quantized_bytes/1024/1024:.2f}MB")
    print(f"Total Memory Saved: {(total_original_bytes - total_quantized_bytes)/1024/1024:.2f}MB")
    print(f"Manifest saved to {MANIFEST_PATH}")

if __name__ == "__main__":
    main()
