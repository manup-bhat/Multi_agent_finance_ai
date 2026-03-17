"""
Shared adapter utilities for caching and retryable fetch wrappers.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

import pandas as pd

T = TypeVar("T")


class BaseAdapter:
    """Small shared cache for expensive adapter fetches."""

    _cache_lock = threading.Lock()
    _cache: dict[str, tuple[float, Any]] = {}

    def _cache_key(self, *parts: object) -> str:
        return "|".join(str(part) for part in parts)

    def _get_cached(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= now:
                self._cache.pop(key, None)
                return None
            if isinstance(value, pd.DataFrame):
                return value.copy(deep=True)
            return value

    def _set_cached(self, key: str, value: Any, ttl_seconds: int) -> Any:
        cached_value = value.copy(deep=True) if isinstance(value, pd.DataFrame) else value
        with self._cache_lock:
            self._cache[key] = (time.monotonic() + max(1, ttl_seconds), cached_value)
        if isinstance(value, pd.DataFrame):
            return value.copy(deep=True)
        return value

    def _cached(self, *, key: str, ttl_seconds: int, loader: Callable[[], T]) -> T:
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        value = loader()
        return self._set_cached(key, value, ttl_seconds)
