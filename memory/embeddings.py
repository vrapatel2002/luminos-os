"""Embedding service: vector generation, conversion, and similarity."""

import logging
import struct
import numpy as np

logger = logging.getLogger("hive.memory.embeddings")


class EmbeddingService:
    def __init__(self, ollama_client):
        self.ollama_client = ollama_client

    async def embed_text(self, text: str) -> list[float]:
        """Get embedding vector for a single text string."""
        return await self.ollama_client.embed(text)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts."""
        return await self.ollama_client.embed_batch(texts)

    def vector_to_bytes(self, vector: list[float]) -> bytes:
        """Convert a float vector to bytes for SQLite BLOB storage."""
        # Use numpy for efficient packing (float32 is standard for embeddings)
        return np.array(vector, dtype=np.float32).tobytes()

    def bytes_to_vector(self, blob: bytes) -> list[float]:
        """Convert BLOB back to float vector."""
        # Convert bytes back to numpy array, then to list
        if not blob:
            return []
        arr = np.frombuffer(blob, dtype=np.float32)
        return arr.tolist()

    def cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a, b) / (norm_a * norm_b))

    def find_similar(
        self,
        query_vector: list[float],
        stored_embeddings: list[tuple[int, bytes]],
        top_k: int = 10,
        threshold: float = 0.3,
    ) -> list[tuple[int, float]]:
        """Find most similar vectors from a list of stored embeddings."""
        if not stored_embeddings:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)

        if q_norm == 0:
            return []

        results = []

        # Optimization: matrix multiplication could be used here if stored_embeddings
        # were pre-loaded as a giant matrix, but for now we iterate (slower but safer for memory).
        # For production with 10k+ items, switch to FAISS or full matrix ops.
        for item_id, blob in stored_embeddings:
            if not blob:
                continue
                
            vec = np.frombuffer(blob, dtype=np.float32)
            norm = np.linalg.norm(vec)
            
            if norm == 0:
                similarity = 0.0
            else:
                similarity = float(np.dot(q_vec, vec) / (q_norm * norm))

            if similarity >= threshold:
                results.append((item_id, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
