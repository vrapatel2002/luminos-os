"""
src/npu/__init__.py
NPU abstraction layer — single gateway to the AMD XDNA NPU.

All NPU calls in the entire Luminos codebase go through NPUInterface.
Nothing else ever touches the NPU directly.

Usage:
    from npu import NPUInterface, NPUUnavailableError

    npu = NPUInterface()
    if npu.is_available():
        npu.load_model("/opt/luminos/models/sentinel.onnx", "sentinel")
        result = npu.run_sentinel(data)
"""

from .npu_interface import NPUInterface
from .npu_errors import (
    NPUUnavailableError,
    NPUModelNotLoadedError,
    NPUInferenceError,
)
from .mock_npu import MockNPUInterface

__all__ = [
    "NPUInterface",
    "MockNPUInterface",
    "NPUUnavailableError",
    "NPUModelNotLoadedError",
    "NPUInferenceError",
]
