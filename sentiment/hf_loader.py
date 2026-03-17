from __future__ import annotations

import threading

_IMPORT_LOCK = threading.Lock()


def get_transformers_pipeline():
    """
    Resolve Hugging Face's documented pipeline entrypoint under a small import
    lock so concurrent model warm-up does not race the lazy module loader.
    """
    with _IMPORT_LOCK:
        from transformers import pipeline as hf_pipeline
    return hf_pipeline
