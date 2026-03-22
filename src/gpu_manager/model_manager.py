"""
model_manager.py
Apple-style AI model lifecycle: nothing active unless needed.

Rules baked in — non-negotiable:
  • Only ONE HIVE model in VRAM at a time, ever.
  • NVIDIA is OFF by default. Wakes only when a model is requested.
  • Models unload after IDLE_TIMEOUT_SECONDS of no use.
  • Gaming mode evicts any loaded model instantly.
  • exit_gaming_mode() does NOT pre-load anything. Wait for a real request.
  • RAM cache (mmap files) is free — models live there at zero power cost.
"""

import logging
import time

logger = logging.getLogger("luminos-ai.gpu_manager.model_manager")

IDLE_TIMEOUT_SECONDS = 300  # 5 minutes

HIVE_MODELS: dict = {
    "nexus": {"size_gb": 4.0, "role": "orchestrator"},
    "bolt":  {"size_gb": 4.0, "role": "code"},
    "nova":  {"size_gb": 4.0, "role": "writing"},
    "eye":   {"size_gb": 4.0, "role": "vision"},
}


class ModelManager:
    """
    Tracks which (if any) HIVE model is currently in NVIDIA VRAM.
    All actual llama.cpp calls are stubs — real loading is wired in Phase P1-04.
    State tracking and policy enforcement are fully real.
    """

    def __init__(self):
        self.active_model:   str | None   = None   # name of loaded model
        self.last_used:      float | None = None   # monotonic timestamp
        self.gaming_mode:    bool         = False
        self.nvidia_active:  bool         = False  # NVIDIA powered up?

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unload_current(self) -> str | None:
        """
        Unload whatever model is currently active.
        Returns the name of the unloaded model, or None if nothing was loaded.
        """
        if self.active_model is None:
            return None
        name = self.active_model
        # Real stub: actual llama.cpp unload would go here
        logger.info(f"MODEL UNLOAD: {name} evicted from NVIDIA VRAM")
        self.active_model  = None
        self.last_used     = None
        self.nvidia_active = False
        return name

    def _load(self, model_name: str, quantization: str, layers: int) -> None:
        """
        Load a model into NVIDIA VRAM.
        Real stub: actual llama.cpp load would go here.
        """
        logger.info(
            f"MODEL LOAD: {model_name} ({quantization}) — {layers} GPU layers "
            f"(NVIDIA waking)"
        )
        self.active_model  = model_name
        self.last_used     = time.monotonic()
        self.nvidia_active = True

    # ------------------------------------------------------------------
    # VRAM math
    # ------------------------------------------------------------------

    def calculate_gpu_layers(self, model_size_gb: float, free_vram_mb: float) -> int:
        """
        How many transformer layers to offload to GPU given available VRAM.
        Returns 0 if VRAM is too tight — model runs on CPU only.
        """
        free_gb = free_vram_mb / 1024.0
        if free_gb >= model_size_gb:
            return 32
        elif free_gb >= model_size_gb * 0.6:
            return int(32 * 0.6)
        elif free_gb >= model_size_gb * 0.3:
            return int(32 * 0.3)
        else:
            return 0

    def select_quantization(self, free_vram_mb: float) -> str:
        """
        Choose the highest quality quantization that fits in available VRAM.
        Falls back to 1b (smallest) as last resort.
        """
        if free_vram_mb >= 7000:
            return "Q8"
        elif free_vram_mb >= 4000:
            return "Q4"
        elif free_vram_mb >= 2000:
            return "Q2"
        else:
            return "1b"

    # ------------------------------------------------------------------
    # Public model lifecycle
    # ------------------------------------------------------------------

    def request_model(self, model_name: str, free_vram_mb: float) -> dict:
        """
        A task needs model_name. Load it, evicting any different model first.

        Args:
            model_name:   One of: nexus, bolt, nova, eye
            free_vram_mb: Current free NVIDIA VRAM in MB (from vram_monitor)

        Returns:
            {
                "loaded":             str,       # model now in VRAM
                "quantization":       str,
                "layers":             int,
                "previously_unloaded": str|None, # evicted model name
            }
        """
        if model_name not in HIVE_MODELS:
            return {
                "loaded":              None,
                "quantization":        None,
                "layers":              0,
                "previously_unloaded": None,
                "error":               f"Unknown model: {model_name}",
            }

        previously_unloaded: str | None = None

        # Evict if a different model is loaded
        if self.active_model is not None and self.active_model != model_name:
            previously_unloaded = self._unload_current()

        # Already loaded — just refresh timestamp
        if self.active_model == model_name:
            self.last_used     = time.monotonic()
            self.nvidia_active = True
            model_info  = HIVE_MODELS[model_name]
            quant       = self.select_quantization(free_vram_mb)
            layers      = self.calculate_gpu_layers(model_info["size_gb"], free_vram_mb)
            logger.info(f"MODEL HIT: {model_name} already loaded — timestamp refreshed")
            return {
                "loaded":              model_name,
                "quantization":        quant,
                "layers":              layers,
                "previously_unloaded": previously_unloaded,
            }

        # Load requested model
        model_info = HIVE_MODELS[model_name]
        quant      = self.select_quantization(free_vram_mb)
        layers     = self.calculate_gpu_layers(model_info["size_gb"], free_vram_mb)
        self._load(model_name, quant, layers)

        return {
            "loaded":              model_name,
            "quantization":        quant,
            "layers":              layers,
            "previously_unloaded": previously_unloaded,
        }

    def release_model_if_idle(self) -> dict:
        """
        Idle-timeout check — call this on a periodic timer (every ~60s).
        Unloads the active model if it has not been used for IDLE_TIMEOUT_SECONDS.

        Returns:
            {"unloaded": str|None, "reason": str}
        """
        if self.active_model is None:
            return {"unloaded": None, "reason": "no model loaded"}

        if self.last_used is None:
            unloaded = self._unload_current()
            return {"unloaded": unloaded, "reason": "no usage timestamp — evicted"}

        idle_seconds = time.monotonic() - self.last_used
        if idle_seconds >= IDLE_TIMEOUT_SECONDS:
            unloaded = self._unload_current()
            return {
                "unloaded": unloaded,
                "reason":   f"idle for {idle_seconds:.0f}s (>{IDLE_TIMEOUT_SECONDS}s) — NVIDIA idled",
            }

        return {
            "unloaded": None,
            "reason":   f"still active ({idle_seconds:.0f}s idle, timeout={IDLE_TIMEOUT_SECONDS}s)",
        }

    # ------------------------------------------------------------------
    # Gaming mode
    # ------------------------------------------------------------------

    def enter_gaming_mode(self) -> dict:
        """
        A game is starting. Evict model immediately. Free NVIDIA for gaming.

        Returns:
            {
                "unloaded":       str|None,
                "vram_freed_mb":  float,
                "message":        str,
            }
        """
        # Estimate freed VRAM based on model size if we know what was loaded
        vram_freed_mb = 0.0
        if self.active_model and self.active_model in HIVE_MODELS:
            vram_freed_mb = HIVE_MODELS[self.active_model]["size_gb"] * 1024.0

        unloaded = self._unload_current()
        self.gaming_mode = True
        logger.info("GAMING MODE: entered — NVIDIA freed for gaming")

        return {
            "unloaded":      unloaded,
            "vram_freed_mb": vram_freed_mb,
            "message":       "NVIDIA freed for gaming",
        }

    def exit_gaming_mode(self) -> dict:
        """
        Game finished. Return to idle state.
        Does NOT pre-load any model — wait for a real task to request one.

        Returns:
            {"message": str}
        """
        self.gaming_mode = False
        logger.info("GAMING MODE: exited — NVIDIA idle until needed")
        return {"message": "Gaming mode off — NVIDIA idle until needed"}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """
        Current manager state snapshot.

        Returns:
            {
                "active_model":           str|None,
                "gaming_mode":            bool,
                "nvidia_active":          bool,
                "idle_timeout_seconds":   int,
                "seconds_since_last_use": float|None,
            }
        """
        seconds_idle = None
        if self.last_used is not None:
            seconds_idle = round(time.monotonic() - self.last_used, 1)

        return {
            "active_model":           self.active_model,
            "gaming_mode":            self.gaming_mode,
            "nvidia_active":          self.nvidia_active,
            "idle_timeout_seconds":   IDLE_TIMEOUT_SECONDS,
            "seconds_since_last_use": seconds_idle,
        }
