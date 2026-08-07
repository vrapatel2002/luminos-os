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
        llm = Llama(model_path=..., n_gpu_layers=99, ...)

``n_gpu_layers`` must be high. The override is subtractive: llama.cpp assigns
every layer to the GPU first, then this pulls the matching tensors back to RAM.
With a low ``n_gpu_layers`` you get whole layers on the CPU *and* the experts on
the CPU, which is the opposite of the point.

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

# Expert FFN tensors in every MoE llama.cpp supports: blk.N.ffn_gate_exps.weight
# and its up/down siblings. Matched with std::regex_search, ECMAScript syntax --
# this is a regex, not a glob. The shared expert (ffn_*_shexp) is deliberately
# NOT matched: it runs on every single token, so it belongs on the GPU.
EXPERT_TENSORS = r"\.ffn_(gate|up|down)_exps\."

_ggml = None


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


@contextlib.contextmanager
def moe_cpu_offload(patterns=(EXPERT_TENSORS,), enabled=True):
    """Within this block, any model loaded keeps `patterns` tensors in RAM.

    Scoped on purpose: a global monkeypatch would silently change the behaviour
    of every other model this process loads, including the little Qwen3-4B that
    wants to be entirely on the card.
    """
    if not enabled:
        yield
        return

    from llama_cpp import _internals

    arr, _keepalive = _build_override_array(list(patterns))
    original = _internals.LlamaModel.__init__

    def patched(self, *, path_model, params, verbose=True):
        params.tensor_buft_overrides = ctypes.cast(arr, ctypes.c_void_p)
        self._luminos_override_keepalive = (arr, _keepalive)
        return original(self, path_model=path_model, params=params, verbose=verbose)

    _internals.LlamaModel.__init__ = patched
    try:
        yield
    finally:
        _internals.LlamaModel.__init__ = original


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


def _selftest(model_path, n_ctx=4096, n_gpu_layers=99, pattern=EXPERT_TENSORS):
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
    print(f"VERDICT: PASS - {moved:.0f} MiB moved off the GPU into RAM")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} MODEL.gguf [n_ctx] [n_gpu_layers] [regex]")
    sys.exit(_selftest(
        sys.argv[1],
        n_ctx=int(sys.argv[2]) if len(sys.argv) > 2 else 4096,
        n_gpu_layers=int(sys.argv[3]) if len(sys.argv) > 3 else 99,
        pattern=sys.argv[4] if len(sys.argv) > 4 else EXPERT_TENSORS,
    ))
