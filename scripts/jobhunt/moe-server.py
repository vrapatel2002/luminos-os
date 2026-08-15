#!/usr/bin/env python
"""Run llama-cpp-python's OpenAI-compatible server with MoE experts in system RAM.
[CHANGE: claude-code | 2026-08-07] DECISION 58 — links luminos_moe_offload into the
serving path so an MoE bigger than the card can actually be served.

Drop-in for `python -m llama_cpp.server`: takes the exact same arguments, adds
nothing to the command line. The only difference is that the model's expert banks
are pinned to system RAM before the model loads.

WHY A LAUNCHER AND NOT A FLAG: llama_cpp.server builds its Llama object deep inside
LlamaProxy, so there is no argument to thread an override through. The offload works
by patching LlamaModel.__init__, which has to happen before that construction. So we
enter the context manager, hand control to the server's own main(), and never exit —
the process IS the scope.

WHY THE PATTERN IS NOT THE DEFAULT: `keep_on_gpu=3` is a MEASURED optimum, not a
guess, and it is not monotonic — 4 is worse than 3, because past ~4.9 GB the
allocator starts fighting the KV cache. Re-measure per model; do not assume 3
transfers. Override with LLM_MOE_KEEP.

NGL IS FORCED TO ALL by the module and that is correct, not a bug: the override is
SUBTRACTIVE. llama.cpp puts every layer on the GPU first, then this pulls the
matching tensors back to RAM. Passing --n_gpu_layers 32 here would leave whole
layers AND the experts in RAM, which is backwards.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from luminos_moe_offload import moe_cpu_offload, expert_pattern  # noqa: E402

KEEP = int(os.environ.get("LLM_MOE_KEEP", "3"))
# [CHANGE: claude-code | 2026-08-14] The second model gets its OWN keep count.
# `keep` is a property of the model file, not of this process: a bigger quant has
# bigger layers, so the same number buys more VRAM and less RAM. Serving two
# quants of the same architecture under one number means one of them is wrong.
# Defaults to KEEP, so single-model setups are unchanged.
MODEL2 = os.environ.get("LLM_MODEL2", "")
KEEP2 = int(os.environ.get("LLM_MOE_KEEP2", str(KEEP)))


def _as_text(path_model):
    """path_model arrives from llama-cpp-python as BYTES, not str."""
    if isinstance(path_model, bytes):
        return path_model.decode("utf-8", "replace")
    return path_model


def _keep_for(path_model):
    """How many layers of experts to leave on the card, for THIS model."""
    path_model = _as_text(path_model)
    if MODEL2 and os.path.realpath(path_model) == os.path.realpath(MODEL2):
        return KEEP2
    return KEEP


def _patterns_for(path_model):
    keep = _keep_for(path_model)
    pattern = expert_pattern(keep_on_gpu=keep)
    print(f"[moe] {os.path.basename(_as_text(path_model))}: experts -> system RAM, "
          f"keeping the first {keep} layers on the card", file=sys.stderr)
    print(f"[moe] pattern: {pattern}", file=sys.stderr)
    return (pattern,)


def main():
    print(f"[moe] keep={KEEP}" + (f", keep2={KEEP2} for {os.path.basename(MODEL2)}"
                                  if MODEL2 else ""), file=sys.stderr)
    from llama_cpp.server.__main__ import main as server_main
    # A CALLABLE, not a fixed tuple: the server may swap models at runtime and
    # each one needs its own pattern. Evaluated per load.
    with moe_cpu_offload(patterns=_patterns_for):
        server_main()


if __name__ == "__main__":
    main()
