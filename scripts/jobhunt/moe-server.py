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


def main():
    pattern = expert_pattern(keep_on_gpu=KEEP)
    print(f"[moe] experts -> system RAM, keeping the first {KEEP} layers on the card",
          file=sys.stderr)
    print(f"[moe] pattern: {pattern}", file=sys.stderr)
    from llama_cpp.server.__main__ import main as server_main
    with moe_cpu_offload(patterns=(pattern,)):
        server_main()


if __name__ == "__main__":
    main()
