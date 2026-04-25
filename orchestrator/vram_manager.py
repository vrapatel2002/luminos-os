"""VRAM manager for Ollama model loading/unloading within 6GB constraint."""

import logging
import httpx

logger = logging.getLogger("hive.orchestrator.vram_manager")


class VRAMManager:
    def __init__(self, base_url: str, models_config: dict):
        self.base_url = base_url
        self.models_config = models_config
        self.current_loaded: str | None = None
        self._embeddings_model = models_config.get("embeddings", {}).get("name", "nomic-embed-text")
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def ensure_model_loaded(self, model_name: str) -> None:
        """Ensure a model is loaded in VRAM before calling it."""
        try:
            # Embeddings model is small — always safe, never needs swapping
            if model_name == self._embeddings_model:
                return

            # Already loaded — nothing to do
            if model_name == self.current_loaded:
                return

            # A different large model is loaded — unload it first
            if self.current_loaded is not None:
                logger.info(f"Unloading model: {self.current_loaded}")
                await self._client.post(
                    "/api/generate",
                    json={
                        "model": self.current_loaded,
                        "prompt": "",
                        "keep_alive": "0",
                    },
                )
                logger.info(f"Unloaded model: {self.current_loaded}")

            # Load the new model with a lightweight request
            keep_alive = self._get_keep_alive_for_model(model_name)
            logger.info(f"Loading model: {model_name} (keep_alive={keep_alive})")
            await self._client.post(
                "/api/generate",
                json={
                    "model": model_name,
                    "prompt": "",
                    "keep_alive": keep_alive,
                },
            )
            self.current_loaded = model_name
            logger.info(f"Model loaded: {model_name}")

        except Exception as e:
            logger.error(f"Failed to ensure model loaded ({model_name}): {e}")
            raise

    async def unload_all(self) -> None:
        """Force unload whatever is currently loaded. Used during shutdown."""
        try:
            if self.current_loaded is not None:
                logger.info(f"Unloading all — current model: {self.current_loaded}")
                await self._client.post(
                    "/api/generate",
                    json={
                        "model": self.current_loaded,
                        "prompt": "",
                        "keep_alive": "0",
                    },
                )
                logger.info(f"Unloaded model: {self.current_loaded}")
                self.current_loaded = None
        except Exception as e:
            logger.error(f"Failed to unload all models: {e}")
            raise

    def get_loaded_model(self) -> str | None:
        """Return the currently loaded large model name, or None."""
        return self.current_loaded

    async def health_check(self) -> dict:
        """Hit Ollama's /api/tags endpoint to verify it's running and return available models."""
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            model_names = [m["name"] for m in data.get("models", [])]
            logger.info(f"Ollama health check OK — {len(model_names)} models available")
            return {"status": "ok", "models": model_names}
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_keep_alive(self, model_role: str) -> str:
        """Look up the keep_alive value from config for a given role."""
        return self.models_config.get(model_role, {}).get("keep_alive", "5m")

    def _get_keep_alive_for_model(self, model_name: str) -> str:
        """Look up keep_alive by model name (searching through all roles)."""
        for role, cfg in self.models_config.items():
            if isinstance(cfg, dict) and cfg.get("name") == model_name:
                return cfg.get("keep_alive", "5m")
        return "5m"

    async def close(self) -> None:
        """Clean up the httpx client."""
        try:
            await self._client.aclose()
        except Exception as e:
            logger.error(f"Failed to close VRAM manager client: {e}")
            raise
