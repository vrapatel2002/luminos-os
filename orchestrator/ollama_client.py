"""Unified async client for all Ollama API operations."""

import asyncio
import logging
import httpx

logger = logging.getLogger("hive.orchestrator.ollama_client")


class OllamaClient:
    def __init__(self, base_url: str, timeout: int, retry_attempts: int, retry_delay: float, vram_manager):
        self.base_url = base_url
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.vram_manager = vram_manager
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def chat(
        self, 
        model: str, 
        messages: list[dict], 
        temperature: float = 0.7, 
        max_tokens: int = 4096, 
        stream: bool = False,
        options: dict = None
    ) -> dict:
        """Send a chat request to Ollama. Returns the full response dict."""
        await self.vram_manager.ensure_model_loaded(model)

        final_options = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
        if options:
            final_options.update(options)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": final_options,
        }

        last_error = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = await self._client.post("/api/chat", json=payload)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(
                    f"Chat attempt {attempt}/{self.retry_attempts} failed for model '{model}' at /api/chat: {e}"
                )
                if attempt < self.retry_attempts:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Chat request failed for model '{model}' at /api/chat: {e}")
                raise

        raise RuntimeError(
            f"Chat request to model '{model}' at /api/chat failed after {self.retry_attempts} attempts: {last_error}"
        )

    async def generate(self, model: str, prompt: str, temperature: float, max_tokens: int, system: str = None) -> str:
        """Send a generate request to Ollama. Returns the response text string."""
        await self.vram_manager.ensure_model_loaded(model)

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system is not None:
            payload["system"] = system

        last_error = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = await self._client.post("/api/generate", json=payload)
                response.raise_for_status()
                return response.json().get("response", "")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(
                    f"Generate attempt {attempt}/{self.retry_attempts} failed for model '{model}' at /api/generate: {e}"
                )
                if attempt < self.retry_attempts:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Generate request failed for model '{model}' at /api/generate: {e}")
                raise

        raise RuntimeError(
            f"Generate request to model '{model}' at /api/generate failed after {self.retry_attempts} attempts: {last_error}"
        )

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""
        embeddings_model = self.vram_manager._embeddings_model
        await self.vram_manager.ensure_model_loaded(embeddings_model)

        try:
            response = await self._client.post(
                "/api/embeddings",
                json={
                    "model": embeddings_model,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            logger.error(f"Embed request failed for model '{embeddings_model}' at /api/embeddings: {e}")
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts sequentially."""
        results = []
        total = len(texts)
        for i, text in enumerate(texts):
            embedding = await self.embed(text)
            results.append(embedding)
            if (i + 1) % 50 == 0:
                logger.info(f"Embedding progress: {i + 1}/{total}")
        if total >= 50:
            logger.info(f"Embedding complete: {total}/{total}")
        return results

    async def chat_stream(self, model: str, messages: list[dict], temperature: float, max_tokens: int):
        """Send a streaming chat request. Returns an async generator yielding content chunks."""
        await self.vram_manager.ensure_model_loaded(model)

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        last_error = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                async with self._client.stream("POST", "/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.strip():
                            import json
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if chunk.get("done", False):
                                return
                return
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(
                    f"Chat stream attempt {attempt}/{self.retry_attempts} failed for model '{model}' at /api/chat: {e}"
                )
                if attempt < self.retry_attempts:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Chat stream request failed for model '{model}' at /api/chat: {e}")
                raise

        raise RuntimeError(
            f"Chat stream to model '{model}' at /api/chat failed after {self.retry_attempts} attempts: {last_error}"
        )

    async def close(self) -> None:
        """Clean up the httpx client."""
        try:
            await self._client.aclose()
        except Exception as e:
            logger.error(f"Failed to close Ollama client: {e}")
            raise
