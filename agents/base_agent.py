"""
Base Agent — shared LLM call helper for Groq sub-agents
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All Groq agents share the same pattern:
  1. Load system prompt from agents/prompts/<name>.txt
  2. Build a human message with pre-computed analytics as text
  3. Call Groq Llama 3.3 70B (or fallback to 8B)
  4. Return the text response
  5. Never raise — always return a degraded result on error

Design rules:
  - LLMs receive ALL numbers as pre-formatted text
  - LLMs NEVER compute math — only interpret and synthesize
  - Each agent runs independently (can run in parallel)
"""
from __future__ import annotations

import structlog
from pathlib import Path
from typing import Optional

logger = structlog.get_logger(__name__)

# Prompt files directory
_PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(agent_name: str) -> str:
    """Load system prompt from agents/prompts/<agent_name>.txt"""
    path = _PROMPTS_DIR / f"{agent_name}.txt"
    if not path.exists():
        return f"You are the {agent_name.upper()} agent. Analyze the provided data and give a structured assessment."
    return path.read_text(encoding="utf-8").strip()


def call_groq(
    system_prompt: str,
    user_message: str,
    task: str = "generic_agent",
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> str:
    """
    Call Groq LLM with system + human messages.
    On error, returns a degraded placeholder string (never raises).
    """
    try:
        from utils.llm_router import llm_router

        if model is not None:
            logger.warning(
                "call_groq.explicit_model_bypasses_router",
                task=task,
                model=model,
            )
            from utils.groq_client import groq_client

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            return groq_client.chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        return llm_router.route_agent_call(
            task=task,
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    except Exception as exc:
        logger.warning("groq_call.failed", error=str(exc))
        return f"[AGENT_ERROR] {exc}"


def call_gemini(
    system_prompt: str,
    user_message: str,
    task: str = "orchestrator",
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> str:
    """
    Call Gemini 2.5 Pro (Orchestrator only).
    On error, returns a degraded placeholder string (never raises).
    """
    try:
        from utils.llm_router import llm_router

        if task != "orchestrator":
            logger.warning("call_gemini.unexpected_task", task=task)
        return llm_router.route_orchestrator_call(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    except Exception as exc:
        logger.warning("gemini_call.failed", error=str(exc))
        return f"[ORCHESTRATOR_ERROR] {exc}"
