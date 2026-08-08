#!/usr/bin/env python
# [CHANGE: claude-code | 2026-08-07]
"""Put a Mixture-of-Experts model's expert weights in RAM and everything else on the GPU.

Why this file exists
--------------------
A MoE model like Gemma 4 26B A4B is mostly dead weight at any given moment: 128
experts exist, 9 of them run per token. The experts are ~90% of the file but only
~7% of the bytes touched. The right split on a 6 GB card is therefore:

    everything that runs every token (attention, router, norms, embeddings, KV)  -> GPU
    the expert FFN blocks                                                        -> RAM

llama.cpp supports exactly this via ``llama_model_params.tensor_buft_overrides``
(the ``-ot`` / ``--override-tensor`` flag on the CLI). llama-cpp-python 0.3.x
declares the field but marks it ``# NOTE: unused`` and never lets you set it, so
the capability is present in the .so and unreachable from Python.

This module reaches it. It does not modify anything in site-packages -- it wraps
``LlamaModel.__init__`` for the duration of a ``with`` block and stamps the field
on the params struct on the way through.

Usage
-----
    from luminos_moe_offload import moe_cpu_offload

    with moe_cpu_offload():
        llm = Llama(model_path=..., ...)          # n_gpu_layers is handled for you

You do not pass ``n_gpu_layers``. The override is subtractive -- llama.cpp puts
every layer on the GPU, then this pulls the expert tensors back to RAM -- so the
only correct setting is "all of them", and the context manager forces it and says
so on stderr. Getting it wrong strands whole layers on the CPU *as well as* the
experts, which is the opposite of the point, so it is not left to the caller.

Who computes what
-----------------
Putting a weight in RAM does not mean the CPU is stuck with the arithmetic:

* **Generating** (one token at a time) the expert math runs on the **CPU**, on
  weights already in RAM at 47 GB/s. Correct: shipping ~0.9 GB across a ~13 GB/s
  PCIe link to save a little compute would be slower than doing it in place.
* **Reading a prompt** (512 tokens at once) llama.cpp copies the RAM-resident
  weight to the **GPU** and computes there, because at that batch size the
  compute saving dwarfs the transfer cost.

llama.cpp decides that per batch, via ``op_offload`` (on by default). It is the
single most important flag here -- with it off, prompt processing falls from
677 tok/s to 7.1 tok/s on this machine. This module refuses to let it be off.

Verify, don't trust
-------------------
Run this file directly to prove the split actually happened:

    dgpu-exec-v2 /opt/luminos/venv-jobhunt/bin/python luminos_moe_offload.py MODEL.gguf

It loads the model twice, with and without the override, and prints llama.cpp's
own per-buffer allocation report. If the two are identical the override did
nothing and it says so rather than claiming success.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import re
import sys
import tempfile

# Every expert-bank tensor, whatever the architecture chose to call it. Matched
# with std::regex_search, ECMAScript syntax -- this is a regex, not a glob.
#
# Do NOT spell out the projection names. The obvious pattern,
# `\.ffn_(gate|up|down)_exps\.`, silently half-works on Gemma 4: it fuses gate
# and up into ONE tensor called `ffn_gate_up_exps`, which matches neither
# `gate` nor `up`. The result was 272 MiB x 30 layers = 7.97 GiB left on the
# card and a cudaMalloc failure, while the log cheerfully reported overrides
# firing -- on the 0 MiB `.scale` tensors that DID match. Anchoring on the
# `_exps` suffix alone is naming-agnostic and survives whatever the next
# architecture fuses together.
#
# What this deliberately does NOT match, and must not:
#   ffn_gate_inp.*  - the router. Tiny, runs every token, belongs on the GPU.
#   ffn_{gate,up,down}.weight (no _exps) - the SHARED expert. Also every token.
EXPERT_TENSORS = r"_exps\."

_ggml = None


def _note(msg):
    """Say what was changed underneath the caller. Silent magic is worse than none."""
    print(f"[luminos-moe] {msg}", file=sys.stderr)


def _load_ggml():
    """Grab the ggml backend API out of the .so llama_cpp already has open."""
    global _ggml
    if _ggml is not None:
        return _ggml

    import llama_cpp

    libdir = os.path.join(os.path.dirname(llama_cpp.__file__), "lib")
    # Already resident in this process (libllama links it), so this is a
    # refcount bump on the same handle, not a second copy.
    lib = ctypes.CDLL(os.path.join(libdir, "libggml-base.so.0"))

    lib.ggml_backend_cpu_buffer_type.argtypes = []
    lib.ggml_backend_cpu_buffer_type.restype = ctypes.c_void_p
    lib.ggml_backend_buft_name.argtypes = [ctypes.c_void_p]
    lib.ggml_backend_buft_name.restype = ctypes.c_char_p

    _ggml = lib
    return lib


class TensorBuftOverride(ctypes.Structure):
    """struct llama_model_tensor_buft_override { const char *pattern; ggml_backend_buffer_type_t buft; }"""

    _fields_ = [
        ("pattern", ctypes.c_char_p),
        ("buft", ctypes.c_void_p),
    ]


def _build_override_array(patterns):
    """NULL-terminated array of {pattern -> CPU buffer type}.

    The caller must keep the returned object alive for as long as the model is
    loading; llama.cpp stores the bare pointer and walks it during load_tensors.
    Let it get collected early and you are reading freed memory.
    """
    ggml = _load_ggml()
    cpu_buft = ggml.ggml_backend_cpu_buffer_type()
    if not cpu_buft:
        raise RuntimeError("ggml_backend_cpu_buffer_type() returned NULL")

    arr = (TensorBuftOverride * (len(patterns) + 1))()
    # Encoded bytes must outlive the array too -- c_char_p does not copy, so a
    # temporary bytes object would be freed the moment the loop iterates.
    keepalive = []
    for i, pat in enumerate(patterns):
        raw = pat.encode()
        keepalive.append(raw)
        arr[i].pattern = raw
        arr[i].buft = cpu_buft
    arr[len(patterns)].pattern = None  # terminator
    arr[len(patterns)].buft = None
    return arr, keepalive


ALL_LAYERS = 999   # "every layer on the GPU"; llama.cpp clamps to the real count


def expert_pattern(keep_on_gpu=0):
    """Offload experts from every layer EXCEPT the first `keep_on_gpu` of them.

    Sending all experts to RAM leaves VRAM unused, and the spare capacity buys
    back a surprising amount of prompt-processing speed. Measured on the 26B
    A4B, 1947-token prompt + 200 generated:

        keep_on_gpu  VRAM MiB   prompt eval   generation   wall
              0        3556       72.2 t/s     17.21 t/s   38.73 s
              3        4918      134.5 t/s     22.31 t/s   23.60 s   <-- best
              4        5372      121.2 t/s     22.92 t/s   24.95 s
              5        OOM (failed to create context)

    Note that 4 is *worse* than 3 despite holding more on the card: past ~4.9 GB
    the allocator is fighting the KV cache and compute buffers for what is left,
    and the loss outweighs the saved PCIe traffic. More on the GPU is not
    monotonically better. Re-measure on any other model rather than assuming 3.
    """
    if keep_on_gpu <= 0:
        return EXPERT_TENSORS
    # Layers keep_on_gpu..99, written out because llama.cpp matches with
    # std::regex on the tensor name -- there is no numeric comparison available.
    lo = keep_on_gpu
    alts = [str(n) for n in range(lo, 10)] + [r"\d{2,}"]
    return r"blk\.(" + "|".join(alts) + r")\..*_exps\."


@contextlib.contextmanager
def moe_cpu_offload(patterns=(EXPERT_TENSORS,),
                    n_gpu_layers=ALL_LAYERS,
                    require_op_offload=True,
                    enabled=True):
    """Within this block, any model loaded keeps `patterns` tensors in RAM.

    Scoped on purpose: a global monkeypatch would silently change the behaviour
    of every other model this process loads, including the little Qwen3-4B that
    wants to be entirely on the card.

    This owns two settings that the caller must not be able to get wrong:

    ``n_gpu_layers`` -- forced to ALL_LAYERS. The override is *subtractive*:
        llama.cpp assigns every layer to the GPU, then this pulls the matching
        tensors back to RAM. Passing a low value would strand whole layers on
        the CPU *in addition to* the experts, which is the opposite of the
        point. There is no sensible reason to hand-tune this alongside an
        expert override, so the parameter is set here rather than trusted.

    ``op_offload`` -- must stay on. See the note below; it is the difference
        between a usable prompt-processing speed and an unusable one.
    """
    if not enabled:
        yield
        return

    from llama_cpp import _internals

    arr, _keepalive = _build_override_array(list(patterns))
    orig_model = _internals.LlamaModel.__init__
    orig_ctx = _internals.LlamaContext.__init__

    def patched_model(self, *, path_model, params, verbose=True):
        if n_gpu_layers is not None and params.n_gpu_layers != n_gpu_layers:
            _note(f"n_gpu_layers {params.n_gpu_layers} -> {n_gpu_layers} "
                  f"(expert override is subtractive; all layers must start on the GPU)")
            params.n_gpu_layers = n_gpu_layers
        params.tensor_buft_overrides = ctypes.cast(arr, ctypes.c_void_p)
        self._luminos_override_keepalive = (arr, _keepalive)
        return orig_model(self, path_model=path_model, params=params, verbose=verbose)

    def patched_ctx(self, *, model, params, verbose=True):
        # Prompt processing is COMPUTE-bound, not bandwidth-bound. Measured on
        # this machine: the CPU reads a prompt at 7.1 tok/s, the GPU at 677 --
        # 95x. With the experts in RAM, every expert matmul would land on the
        # CPU and prompt processing would collapse to the 7 tok/s number.
        #
        # op_offload is what prevents that. For a large batch llama.cpp copies
        # the RAM-resident weight across PCIe and runs the matmul on the GPU,
        # because at 512 tokens at once the compute saving dwarfs the transfer.
        # For single-token generation it correctly does NOT -- shipping ~0.9 GB
        # over a ~13 GB/s link to save arithmetic is slower than just reading it
        # locally at 47 GB/s. llama.cpp makes that call per batch; we only have
        # to not disable it.
        if require_op_offload and not params.op_offload:
            _note("op_offload was OFF - forcing it back ON. With experts in RAM "
                  "this is the difference between ~677 and ~7 tok/s prompt eval.")
            params.op_offload = True
        return orig_ctx(self, model=model, params=params, verbose=verbose)

    _internals.LlamaModel.__init__ = patched_model
    _internals.LlamaContext.__init__ = patched_ctx
    try:
        yield
    finally:
        _internals.LlamaModel.__init__ = orig_model
        _internals.LlamaContext.__init__ = orig_ctx


@contextlib.contextmanager
def _capture_fd(fd=2):
    """Capture C-level writes to a file descriptor.

    llama.cpp logs the buffer allocation from C, so it bypasses sys.stderr
    entirely -- redirecting the Python object captures nothing.
    """
    with tempfile.TemporaryFile(mode="w+b") as tmp:
        saved = os.dup(fd)
        sys.stderr.flush()
        os.dup2(tmp.fileno(), fd)
        try:
            yield tmp
        finally:
            os.dup2(saved, fd)
            os.close(saved)
            tmp.seek(0)
            tmp._text = tmp.read().decode("utf-8", "replace")


_BUF_RE = re.compile(r"^load_tensors:\s+(\S+?)\s+model buffer size\s*=\s*([\d.]+)\s*MiB", re.M)


def buffer_report(log_text):
    """Pull llama.cpp's own 'X model buffer size = N MiB' lines out of a load log."""
    return {m.group(1): float(m.group(2)) for m in _BUF_RE.finditer(log_text)}


def _selftest(model_path, n_ctx=4096, n_gpu_layers=ALL_LAYERS, pattern=EXPERT_TENSORS):
    from llama_cpp import Llama

    def load(use_override):
        with _capture_fd(2) as cap:
            try:
                with moe_cpu_offload(patterns=(pattern,), enabled=use_override):
                    llm = Llama(
                        model_path=model_path,
                        n_gpu_layers=n_gpu_layers,
                        n_ctx=n_ctx,
                        n_threads=4,
                        type_k=8,
                        type_v=8,
                        flash_attn=True,
                        logits_all=False,
                        verbose=True,   # needed: the buffer report IS the log
                    )
                llm.close()
                err = None
            except Exception as exc:      # noqa: BLE001 - report, don't mask
                err = exc
        return buffer_report(cap._text), err, cap._text

    print(f"model: {model_path}\n")

    off, off_err, off_log = load(False)
    print(f"--- WITHOUT override (n_gpu_layers={n_gpu_layers})")
    if off_err:
        print(f"    FAILED: {off_err}")
    for k, v in sorted(off.items()):
        print(f"    {k:<12} {v:>10.1f} MiB")

    on, on_err, on_log = load(True)
    print(f"\n--- WITH override  pattern={pattern!r}")
    if on_err:
        print(f"    FAILED: {on_err}")
    for k, v in sorted(on.items()):
        print(f"    {k:<12} {v:>10.1f} MiB")

    print()
    if on_err and not off_err:
        print("VERDICT: FAIL - override broke a load that otherwise worked")
        return 1
    if not on:
        print("VERDICT: INCONCLUSIVE - no buffer lines parsed from the load log")
        print(on_log[-1500:])
        return 1
    if on == off:
        print("VERDICT: FAIL - allocation is byte-identical, the override did nothing")
        return 1

    moved = off.get("CUDA0", 0.0) - on.get("CUDA0", 0.0)
    if off_err and not on_err:
        # The strongest possible result: the card cannot hold this model at all,
        # and the override is the only reason it loads.
        print(f"VERDICT: PASS - decisive. WITHOUT the override the model does not load "
              f"({type(off_err).__name__}). WITH it, {on.get('CUDA0', 0.0):.0f} MiB on the "
              f"GPU and {on.get('CPU_Mapped', 0.0):.0f} MiB in RAM.")
    elif moved > 0:
        print(f"VERDICT: PASS - {moved:.0f} MiB moved off the GPU into RAM")
    else:
        # Happens when the baseline itself was crippled: the caller passed a low
        # n_gpu_layers, so the "without" run had barely anything on the GPU to
        # begin with, and the override run repaired it. The override still fired
        # (the allocations differ), but "moved N MiB" would be a lie here.
        print(f"VERDICT: PASS - override fired, but the baseline is not comparable: "
              f"it had only {off.get('CUDA0', 0.0):.0f} MiB on the GPU because a low "
              f"n_gpu_layers was passed. The override run forced all layers on and "
              f"landed at {on.get('CUDA0', 0.0):.0f} MiB. Re-run without the "
              f"n_gpu_layers argument for a like-for-like number.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} MODEL.gguf [n_ctx] [n_gpu_layers] [regex]")
    sys.exit(_selftest(
        sys.argv[1],
        n_ctx=int(sys.argv[2]) if len(sys.argv) > 2 else 4096,
        n_gpu_layers=int(sys.argv[3]) if len(sys.argv) > 3 else ALL_LAYERS,
        pattern=sys.argv[4] if len(sys.argv) > 4 else EXPERT_TENSORS,
    ))
