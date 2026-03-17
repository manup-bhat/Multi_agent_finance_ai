"""
Central LLM router for local, Groq, and Gemini workloads.

Implements four routing patterns:
  - Hard routing for low-risk local preprocessing
  - Cascade routing for selected Groq agent tasks
  - Failover across model tiers and providers
  - Budget-aware routing that degrades gracefully through the day
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

import structlog

from config.settings import get_settings
from utils.gemini_client import gemini_client
from utils.groq_client import groq_client
from utils.ollama_client import MAX_TOKENS, PROMPTS, _chat as ollama_chat, normalise_ticker

logger = structlog.get_logger(__name__)

BudgetStage = Literal["normal", "economy", "emergency", "survival"]

_STAGE_ORDER: dict[BudgetStage, int] = {
    "normal": 0,
    "economy": 1,
    "emergency": 2,
    "survival": 3,
}


@dataclass(frozen=True)
class AgentProfile:
    required_sections: tuple[str, ...]
    fast_first: bool
    primary_role: Literal["fast", "primary", "reasoning"] = "primary"
    min_chars: int = 120
    local_thinking: bool = False


@dataclass(frozen=True)
class RoutingPlan:
    provider: Literal["local", "groq"]
    strategy: Literal["single", "cascade"]
    initial_role: Literal["fast", "primary", "reasoning"]
    escalation_role: Literal["fast", "primary", "reasoning"] | None = None
    use_local_thinking: bool = False


AGENT_PROFILES: dict[str, AgentProfile] = {
    "quant_agent": AgentProfile(
        required_sections=("QUANT VERDICT", "STRENGTH", "KEY SIGNALS", "CONFIDENCE"),
        fast_first=True,
        min_chars=100,
    ),
    "macro_agent": AgentProfile(
        required_sections=("MACRO VERDICT", "FII SIGNAL", "VIX REGIME", "CONFIDENCE"),
        fast_first=False,
        primary_role="primary",
        min_chars=130,
        local_thinking=True,
    ),
    "fundamental_agent": AgentProfile(
        required_sections=(
            "FUNDAMENTAL VERDICT",
            "KEY NEWS",
            "SEBI/REGULATORY",
            "CONFIDENCE",
        ),
        fast_first=True,
        min_chars=100,
    ),
    "prediction_agent": AgentProfile(
        required_sections=(
            "PREDICTION VERDICT",
            "PRICE TARGET P50",
            "CONFIDENCE BAND",
            "CONFIDENCE",
        ),
        fast_first=True,
        min_chars=110,
    ),
    "emotion_agent": AgentProfile(
        required_sections=(
            "EMOTION VERDICT",
            "INDIA FEAR/GREED",
            "CONTRARIAN SIGNAL",
            "CONFIDENCE",
        ),
        fast_first=True,
        min_chars=90,
    ),
    "fno_agent": AgentProfile(
        required_sections=("F&O VERDICT", "MAX PAIN", "RECOMMENDED STRATEGY", "CONFIDENCE"),
        fast_first=True,
        min_chars=120,
    ),
    "devils_advocate_agent": AgentProfile(
        required_sections=(
            "CONTRARIAN VERDICT",
            "INDIA-SPECIFIC TAIL RISKS",
            "WHEN WOULD I FLIP",
            "CONFIDENCE",
        ),
        fast_first=False,
        primary_role="reasoning",
        min_chars=130,
        local_thinking=True,
    ),
}


class LLMBudgetTracker:
    """Thread-safe daily usage tracker persisted on disk."""

    def __init__(
        self,
        path: str | Path | None = None,
        groq_daily_token_budget: int | None = None,
        gemini_daily_call_budget: int | None = None,
    ):
        cfg = get_settings()
        self._path = Path(path or cfg.llm_budget_state_path)
        self._groq_daily_token_budget = max(
            1, groq_daily_token_budget or cfg.groq_daily_token_budget
        )
        self._gemini_daily_call_budget = max(
            1, gemini_daily_call_budget or cfg.gemini_daily_call_budget
        )
        self._economy_threshold = cfg.groq_budget_economy_threshold
        self._emergency_threshold = cfg.groq_budget_emergency_threshold
        self._survival_threshold = cfg.groq_budget_survival_threshold
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _new_state(self) -> dict[str, Any]:
        return {
            "date": date.today().isoformat(),
            "groq_calls": 0,
            "groq_prompt_tokens": 0,
            "groq_completion_tokens": 0,
            "groq_total_tokens": 0,
            "gemini_calls": 0,
            "last_updated": datetime.utcnow().isoformat(timespec="seconds"),
        }

    def _load_locked(self) -> dict[str, Any]:
        if not self._path.exists():
            return self._new_state()
        try:
            state = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("llm_budget_tracker.corrupt_state", path=str(self._path))
            return self._new_state()
        if state.get("date") != date.today().isoformat():
            return self._new_state()
        merged = self._new_state()
        merged.update(state)
        return merged

    def _save_locked(self, state: dict[str, Any]) -> None:
        state["last_updated"] = datetime.utcnow().isoformat(timespec="seconds")
        self._path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._load_locked())

    def record_groq_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        *,
        estimated: bool = False,
    ) -> None:
        with self._lock:
            state = self._load_locked()
            state["groq_calls"] += 1
            state["groq_prompt_tokens"] += max(0, int(prompt_tokens))
            state["groq_completion_tokens"] += max(0, int(completion_tokens))
            state["groq_total_tokens"] += max(
                0, int(prompt_tokens) + int(completion_tokens)
            )
            state["last_groq_model"] = model
            state["last_groq_usage_estimated"] = estimated
            self._save_locked(state)

    def record_gemini_call(self, model: str) -> None:
        with self._lock:
            state = self._load_locked()
            state["gemini_calls"] += 1
            state["last_gemini_model"] = model
            self._save_locked(state)

    def groq_usage_ratio(self) -> float:
        state = self.snapshot()
        return min(1.0, state["groq_total_tokens"] / self._groq_daily_token_budget)

    def gemini_usage_ratio(self) -> float:
        state = self.snapshot()
        return min(1.0, state["gemini_calls"] / self._gemini_daily_call_budget)

    def _ratio_to_stage(self, ratio: float) -> BudgetStage:
        if ratio >= self._survival_threshold:
            return "survival"
        if ratio >= self._emergency_threshold:
            return "emergency"
        if ratio >= self._economy_threshold:
            return "economy"
        return "normal"

    def groq_stage(self) -> BudgetStage:
        return self._ratio_to_stage(self.groq_usage_ratio())

    def gemini_stage(self) -> BudgetStage:
        return self._ratio_to_stage(self.gemini_usage_ratio())


class LLMRouter:
    def __init__(self, budget_tracker: LLMBudgetTracker | None = None):
        self._settings = get_settings()
        self.budget_tracker = budget_tracker or LLMBudgetTracker()

    def usage_snapshot(self) -> dict[str, Any]:
        snapshot = self.budget_tracker.snapshot()
        snapshot["groq_stage"] = self.budget_tracker.groq_stage()
        snapshot["gemini_stage"] = self.budget_tracker.gemini_stage()
        return snapshot

    def format_ta_to_text(self, ta_values: dict[str, Any]) -> str:
        user_message = json.dumps(ta_values, ensure_ascii=True, sort_keys=True)
        result = self._call_groq_text(
            system_prompt=PROMPTS["ta_format"],
            user_message=user_message,
            model_role="fast",
            max_tokens=MAX_TOKENS["ta_format"],
            temperature=0.0,
        )
        if self._is_valid_ta_summary(result):
            return result
        return self._deterministic_ta_summary(ta_values)

    def extract_json(self, raw_text: str, schema_example: str = "") -> str:
        user_message = raw_text[:1500]
        if schema_example:
            user_message = f"Schema example: {schema_example}\nText: {user_message}"

        result = self._call_groq_text(
            system_prompt=PROMPTS["json"],
            user_message=user_message,
            model_role="fast",
            max_tokens=max(MAX_TOKENS["json"], 120),
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        data = self._coerce_json_dict(result)
        if data is None:
            local_result = self._call_local_text(
                system_prompt=PROMPTS["json"],
                user_message=user_message,
                max_tokens=max(MAX_TOKENS["json"], 120),
            )
            data = self._coerce_json_dict(local_result)
        if data is None:
            return result or "{}"

        if "ticker" in data and data["ticker"]:
            data["ticker"] = normalise_ticker(str(data["ticker"]))
        return json.dumps(data, ensure_ascii=True)

    def preprocess_news(self, articles: list[dict[str, Any]]) -> str:
        if not articles:
            return ""
        combined = "\n".join(
            f"- {article.get('title', '')}: {str(article.get('summary', ''))[:150]}"
            for article in articles[:5]
        )
        result = self._call_local_text(
            system_prompt=PROMPTS["news"],
            user_message=combined,
            max_tokens=MAX_TOKENS["news"],
        )
        if not result:
            result = "\n".join(
                f"- {article.get('title', 'Market update')}"
                for article in articles[:5]
                if article.get("title")
            )
        return self._trim_news_summary(result)

    def route_agent_call(
        self,
        task: str,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> str:
        profile = AGENT_PROFILES.get(task)
        if profile is None:
            return self._call_groq_text(
                system_prompt=system_prompt,
                user_message=user_message,
                model_role="primary",
                max_tokens=max_tokens,
                temperature=temperature,
            ) or self._call_local_text(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
            )

        plan = self._select_agent_plan(task, profile)
        logger.info(
            "llm_router.agent_route",
            task=task,
            provider=plan.provider,
            strategy=plan.strategy,
            budget_stage=self.budget_tracker.groq_stage(),
            initial_model=self._model_name(plan.initial_role),
            escalation_model=(
                self._model_name(plan.escalation_role)
                if plan.escalation_role is not None
                else None
            ),
        )

        if plan.provider == "local":
            return self._call_local_text(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
                use_thinking=plan.use_local_thinking,
            )

        if plan.strategy == "cascade":
            first = self._call_groq_text(
                system_prompt=system_prompt,
                user_message=user_message,
                model_role=plan.initial_role,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if self._accept_fast_agent_output(
                profile=profile,
                text=first,
                strict_confidence=True,
            ):
                return first

            second = self._call_groq_text(
                system_prompt=system_prompt,
                user_message=user_message,
                model_role=plan.escalation_role or profile.primary_role,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return second or first or self._call_local_text(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
                use_thinking=profile.local_thinking,
            )

        first = self._call_groq_text(
            system_prompt=system_prompt,
            user_message=user_message,
            model_role=plan.initial_role,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if first:
            return first
        return self._call_local_text(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            use_thinking=plan.use_local_thinking,
        )

    def route_orchestrator_call(
        self,
        system_prompt: str,
        user_message: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> str:
        stage = self._max_stage(
            self.budget_tracker.groq_stage(),
            self.budget_tracker.gemini_stage(),
        )
        preferred_model = (
            self._settings.gemini_model
            if stage in {"normal", "economy"}
            else self._settings.gemini_model_fast
        )
        logger.info(
            "llm_router.orchestrator_route",
            budget_stage=stage,
            model=preferred_model,
        )

        for model_name in self._gemini_fallback_chain(preferred_model):
            if not model_name:
                continue
            try:
                return self._call_gemini_text(
                    model_name=model_name,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as exc:
                logger.warning(
                    "llm_router.gemini_failed",
                    model=model_name,
                    error=str(exc),
                )

        groq_role: Literal["fast", "primary", "reasoning"] = (
            "primary" if stage in {"normal", "economy"} else "fast"
        )
        groq_fallback = self._call_groq_text(
            system_prompt=system_prompt,
            user_message=user_message,
            model_role=groq_role,
            max_tokens=min(max_tokens, self._settings.groq_max_tokens),
            temperature=temperature,
        )
        if groq_fallback:
            return groq_fallback

        return self._call_local_text(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=min(max_tokens, 1024),
            use_thinking=True,
        )

    def _select_agent_plan(self, task: str, profile: AgentProfile) -> RoutingPlan:
        stage = self.budget_tracker.groq_stage()
        if not self._has_groq_key():
            return RoutingPlan(
                provider="local",
                strategy="single",
                initial_role="fast",
                use_local_thinking=profile.local_thinking,
            )

        if stage == "survival":
            return RoutingPlan(
                provider="local",
                strategy="single",
                initial_role="fast",
                use_local_thinking=profile.local_thinking,
            )

        if stage == "emergency":
            return RoutingPlan(
                provider="groq",
                strategy="single",
                initial_role="fast",
                use_local_thinking=profile.local_thinking,
            )

        if stage == "economy":
            if task in {"macro_agent", "devils_advocate_agent"}:
                return RoutingPlan(
                    provider="groq",
                    strategy="single",
                    initial_role=profile.primary_role,
                    use_local_thinking=profile.local_thinking,
                )
            return RoutingPlan(
                provider="groq",
                strategy="single",
                initial_role="fast",
                use_local_thinking=profile.local_thinking,
            )

        if profile.fast_first:
            return RoutingPlan(
                provider="groq",
                strategy="cascade",
                initial_role="fast",
                escalation_role=profile.primary_role,
                use_local_thinking=profile.local_thinking,
            )

        return RoutingPlan(
            provider="groq",
            strategy="single",
            initial_role=profile.primary_role,
            use_local_thinking=profile.local_thinking,
        )

    def _accept_fast_agent_output(
        self,
        *,
        profile: AgentProfile,
        text: str,
        strict_confidence: bool,
    ) -> bool:
        if not text or text.startswith("[AGENT_ERROR]"):
            return False
        upper_text = text.upper()
        if any(section not in upper_text for section in profile.required_sections):
            return False
        if len(text.strip()) < profile.min_chars:
            return False

        confidence = self._extract_confidence_label(text)
        if strict_confidence and confidence == "LOW":
            return False
        return True

    def _extract_confidence_label(self, text: str) -> str:
        match = re.search(
            r"CONFIDENCE[^:\n]*:\s*(HIGH|MEDIUM|LOW)",
            text,
            re.IGNORECASE,
        )
        return (match.group(1).upper() if match else "")

    def _call_groq_text(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model_role: Literal["fast", "primary", "reasoning"],
        max_tokens: int,
        temperature: float,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        model_name = self._model_name(model_role)
        try:
            response = groq_client.chat_completion(
                messages=messages,
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )
            content = (response.get("content") or "").strip()
            usage = response.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens") or self._approx_tokens(
                f"{system_prompt}\n{user_message}"
            )
            completion_tokens = usage.get("completion_tokens") or self._approx_tokens(content)
            estimated = not bool(usage.get("total_tokens"))
            self.budget_tracker.record_groq_usage(
                model=response.get("model", model_name),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated=estimated,
            )
            return content
        except Exception as exc:
            logger.warning(
                "llm_router.groq_failed",
                model=model_name,
                error=str(exc),
            )
            return ""

    def _call_local_text(
        self,
        *,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        use_thinking: bool = False,
    ) -> str:
        return ollama_chat(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            use_thinking=use_thinking,
        ).strip()

    def _call_gemini_text(
        self,
        *,
        model_name: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        response = gemini_client.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        used_model = str(response.get("model") or model_name)
        self.budget_tracker.record_gemini_call(used_model)
        return str(response.get("content") or "").strip()

    def _gemini_fallback_chain(self, preferred_model: str) -> list[str]:
        if preferred_model == self._settings.gemini_model_fast:
            return [self._settings.gemini_model_fast]
        return [self._settings.gemini_model, self._settings.gemini_model_fast]

    def _deterministic_ta_summary(self, ta_values: dict[str, Any]) -> str:
        rsi = self._to_float(ta_values.get("RSI") or ta_values.get("rsi"))
        adx = self._to_float(ta_values.get("ADX") or ta_values.get("adx"))
        macd = self._to_float(
            ta_values.get("MACD_hist")
            or ta_values.get("macd_hist")
            or ta_values.get("macd")
        )

        if rsi is None:
            momentum = "Momentum is mixed with no reliable RSI reading."
        elif rsi >= 70:
            momentum = f"RSI at {rsi:.1f} signals stretched bullish momentum."
        elif rsi <= 30:
            momentum = f"RSI at {rsi:.1f} signals oversold conditions and rebound risk."
        elif rsi >= 55:
            momentum = f"RSI at {rsi:.1f} supports a mildly bullish momentum profile."
        elif rsi <= 45:
            momentum = f"RSI at {rsi:.1f} points to soft momentum and seller control."
        else:
            momentum = f"RSI at {rsi:.1f} suggests balanced momentum without an extreme."

        if macd is not None:
            if macd > 0:
                momentum += f" MACD histogram remains positive at {macd:.2f}."
            elif macd < 0:
                momentum += f" MACD histogram remains negative at {macd:.2f}."

        if adx is None:
            trend = "Trend strength is unclear because ADX is unavailable."
        elif adx >= 25:
            trend = f"ADX at {adx:.1f} confirms a strong directional trend."
        elif adx >= 18:
            trend = f"ADX at {adx:.1f} points to a developing trend but not a decisive one."
        else:
            trend = f"ADX at {adx:.1f} suggests a range-bound or weak-trend market."

        return f"{momentum} {trend}"

    def _is_valid_ta_summary(self, text: str) -> bool:
        if not text:
            return False
        sentences = [part.strip() for part in re.split(r"[.!?]+", text) if part.strip()]
        return 1 < len(sentences) <= 3 and len(text) <= 350

    def _coerce_json_dict(self, text: str) -> dict[str, Any] | None:
        if not text:
            return None
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None

    def _trim_news_summary(self, text: str) -> str:
        raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
        lines: list[str] = []
        for line in raw_lines:
            clean = re.sub(r"^[-*•]\s*", "", line).strip()
            if not clean:
                continue
            if not clean.endswith("."):
                clean += "."
            lines.append(f"- {clean}")
            if len(lines) == 5:
                break

        if not lines:
            fragments = [
                fragment.strip()
                for fragment in re.split(r"[.!?]+", text)
                if fragment.strip()
            ]
            lines = [f"- {fragment}." for fragment in fragments[:5]]

        trimmed = "\n".join(lines)
        return trimmed[:1000].rstrip()

    def _model_name(self, role: Literal["fast", "primary", "reasoning"] | None) -> str | None:
        if role is None:
            return None
        if role == "fast":
            return self._settings.groq_model_fast
        if role == "reasoning":
            return self._settings.groq_model_reasoning or self._settings.groq_model_primary
        return self._settings.groq_model_primary

    def _max_stage(self, left: BudgetStage, right: BudgetStage) -> BudgetStage:
        return left if _STAGE_ORDER[left] >= _STAGE_ORDER[right] else right

    def _has_groq_key(self) -> bool:
        return any(key.strip() for key in groq_client.keys)

    def _approx_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _to_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


llm_router = LLMRouter()
