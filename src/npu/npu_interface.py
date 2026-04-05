"""
src/npu/npu_interface.py
Single gateway to the AMD XDNA NPU.

All NPU calls in the entire codebase go through this one file.
Nothing else ever touches the NPU directly.

Architecture:
  - Sentinel runs continuously at low priority
  - Router bursts on demand at high priority
  - Router pauses Sentinel, runs, then resumes Sentinel
  - If NPU unavailable: raise NPUUnavailableError (caller waits)
  - Never reroute to CPU or GPU — no fallbacks

Driver detection:
  1. /dev/accel/accel0 (or similar XDNA device)
  2. amdxdna kernel module loaded (/proc/modules)
  3. ONNX Runtime has NPU execution provider
"""

import logging
import os
import threading
import time

from .npu_errors import (
    NPUUnavailableError,
    NPUModelNotLoadedError,
    NPUInferenceError,
)

logger = logging.getLogger("luminos-ai.npu")


class NPUInterface:
    """Single gateway to the AMD XDNA NPU."""

    def __init__(self):
        self._available = None          # None = not yet checked
        self._driver = None             # "xdna" or "none"
        self._lock = threading.Lock()
        self._current_task = None       # "sentinel" or "router"
        self._sentinel_paused = threading.Event()
        self._sentinel_paused.set()     # starts unpaused
        self._models = {}               # task -> onnx session
        self._queue_depth = 0

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """
        Returns True if XDNA driver is loaded and NPU is accessible.

        Detection:
          1. Check /dev/accel/accel0 (or similar XDNA device)
          2. Check amdxdna kernel module in /proc/modules
          3. Check ONNX Runtime has VitisAIExecutionProvider

        Result is cached after first check.
        """
        if self._available is not None:
            return self._available

        self._available = False
        self._driver = "none"

        # Check 1: XDNA device node
        xdna_device = self._find_xdna_device()
        if not xdna_device:
            logger.info("NPU: no XDNA device found in /dev/accel/")
            return False

        # Check 2: kernel module
        if not self._check_kernel_module():
            logger.info("NPU: amdxdna kernel module not loaded")
            return False

        # Check 3: ONNX Runtime provider
        if not self._check_onnx_provider():
            logger.info("NPU: VitisAIExecutionProvider not available in ONNX Runtime")
            return False

        self._available = True
        self._driver = "xdna"
        logger.info(f"NPU: AMD XDNA available via {xdna_device}")
        return True

    def status(self) -> dict:
        """
        Returns NPU status dict.

        Keys:
          available: bool
          driver: "xdna" | "none"
          current_task: "sentinel" | "router" | None
          queue_depth: int
        """
        return {
            "available": self.is_available(),
            "driver": self._driver or "none",
            "current_task": self._current_task,
            "queue_depth": self._queue_depth,
        }

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def run_sentinel(self, data: dict) -> dict:
        """
        Run Sentinel classification on NPU.

        Args:
            data: {"syscalls": [...], "process": "name", "pid": int}

        Returns:
            {"classification": "normal"|"suspicious"|"block",
             "confidence": float, "reason": str}

        Queue behavior:
          If router is currently running: wait for it to finish.
          Sentinel is always lower priority than Router.

        Raises:
            NPUUnavailableError: if NPU is not available
            NPUModelNotLoadedError: if sentinel model not loaded
            NPUInferenceError: on inference failure
        """
        if not self.is_available():
            raise NPUUnavailableError("AMD XDNA NPU is not available")

        if "sentinel" not in self._models:
            raise NPUModelNotLoadedError(
                "Sentinel model not loaded — call load_model() first"
            )

        # Wait if router is running (sentinel yields to router)
        self._sentinel_paused.wait(timeout=10.0)

        with self._lock:
            self._current_task = "sentinel"
            self._queue_depth += 1

        try:
            result = self._infer_sentinel(data)
            return result
        except Exception as e:
            raise NPUInferenceError(f"Sentinel inference failed: {e}") from e
        finally:
            with self._lock:
                self._current_task = None
                self._queue_depth = max(0, self._queue_depth - 1)

    def run_router(self, exe_data: dict) -> dict:
        """
        Run compatibility router on NPU.

        Args:
            exe_data: {"path": str, "pe_headers": dict, "apis": list}

        Returns:
            {"layer": "proton"|"wine"|"firecracker"|"kvm",
             "confidence": float, "rule_matched": str|None}

        Queue behavior:
          Pauses sentinel immediately.
          Runs router analysis (typically 1-3 seconds).
          Resumes sentinel when done.

        Raises:
            NPUUnavailableError: if NPU is not available
            NPUModelNotLoadedError: if router model not loaded
            NPUInferenceError: on inference failure
        """
        if not self.is_available():
            raise NPUUnavailableError("AMD XDNA NPU is not available")

        if "router" not in self._models:
            raise NPUModelNotLoadedError(
                "Router model not loaded — call load_model() first"
            )

        # Pause sentinel — router has priority
        self._pause_sentinel()

        with self._lock:
            self._current_task = "router"
            self._queue_depth += 1

        try:
            result = self._infer_router(exe_data)
            return result
        except Exception as e:
            raise NPUInferenceError(f"Router inference failed: {e}") from e
        finally:
            with self._lock:
                self._current_task = None
                self._queue_depth = max(0, self._queue_depth - 1)
            self._resume_sentinel()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, task: str) -> bool:
        """
        Load an ONNX model onto the NPU.

        Args:
            model_path: Path to .onnx model file.
            task: "sentinel" or "router"

        Returns:
            True on success, False on failure.
        """
        if not self.is_available():
            logger.warning(f"NPU: cannot load model for {task} — NPU unavailable")
            return False

        if not os.path.isfile(model_path):
            logger.warning(f"NPU: model not found at {model_path}")
            return False

        try:
            import onnxruntime as ort

            session = ort.InferenceSession(
                model_path,
                providers=["VitisAIExecutionProvider"],
            )
            self._models[task] = session
            logger.info(f"NPU: loaded {task} model from {model_path}")
            return True

        except ImportError:
            logger.warning("NPU: onnxruntime not installed")
            return False
        except Exception as e:
            logger.warning(f"NPU: failed to load {task} model: {e}")
            return False

    # ------------------------------------------------------------------
    # Internal: sentinel pause/resume
    # ------------------------------------------------------------------

    def _pause_sentinel(self):
        """Pause sentinel to yield NPU to router."""
        self._sentinel_paused.clear()
        logger.debug("NPU: sentinel paused for router")

        # Wait for sentinel to release lock if currently running
        start = time.monotonic()
        while self._current_task == "sentinel":
            time.sleep(0.05)
            if time.monotonic() - start > 5.0:
                logger.warning(
                    "NPU: sentinel did not release within 5s — "
                    "proceeding anyway"
                )
                break

    def _resume_sentinel(self):
        """Resume sentinel after router finishes."""
        self._sentinel_paused.set()
        logger.debug("NPU: sentinel resumed")

    # ------------------------------------------------------------------
    # Internal: inference
    # ------------------------------------------------------------------

    def _infer_sentinel(self, data: dict) -> dict:
        """Run sentinel model inference."""
        import numpy as np

        session = self._models["sentinel"]

        # Build feature vector from process signals
        features = np.array([[
            float(len(data.get("syscalls", []))),
            1.0 if data.get("is_elevated", False) else 0.0,
            data.get("cpu_percent", 0.0),
            data.get("memory_mb", 0.0),
            float(data.get("open_files_count", 0)),
            float(data.get("network_connections", 0)),
            float(data.get("child_process_count", 0)),
        ]], dtype=np.float32)

        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: features})

        logits = outputs[0][0]
        probs = self._softmax(logits)
        labels = ["normal", "suspicious", "block"]
        idx = int(probs.argmax())

        return {
            "classification": labels[idx],
            "confidence": round(float(probs[idx]), 3),
            "reason": f"NPU classification: {labels[idx]} "
                      f"(confidence {probs[idx]:.2f})",
        }

    def _infer_router(self, exe_data: dict) -> dict:
        """Run router model inference."""
        import numpy as np

        session = self._models["router"]

        # Build feature vector from exe analysis
        features = np.array([[
            1.0 if exe_data.get("is_pe", False) else 0.0,
            1.0 if exe_data.get("has_win32_imports", False) else 0.0,
            1.0 if exe_data.get("has_kernel_driver_imports", False) else 0.0,
            1.0 if exe_data.get("has_anticheat_strings", False) else 0.0,
            1.0 if exe_data.get("has_dx12", False) else 0.0,
            1.0 if exe_data.get("has_dx11", False) else 0.0,
            1.0 if exe_data.get("has_dotnet", False) else 0.0,
            1.0 if exe_data.get("has_vulkan", False) else 0.0,
            exe_data.get("file_size_mb", 0.0),
        ]], dtype=np.float32)

        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: features})

        logits = outputs[0][0]
        probs = self._softmax(logits)
        layers = ["proton", "wine", "firecracker", "kvm"]
        idx = int(probs.argmax())

        return {
            "layer": layers[idx],
            "confidence": round(float(probs[idx]), 3),
            "rule_matched": None,
        }

    # ------------------------------------------------------------------
    # Internal: detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_xdna_device() -> str | None:
        """Find XDNA accelerator device node."""
        accel_dir = "/dev/accel"
        if not os.path.isdir(accel_dir):
            return None
        for entry in os.listdir(accel_dir):
            path = os.path.join(accel_dir, entry)
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def _check_kernel_module() -> bool:
        """Check if amdxdna kernel module is loaded."""
        try:
            with open("/proc/modules", "r") as f:
                modules = f.read()
            return "amdxdna" in modules
        except OSError:
            return False

    @staticmethod
    def _check_onnx_provider() -> bool:
        """Check if ONNX Runtime has VitisAI execution provider."""
        try:
            import onnxruntime as ort
            return "VitisAIExecutionProvider" in ort.get_available_providers()
        except ImportError:
            return False

    @staticmethod
    def _softmax(x):
        """Stable softmax."""
        import numpy as np
        e = np.exp(x - np.max(x))
        return e / e.sum()
