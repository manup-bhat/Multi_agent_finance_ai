"""
Gemini client with Pro -> Flash failover.
"""
from __future__ import annotations

from typing import Any

import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class GeminiFailoverClient:
    """Small wrapper around Gemini models with quota-aware fallback."""

    def __init__(self):
        self._settings = get_settings()

    def _build_llm(
        self,
        *,
        model_name: str,
        max_tokens: int,
        temperature: float,
    ):
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=self._settings.google_api_key,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

    def _fallback_chain(self, preferred_model: str | None = None) -> list[str]:
        if preferred_model:
            if preferred_model == self._settings.gemini_model_fast:
                return [self._settings.gemini_model_fast]
            return [preferred_model, self._settings.gemini_model_fast]
        return [self._settings.gemini_model, self._settings.gemini_model_fast]

    def chat(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        from langchain_core.messages import HumanMessage, SystemMessage

        if not self._settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY_NOT_SET")

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
        last_error: Exception | None = None
        for model_name in self._fallback_chain(model):
            try:
                llm = self._build_llm(
                    model_name=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                response = llm.invoke(messages)
                content = response.content if isinstance(response.content, str) else str(response.content)
                return {
                    "content": content.strip(),
                    "model": model_name,
                }
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "gemini_client.model_failed",
                    model=model_name,
                    error=str(exc),
                )
                if not any(token in str(exc).lower() for token in ("429", "quota", "rate limit", "resource exhausted")):
                    if model is not None:
                        break
                    continue

        if last_error is not None:
            raise last_error
        raise RuntimeError("Gemini request failed without a concrete provider error.")


gemini_client = GeminiFailoverClient()
