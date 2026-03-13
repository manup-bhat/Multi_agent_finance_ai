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

import os
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
    model: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> str:
    """
    Call Groq LLM with system + human messages.
    On error, returns a degraded placeholder string (never raises).
    """
    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import SystemMessage, HumanMessage
        from config.settings import get_settings

        cfg = get_settings()
        if not cfg.groq_api_key:
            return "[GROQ_API_KEY_NOT_SET] Agent unavailable."

        llm = ChatGroq(
            model=model or cfg.groq_model_primary,
            api_key=cfg.groq_api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
        response = llm.invoke(messages)
        return response.content

    except Exception as exc:
        logger.warning("groq_call.failed", error=str(exc))
        return f"[AGENT_ERROR] {exc}"


def call_gemini(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> str:
    """
    Call Gemini 2.5 Pro (Orchestrator only).
    On error, returns a degraded placeholder string (never raises).
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage
        from config.settings import get_settings

        cfg = get_settings()
        if not cfg.google_api_key:
            return "[GOOGLE_API_KEY_NOT_SET] Orchestrator unavailable."

        llm = ChatGoogleGenerativeAI(
            model=cfg.gemini_model,
            google_api_key=cfg.google_api_key,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
        response = llm.invoke(messages)
        return response.content

    except Exception as exc:
        logger.warning("gemini_call.failed", error=str(exc))
        return f"[ORCHESTRATOR_ERROR] {exc}"
