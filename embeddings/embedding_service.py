"""
Embedding service with a lightweight deterministic fallback.
"""
from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from typing import Iterable

from config.settings import get_settings


class EmbeddingService:
    """
    Embed text for local RAG use.

    Prefers sentence-transformers when available. Falls back to a deterministic
    hashed bag-of-words embedding so the rest of the pipeline still works in
    constrained environments and tests.
    """

    def __init__(self, dimension: int = 384):
        self._settings = get_settings()
        self._dimension = dimension
        self._model = None
        self._initialised = False

    def _initialise_model(self) -> None:
        if self._initialised:
            return
        self._initialised = True
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._settings.embedding_model)
        except Exception:
            self._model = None

    @property
    def dimension(self) -> int:
        self._initialise_model()
        if self._model is not None:
            try:
                return int(self._model.get_sentence_embedding_dimension())
            except Exception:
                return self._dimension
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        self._initialise_model()
        content = (text or "").strip()
        if not content:
            return [0.0] * self.dimension

        if self._model is not None:
            vector = self._model.encode(content, normalize_embeddings=True)
            return [float(value) for value in vector]

        buckets = [0.0] * self.dimension
        for token in content.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            buckets[idx] += sign
        norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
        return [value / norm for value in buckets]

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
