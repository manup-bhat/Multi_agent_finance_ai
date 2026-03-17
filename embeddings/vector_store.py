"""
Minimal local vector store abstraction for fundamental-analysis RAG.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from config.settings import get_settings
from embeddings.embedding_service import get_embedding_service


@dataclass
class VectorDocument:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


class LocalVectorStore:
    """
    Simple persistent local vector store.

    This intentionally avoids hard dependency on Chroma/Qdrant at runtime while
    still giving the fundamental agent a concrete retrieval surface.
    """

    def __init__(self, path: str | Path | None = None):
        cfg = get_settings()
        base = Path(path or "./storage/vector_store/documents.json")
        self._path = base
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._embedding_service = get_embedding_service()
        self._documents: dict[str, VectorDocument] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            return
        try:
            raw_docs = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            raw_docs = []
        for item in raw_docs:
            doc = VectorDocument(
                id=str(item["id"]),
                text=str(item["text"]),
                metadata=dict(item.get("metadata", {})),
                embedding=item.get("embedding"),
            )
            self._documents[doc.id] = doc

    def _persist(self) -> None:
        payload = [asdict(doc) for doc in self._documents.values()]
        self._path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def upsert_documents(self, documents: list[VectorDocument]) -> None:
        self._ensure_loaded()
        for doc in documents:
            if doc.embedding is None:
                doc.embedding = self._embedding_service.embed_text(doc.text)
            self._documents[doc.id] = doc
        self._persist()

    def query(
        self,
        query_text: str,
        *,
        top_k: int = 3,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[VectorDocument]:
        self._ensure_loaded()
        if not self._documents:
            return []

        query_embedding = self._embedding_service.embed_text(query_text)
        results: list[tuple[float, VectorDocument]] = []
        for doc in self._documents.values():
            if metadata_filter and any(doc.metadata.get(k) != v for k, v in metadata_filter.items()):
                continue
            embedding = doc.embedding or self._embedding_service.embed_text(doc.text)
            score = sum(a * b for a, b in zip(query_embedding, embedding))
            results.append((score, doc))

        results.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in results[:top_k]]


@lru_cache(maxsize=1)
def get_default_vector_store() -> LocalVectorStore:
    return LocalVectorStore()
