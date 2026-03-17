import time
from typing import Any

from groq import Groq, RateLimitError
from langchain_groq import ChatGroq
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class GroqFailoverClient:
    """
    Dual-account Groq client.
    Automatically switches to Account 2 when Account 1 hits 429 (rate limit).
    Resets back to Account 1 after 60 seconds.
    """

    def __init__(self):
        cfg = get_settings()
        # Collect all non-empty api keys 
        keys = []
        if cfg.groq_api_key_1: keys.append(cfg.groq_api_key_1)
        if cfg.groq_api_key_2: keys.append(cfg.groq_api_key_2)
        if not keys and cfg.groq_api_key: keys.append(cfg.groq_api_key)

        self.keys = keys if keys else [""]
        
        self.current_index = 0
        self.cooldown_until = [0] * len(self.keys)
        self.model_primary = cfg.groq_model_primary
        self.model_fast    = cfg.groq_model_fast
        self.max_tokens    = cfg.groq_max_tokens
        self.temperature   = cfg.groq_temperature
        self._sync_clients: dict[str, Groq] = {}
        self._langchain_clients: dict[tuple[str, str, int, float], ChatGroq] = {}

    def _get_active_key(self) -> str:
        """Return the first key that is not in cooldown."""
        now = time.time()

        for i in range(len(self.keys)):
            idx = (self.current_index + i) % len(self.keys)
            if now >= self.cooldown_until[idx]:
                self.current_index = idx
                return self.keys[idx]

        # All keys in cooldown — wait for the soonest one
        wait_for = min(self.cooldown_until) - now
        logger.warning(f"All Groq keys in cooldown (total keys: {len(self.keys)}). Waiting {wait_for:.1f}s...")
        time.sleep(max(0.1, wait_for + 1)) # Add 1 second buffer
        self.current_index = 0
        return self.keys[0]

    def _mark_rate_limited(self, key_index: int, cooldown_seconds: int = 60):
        """Put a key in cooldown after hitting 429."""
        self.cooldown_until[key_index] = time.time() + cooldown_seconds
        next_index = (key_index + 1) % len(self.keys)
        logger.warning(
            f"Groq key {key_index + 1} rate limited. "
            f"Switching to key {next_index + 1} for {cooldown_seconds}s."
        )
        self.current_index = next_index

    def get_langchain_llm(self, fast: bool = False, **kwargs) -> ChatGroq:
        """Return a LangChain ChatGroq instance with the active key."""
        key = self._get_active_key()
        model = self.model_fast if fast else self.model_primary
        if kwargs:
            return ChatGroq(
                api_key=key,
                model_name=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                **kwargs
            )
        cache_key = (key, model, self.max_tokens, self.temperature)
        if cache_key not in self._langchain_clients:
            self._langchain_clients[cache_key] = ChatGroq(
                api_key=key,
                model_name=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        return self._langchain_clients[cache_key]

    def _get_sync_client(self, key: str) -> Groq:
        if key not in self._sync_clients:
            self._sync_clients[key] = Groq(api_key=key)
        return self._sync_clients[key]

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send a chat request with automatic failover on 429 and return metadata.
        """
        for attempt in range(len(self.keys)):
            key_index = self.current_index
            key = self._get_active_key()
            
            if not key:
                raise ValueError("No GROQ API key is set.")

            try:
                client = self._get_sync_client(key)
                kwargs: dict[str, Any] = {
                    "model": model or self.model_primary,
                    "messages": messages,
                    "max_tokens": (
                        max_tokens if max_tokens is not None else self.max_tokens
                    ),
                    "temperature": (
                        temperature if temperature is not None else self.temperature
                    ),
                }
                if response_format is not None:
                    kwargs["response_format"] = response_format

                response = client.chat.completions.create(**kwargs)
                usage = getattr(response, "usage", None)
                return {
                    "content": response.choices[0].message.content or "",
                    "model": getattr(response, "model", kwargs["model"]),
                    "usage": {
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                    },
                }

            except RateLimitError:
                self._mark_rate_limited(key_index, cooldown_seconds=60)
                if attempt == len(self.keys) - 1:
                    raise   # both keys exhausted — propagate error

            except Exception as e:
                # Catch any other exception that might be a 429 string wrapper
                if "429" in str(e) or "rate limit" in str(e).lower():
                    self._mark_rate_limited(key_index, cooldown_seconds=60)
                    if attempt == len(self.keys) - 1:
                        raise
                else:
                    logger.error(f"Groq key {key_index + 1} error: {e}")
                    raise

        raise RuntimeError("Groq chat completion failed after exhausting all keys.")

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """
        Send a chat request with automatic failover on 429.
        Retries up to len(self.keys) times before raising.
        """
        result = self.chat_completion(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )
        return result["content"]

# ── Singleton — import this everywhere ────────────────────────────
groq_client = GroqFailoverClient()
