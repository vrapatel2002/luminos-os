import os
import json
import numpy as np

QUANT_DIR = os.path.expanduser("~/.local/share/luminos/models/mobilellm-r1-140m/quantized_weights/")
OLD_MANIFEST_PATH = os.path.join(QUANT_DIR, "weight_manifest.json")
NEW_MANIFEST_PATH = "weight_manifest.json"

def get_scale(filename):
    path = os.path.join(QUANT_DIR, filename)
    return float(np.fromfile(path, dtype=np.float32)[0])

def rebuild():
    with open(OLD_MANIFEST_PATH, "r") as f:
        old_manifest = json.load(f)
    
    # Map old entries to generic names for the benchmark script
    # We use layer 0 weights as representative scales
    mapping = {
        "model.layers.0.attn.q_proj.MatMul.weight": "attn_q_proj",
        "model.layers.0.attn.k_proj.MatMul.weight": "attn_k_proj",
        "model.layers.0.mlp.gate_proj.MatMul.weight": "ffn_gate_proj",
        "model.layers.0.mlp.down_proj.MatMul.weight": "ffn_down_proj",
    }
    
    layers_cfg = {}
    for entry in old_manifest:
        name = entry["name"]
        if name in mapping:
            generic_name = mapping[name]
            scale = get_scale(entry["scale"])
            layers_cfg[generic_name] = {
                "scale": scale,
                "shape": entry["shape"]
            }
            
    new_manifest = {
        "model": {
            "name": "MobileLLM-R1-140M",
            "hidden_dim": 576,
            "intermediate_dim": 2048,
            "layers": 15
        },
        "layers": layers_cfg,
        "all_weights": old_manifest # Keep the full list for future HATS streaming
    }
    
    with open(NEW_MANIFEST_PATH, "w") as f:
        json.dump(new_manifest, f, indent=2)
    print(f"Rebuilt manifest at {NEW_MANIFEST_PATH}")

if __name__ == "__main__":
    rebuild()
