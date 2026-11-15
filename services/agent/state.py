"""Minimal typed state for the TrackFlow LangGraph agent.

Explicit fields only — no unnecessary full history.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    """Mutable state flowing through the agent graph.

    Fields are populated by individual nodes; ``answer`` is the final output.
    """

    # ── input ────────────────────────────────────────────────────────────────
    question: str

    # ── routing metadata ─────────────────────────────────────────────────────
    classification: str | None  # "rag" | "ticket" | "inventory" | "both" | "unknown"
    error: str | None           # machine-readable error code or None

    # ── RAG pipeline ─────────────────────────────────────────────────────────
    retrieved_chunks: list[dict[str, Any]] | None  # serialised RetrievedChunk
    generated_answer: str | None                   # raw LLM output (RAG path)

    # ── read-only tool results (Part 2) ──────────────────────────────────────
    incident_result: dict[str, Any] | None
    inventory_result: list[dict[str, Any]] | None

    # ── final output ─────────────────────────────────────────────────────────
    answer: str | None

    # ── run identification (set by trace module) ─────────────────────────────
    run_id: str | None