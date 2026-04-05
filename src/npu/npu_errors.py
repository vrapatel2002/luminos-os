"""
src/npu/npu_errors.py
Exception classes for NPU operations.
"""


class NPUUnavailableError(Exception):
    """Raised when the AMD XDNA NPU is not available.

    Callers must catch this and WAIT — never reroute to CPU or GPU.
    """
    pass


class NPUModelNotLoadedError(Exception):
    """Raised when inference is attempted without a loaded model."""
    pass


class NPUInferenceError(Exception):
    """Raised when NPU inference fails at runtime."""
    pass
