"""
LangGraph Workflow — 9-Agent India Engine State Machine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Fix (2026-03-21): DA node was connected via a list-edge
    graph.add_edge(DOMAIN_AGENT_NAMES, "devils_advocate")
which can cause DA to fire once per incoming edge in some
LangGraph versions — generating duplicate LLM calls.

Resolution: introduce a lightweight synchronous `join_parallel_agents`
node between the parallel fan-out and the DA node. The join node is a
pure Python no-op dict merge; it fires exactly once after all parallel
agents complete, then emits a single edge to DA.
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


def _join_parallel_agents(state: IndiaEngineState) -> dict:
    """
    Fan-in barrier node.

    Pure Python, zero side-effects, zero LLM calls.
    Executes exactly once after ALL parallel domain agents complete.
    Returns an empty update dict — its sole purpose is to provide a
    single, concrete source node for the edge to devils_advocate.
    """
    logger.debug(
        "join_parallel_agents.done",
        ready_keys=[
            k for k in (
                "quant_analysis", "macro_analysis", "fundamental_analysis",
                "prediction_analysis", "emotion_analysis", "fno_analysis",
            )
            if state.get(k)
        ],
    )
    return {}


def build_workflow():
    """
    Build and compile the LangGraph workflow.

    Graph topology
    ──────────────
    START
      ├─ quant_agent ─┐
      ├─ macro_agent ─┤
      ├─ fundamental_agent ─┤ (parallel fan-out)
      ├─ prediction_agent ──┤
      ├─ emotion_agent ─────┤
      └─ fno_agent ─────────┘
                            ↓
               join_parallel_agents  ← barrier node (pure Python)
                            ↓
               devils_advocate       ← exactly-once LLM call
                            ↓
               risk_node             ← deterministic gating
                            ↓
               validate_orchestrator_inputs
                            ↓
               orchestrator ─→ END
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

    # ── Domain agents (parallel fan-out) ─────────────────────────────
    graph.add_node("quant_agent",        node_quant)
    graph.add_node("macro_agent",        node_macro)
    graph.add_node("fundamental_agent",  node_fundamental)
    graph.add_node("prediction_agent",   node_prediction)
    graph.add_node("emotion_agent",      node_emotion)
    graph.add_node("fno_agent",          node_fno)

    # ── Barrier / sequential nodes ───────────────────────────────────
    graph.add_node("join_parallel_agents",       _join_parallel_agents)
    graph.add_node("devils_advocate",            node_da)
    graph.add_node("risk_node",                  node_risk)
    graph.add_node("validate_orchestrator_inputs", node_validate)
    graph.add_node("orchestrator",               node_orchestrator)

    # ── Edges ────────────────────────────────────────────────────────
    # 1. Fan-out from START → all parallel agents
    for agent in DOMAIN_AGENT_NAMES:
        graph.add_edge(START, agent)

    # 2. Parallel agents → join barrier (all must complete before join fires)
    graph.add_edge(DOMAIN_AGENT_NAMES, "join_parallel_agents")

    # 3. Barrier → DA (exactly once, guaranteed single-edge trigger)
    graph.add_edge("join_parallel_agents",       "devils_advocate")
    graph.add_edge("devils_advocate",            "risk_node")
    graph.add_edge("risk_node",                  "validate_orchestrator_inputs")
    graph.add_edge("validate_orchestrator_inputs", "orchestrator")
    graph.add_edge("orchestrator",               END)

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
