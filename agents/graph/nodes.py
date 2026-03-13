"""
LangGraph Graph Nodes — thin wrappers for state machine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Each function is a LangGraph node that takes state, updates one key,
and returns the updated state. No business logic lives here.
"""
from __future__ import annotations

from agents.state import IndiaEngineState
from agents.quant_agent import run_quant_agent
from agents.macro_agent import run_macro_agent
from agents.fundamental_agent import run_fundamental_agent
from agents.prediction_agent import run_prediction_agent
from agents.emotion_agent import run_emotion_agent
from agents.fno_agent import run_fno_agent
from agents.devils_advocate_agent import run_devils_advocate_agent
from agents.risk_node import run_risk_node
from agents.orchestrator_agent import run_orchestrator_agent


# Re-export node callables for workflow.py
node_quant         = run_quant_agent
node_macro         = run_macro_agent
node_fundamental   = run_fundamental_agent
node_prediction    = run_prediction_agent
node_emotion       = run_emotion_agent
node_fno           = run_fno_agent
node_da            = run_devils_advocate_agent
node_risk          = run_risk_node
node_orchestrator  = run_orchestrator_agent


def merge_parallel_states(states: list[IndiaEngineState]) -> IndiaEngineState:
    """
    Merge multiple state dicts from parallel node executions.
    Each parallel node writes a distinct key → simple dict merge.
    """
    if not states:
        return IndiaEngineState()
    merged: IndiaEngineState = dict(states[0])  # type: ignore[assignment]
    for s in states[1:]:
        merged.update(s)
    return merged
