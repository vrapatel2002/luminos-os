"""
src/npu/mock_npu.py
Mock NPU interface for testing.

Drop-in replacement for NPUInterface that returns realistic fake data.
Used in all unit tests so tests don't need real hardware.
"""

import threading

from .npu_interface import NPUInterface
from .npu_errors import NPUUnavailableError, NPUModelNotLoadedError


class MockNPUInterface(NPUInterface):
    """
    Mock NPU that simulates all operations without real hardware.

    Set mock_available=False to simulate unavailable NPU.
    """

    def __init__(self, mock_available: bool = True):
        super().__init__()
        self._mock_available = mock_available
        self._available = mock_available
        self._driver = "xdna" if mock_available else "none"
        self._models = {}
        self._pause_count = 0
        self._resume_count = 0

    def is_available(self) -> bool:
        return self._mock_available

    def load_model(self, model_path: str, task: str) -> bool:
        if not self._mock_available:
            return False
        self._models[task] = True  # just mark as loaded
        return True

    def run_sentinel(self, data: dict) -> dict:
        if not self._mock_available:
            raise NPUUnavailableError("Mock NPU unavailable")
        if "sentinel" not in self._models:
            raise NPUModelNotLoadedError("Sentinel model not loaded")

        # Wait if router is running
        self._sentinel_paused.wait(timeout=5.0)

        with self._lock:
            self._current_task = "sentinel"

        try:
            # Return realistic mock classification
            syscall_count = len(data.get("syscalls", []))
            if syscall_count > 100:
                classification = "suspicious"
                confidence = 0.72
            elif data.get("is_elevated", False):
                classification = "suspicious"
                confidence = 0.65
            else:
                classification = "normal"
                confidence = 0.95

            return {
                "classification": classification,
                "confidence": confidence,
                "reason": f"Mock NPU: {classification}",
            }
        finally:
            with self._lock:
                self._current_task = None

    def run_router(self, exe_data: dict) -> dict:
        if not self._mock_available:
            raise NPUUnavailableError("Mock NPU unavailable")
        if "router" not in self._models:
            raise NPUModelNotLoadedError("Router model not loaded")

        self._pause_sentinel()

        with self._lock:
            self._current_task = "router"

        try:
            # Return realistic mock routing decision
            if exe_data.get("has_anticheat_strings"):
                layer = "kvm"
                confidence = 0.98
            elif exe_data.get("has_kernel_driver_imports"):
                layer = "firecracker"
                confidence = 0.88
            elif exe_data.get("has_dx12") or exe_data.get("has_dx11"):
                layer = "proton"
                confidence = 0.92
            elif exe_data.get("has_dotnet"):
                layer = "wine"
                confidence = 0.85
            else:
                layer = "proton"
                confidence = 0.75

            return {
                "layer": layer,
                "confidence": confidence,
                "rule_matched": None,
            }
        finally:
            with self._lock:
                self._current_task = None
            self._resume_sentinel()

    def _pause_sentinel(self):
        self._sentinel_paused.clear()
        self._pause_count += 1

    def _resume_sentinel(self):
        self._sentinel_paused.set()
        self._resume_count += 1
