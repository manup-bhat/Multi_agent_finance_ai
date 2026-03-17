"""
LangGraph Workflow — 9-Agent India Engine State Machine
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph

from agents.state import IndiaEngineState

logger = structlog.get_logger(__name__)

DOMAIN_AGENT_NAMES = [
    "quant_agent",
    "macro_agent",
    "fundamental_agent",
    "prediction_agent",
    "emotion_agent",
    "fno_agent",
]


def build_workflow():
    """
    Build and compile the LangGraph workflow.

    Parallel domain agents fan out from START, then join exactly once into the
    devil's advocate node, followed by risk, validation, and orchestration.
    """
    from agents.graph.nodes import (
        node_da,
        node_emotion,
        node_fno,
        node_fundamental,
        node_macro,
        node_orchestrator,
        node_prediction,
        node_quant,
        node_risk,
        node_validate,
    )

    graph = StateGraph(IndiaEngineState)

    graph.add_node("quant_agent", node_quant)
    graph.add_node("macro_agent", node_macro)
    graph.add_node("fundamental_agent", node_fundamental)
    graph.add_node("prediction_agent", node_prediction)
    graph.add_node("emotion_agent", node_emotion)
    graph.add_node("fno_agent", node_fno)
    graph.add_node("devils_advocate", node_da)
    graph.add_node("risk_node", node_risk)
    graph.add_node("validate_orchestrator_inputs", node_validate)
    graph.add_node("orchestrator", node_orchestrator)

    for agent in DOMAIN_AGENT_NAMES:
        graph.add_edge(START, agent)

    graph.add_edge(DOMAIN_AGENT_NAMES, "devils_advocate")
    graph.add_edge("devils_advocate", "risk_node")
    graph.add_edge("risk_node", "validate_orchestrator_inputs")
    graph.add_edge("validate_orchestrator_inputs", "orchestrator")
    graph.add_edge("orchestrator", END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_workflow():
    """Lazy cached workflow factory used by API and module proxy."""
    try:
        return build_workflow()
    except Exception as exc:
        logger.exception("workflow.build_failed", error=str(exc))
        raise RuntimeError(f"Failed to build LangGraph workflow: {exc}") from exc


class _LazyWorkflowProxy:
    """Compatibility proxy that delays workflow compilation until first use."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_workflow(), name)

    def __repr__(self) -> str:
        return "<LazyWorkflowProxy for agents.graph.workflow.get_workflow()>"


workflow = _LazyWorkflowProxy()

__all__ = ["workflow", "build_workflow", "get_workflow"]
