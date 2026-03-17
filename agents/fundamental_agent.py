"""
Fundamental Agent — News + SEBI + Corporate Actions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Receives pre-processed text from the sentiment pipeline + news scrapers.
"""
from __future__ import annotations

import structlog

from agents.state import IndiaEngineState
from agents.base_agent import load_prompt, call_groq

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("fundamental_agent")


def _build_rag_context(state: IndiaEngineState) -> str:
    """
    Retrieve optional historical/news context for the fundamental agent.

    If the vector store is empty or unavailable, return an explicit message
    rather than silently pretending that retrieval succeeded.
    """
    try:
        from embeddings import VectorDocument, get_default_vector_store
    except Exception as exc:
        logger.warning("fundamental_agent.rag_import_failed", error=str(exc))
        return "RAG unavailable: embedding modules could not be imported."

    ticker = state.get("ticker", "N/A")
    summary = state.get("fundamental_summary", "")
    raw_documents = state.get("fundamental_documents", []) or []

    try:
        store = get_default_vector_store()
        documents_to_upsert: list[VectorDocument] = []
        for idx, item in enumerate(raw_documents):
            text = str(item.get("text") or item.get("summary") or item.get("headline") or "").strip()
            if not text:
                continue
            documents_to_upsert.append(
                VectorDocument(
                    id=str(item.get("id") or f"{ticker}:{idx}"),
                    text=text,
                    metadata={
                        "ticker": ticker,
                        "source": item.get("source", "runtime"),
                        "date": item.get("date", ""),
                    },
                )
            )
        if documents_to_upsert:
            store.upsert_documents(documents_to_upsert)

        retrieved = store.query(
            f"{ticker} {summary}",
            top_k=3,
            metadata_filter={"ticker": ticker},
        )
        if not retrieved and summary:
            retrieved = store.query(summary, top_k=3)
    except Exception as exc:
        logger.warning("fundamental_agent.rag_query_failed", error=str(exc))
        return "RAG unavailable: vector retrieval failed."

    if not retrieved:
        return "No retrieved context available in the vector store."

    lines = []
    for doc in retrieved:
        source = doc.metadata.get("source", "unknown")
        lines.append(f"- [{source}] {doc.text[:220]}")
    return "\n".join(lines)


def _build_fundamental_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    fundamental = state.get("fundamental_summary", "No fundamental data.")
    rag_context = _build_rag_context(state)
    return (
        f"TICKER: {ticker}\n\n"
        f"=== FUNDAMENTAL DATA (pre-processed) ===\n{fundamental}\n\n"
        f"=== RETRIEVED CONTEXT (RAG) ===\n{rag_context}\n"
    )


def run_fundamental_agent(state: IndiaEngineState) -> dict:
    """LangGraph node: runs Fundamental agent, writes fundamental_analysis to state."""
    logger.info("fundamental_agent.start", ticker=state.get("ticker"))
    context = _build_fundamental_context(state)
    result = call_groq(_PROMPT, context, task="fundamental_agent")
    logger.info("fundamental_agent.done")
    return {"fundamental_analysis": result}
