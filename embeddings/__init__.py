"""Embedding and vector-store public API."""

from embeddings.embedding_service import EmbeddingService, get_embedding_service
from embeddings.vector_store import LocalVectorStore, VectorDocument, get_default_vector_store

__all__ = [
    "EmbeddingService",
    "LocalVectorStore",
    "VectorDocument",
    "get_embedding_service",
    "get_default_vector_store",
]
