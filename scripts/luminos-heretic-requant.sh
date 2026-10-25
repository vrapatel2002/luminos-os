#!/bin/bash
# [CHANGE: claude-code | 2026-10-24] Heretic-abliterated Qwen3.6 + Qwen3.8 (Shawn: "use heretic and do it").
# Heretic itself needs ~15 GB VRAM (4-bit) + ~80 GB RAM to merge a 27B — not this laptop — so we take Heretic
# outputs made on big GPUs and requantize their BF16 with Unsloth's own per-tensor recipe + imatrix.
set -u
A=~/.local/share/luminos/models/abliterated; cd $A; H=https://huggingface.co
get(){ echo "$(date +%T) start $2"; curl -L --fail -sS -C - -o "$3" "$H/$1/resolve/main/$2" || { echo "FAIL $2"; return 1; }
  want=$(curl -sIL "$H/$1/resolve/main/$2" | grep -i '^x-linked-etag' | tail -1 | tr -d '"\r' | awk '{print $2}')
  have=$(sha256sum "$3" | cut -c1-64); if [ "$want" = "$have" ]; then echo "$(date +%T) OK $3 sha256"; else echo "$(date +%T) SHA MISMATCH $3"; return 1; fi; }
quant(){ # bf16 imatrix types out base
  echo "$(date +%T) quantize $4"
  nice -n 10 /usr/bin/llama-quantize --imatrix "$2" --tensor-type-file "$3" "$1" "$4" "$5" 8 > "$4.quant.log" 2>&1 \
    && echo "$(date +%T) OK $4 $(du -h "$4" | cut -f1)" || { echo "QUANT FAIL $4 (see $4.quant.log)"; return 1; }; }
# 1) Qwen3.6-35B-A3B Heretic (llmfan46, refusals 83→10/100, KL 0.0015, MTP kept)
get llmfan46/Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-GGUF Qwen3.6-35B-A3B-uncensored-heretic-Native-MTP-Preserved-BF16.gguf q36-heretic-bf16.gguf \
 && quant q36-heretic-bf16.gguf imatrix-unsloth-qwen3.6-35b-a3b.gguf qwen36-udq3kxl-tensor-types.txt Qwen3.6-35B-A3B-heretic-UD-Q3_K_XL.gguf Q3_K_M \
 && rm -f q36-heretic-bf16.gguf && echo "$(date +%T) removed q36 bf16"
# 2) Qwen3.8-27B Heretic (darrellbest, refusals 98→0/100, KL 0.0465)
get unsloth/Qwen3.8-27B-GGUF imatrix_unsloth.gguf imatrix-unsloth-qwen3.8-27b.gguf
get darrellbest/Qwen3.8-27B-Heretic-GGUF Qwen3.8-27B-Heretic-BF16.gguf q38-heretic-bf16.gguf \
 && quant q38-heretic-bf16.gguf imatrix-unsloth-qwen3.8-27b.gguf qwen38-udq2kxl-tensor-types.txt Qwen3.8-27B-heretic-UD-Q2_K_XL.gguf Q2_K \
 && rm -f q38-heretic-bf16.gguf && echo "$(date +%T) removed q38 bf16"
echo "$(date +%T) PIPELINE-DONE"; df -h / | tail -1
