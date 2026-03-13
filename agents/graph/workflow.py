"""
LangGraph Workflow — 9-Agent India Engine State Machine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Graph topology:
  START
    │
    ├──► quant_agent      ──┐
    ├──► macro_agent      ──┤
    ├──► fundamental_agent──┤  (parallel fan-out)
    ├──► prediction_agent ──┤
    ├──► emotion_agent    ──┤
    └──► fno_agent        ──┘
                             │
                       devils_advocate  (needs all 6 above)
                             │
                          risk_node    (pure Python — no LLM)
                             │
                        orchestrator   (Gemini 2.5 Pro)
                             │
                            END

Note: LangGraph v0.2+ uses `add_node` / `add_edge` / `add_conditional_edges`.
The 6 parallel nodes are connected via separate edges from START.
LangGraph automatically parallelises nodes with no dependency between them.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from agents.state import IndiaEngineState
from agents.graph.nodes import (
    node_quant, node_macro, node_fundamental,
    node_prediction, node_emotion, node_fno,
    node_da, node_risk, node_orchestrator,
)


def build_workflow() -> StateGraph:
    """
    Build and compile the 9-agent LangGraph workflow.

    Returns:
        Compiled Runnable that can be invoked with an IndiaEngineState dict.
    """
    graph = StateGraph(IndiaEngineState)

    # ── Register all nodes ─────────────────────────────────────────
    graph.add_node("quant_agent",         node_quant)
    graph.add_node("macro_agent",         node_macro)
    graph.add_node("fundamental_agent",   node_fundamental)
    graph.add_node("prediction_agent",    node_prediction)
    graph.add_node("emotion_agent",       node_emotion)
    graph.add_node("fno_agent",           node_fno)
    graph.add_node("devils_advocate",     node_da)
    graph.add_node("risk_node",           node_risk)
    graph.add_node("orchestrator",        node_orchestrator)

    # ── Parallel fan-out: START → 6 domain agents ─────────────────
    for agent in [
        "quant_agent", "macro_agent", "fundamental_agent",
        "prediction_agent", "emotion_agent", "fno_agent",
    ]:
        graph.add_edge(START, agent)

    # ── Sequential: all 6 → devil's advocate ──────────────────────
    for agent in [
        "quant_agent", "macro_agent", "fundamental_agent",
        "prediction_agent", "emotion_agent", "fno_agent",
    ]:
        graph.add_edge(agent, "devils_advocate")

    # ── Sequential chain: DA → Risk → Orchestrator → END ──────────
    graph.add_edge("devils_advocate", "risk_node")
    graph.add_edge("risk_node",       "orchestrator")
    graph.add_edge("orchestrator",    END)

    return graph.compile()


# Module-level compiled workflow (import this for use in API/CLI)
workflow = build_workflow()

__all__ = ["workflow", "build_workflow"]
