"""LangGraph agent for TrackFlow — RAG pipeline with read-only incident/inventory tools.

Graph structure
---------------
receive_validate → route_classify ─┬─ (rag) → retrieve_context ─┬─ has chunks → generate_answer ─┐
                                    │                            └─ empty → fallback ─────────────┤
                                    ├─ (ticket) → lookup_incident ─┬─ both → retrieve_context ───┤
                                    │                              └─ only ticket → assemble_final ┤
                                    ├─ (inventory) → lookup_inventory → assemble_final ──────────┤
                                    └─ (unknown/invalid) → fallback → assemble_final ────────────┤
                                                                                                  ↓
                                                                                           assemble_final

Every transition uses real LangGraph conditional edges with a ``path_map``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langgraph.graph import StateGraph

from services.agent.state import AgentState
from services.agent.trace import (
    _normalise_outcome,
    finish_run,
    save_run_node,
    start_run,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

_INCIDENT_KEYWORDS = frozenset({
    "incident", "ticket", "issue", "problem", "complaint",
    "trf-", "tracking", "parcel", "package",
    "lost", "damage", "delayed",
})

_INVENTORY_KEYWORDS = frozenset({
    "inventory", "stock", "sku", "product", "warehouse",
    "quantity", "available", "products", "supply",
})

# Write-intent keywords — no mutating MCP tools exist; these are rejected.
_WRITE_KEYWORDS = frozenset({
    "create", "update", "delete", "remove", "modify", "change",
    "close", "resolve", "cancel", "edit", "add", "new",
})

_RAG_KEYWORDS = frozenset({
    "policy", "sla", "guarantee", "coverage", "carrier",
    "return", "storage", "discount", "pricing", "fee",
    "rate", "terms", "condition", "contract", "obligation",
    "deadline", "trackflow", "company", "service",
    "liability", "responsibility",
})


def _normalise(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9 ]+", " ", text).strip().casefold()


def _tokenise(text: str) -> frozenset[str]:
    """Lower-case words, stripping punctuation."""
    return frozenset(_normalise(text).split())


def classify_question(question: str) -> str:
    """Return one of ``"rag"``, ``"ticket"``, ``"inventory"``, ``"both"``, ``"unknown"``.

    Write-intent requests (create/update/delete/close) are classified as
    ``"write_intent"`` so they are routed to a clear rejection message
    instead of hitting read-only tools.
    """
    tokens = _tokenise(question)
    is_incident = bool(tokens & _INCIDENT_KEYWORDS)
    is_inventory = bool(tokens & _INVENTORY_KEYWORDS)
    is_rag = bool(tokens & _RAG_KEYWORDS)
    is_write = bool(tokens & _WRITE_KEYWORDS)

    # Write-intent check comes first: a user asking to "create a ticket" or
    # "delete incident TRF-123" must get a clear rejection, not a RAG answer.
    if is_write and (is_incident or is_inventory):
        return "write_intent"

    # Combined incident+RAG → "both" (lookup incident, then retrieve context)
    if is_incident and is_rag:
        return "both"

    # RAG questions (policy, SLA, returns, storage, etc.) take priority over
    # inventory because common words like "product" appear in both domains.
    if is_rag:
        return "rag"

    if is_incident:
        return "ticket"
    if is_inventory:
        return "inventory"
    return "unknown"


# ---------------------------------------------------------------------------
# Node implementations  (one function per graph node)
# ---------------------------------------------------------------------------


def receive_validate(state: AgentState) -> AgentState:
    """Validate input and set run_id.

    **Trace-first ordering**: the run record is created *before* validation
    so that even blank/invalid questions leave a durable trace in the
    SQLite store for offline evaluation.
    """
    run_id = start_run(state)
    state["run_id"] = run_id

    question = (state.get("question") or "").strip()
    if not question:
        state["error"] = "BLANK_QUESTION"
        _trace_node(state, "receive_validate", status="completed",
                    details={"error": "BLANK_QUESTION"})
        return state

    state["error"] = None
    _trace_node(state, "receive_validate", status="completed")
    return state


def route_classify(state: AgentState) -> AgentState:
    """Classify the question and update state."""
    if state.get("error"):
        _trace_node(state, "route_classify", status="skipped")
        return state
    classification = classify_question(state.get("question", ""))
    state["classification"] = classification
    _trace_node(state, "route_classify", status="completed",
                details={"classification": classification})
    return state


rejection_prompt = (
    "I can only answer read-only questions about TrackFlow policies, "
    "incidents/tickets, and inventory. I cannot create, update, or "
    "delete tickets or inventory. Please contact your TrackFlow "
    "administrator or use the TrackFlow back-office to make changes."
)


def reject_write_intent(state: AgentState) -> AgentState:
    """Reject write-intent requests with a clear explanation."""
    state["answer"] = rejection_prompt
    state["classification"] = "write_intent"
    _trace_node(state, "reject_write_intent", status="completed")
    return state


def lookup_incident(state: AgentState) -> AgentState:
    """Look up an incident/ticket by ID via the bounded 5-second tool.

    Uses ``services.agent.tools.incident.lookup_incident_by_id`` which
    enforces a 5-second wall-clock timeout via ``ThreadPoolExecutor``.
    """
    if state.get("error"):
        _trace_node(state, "lookup_incident", status="skipped")
        return state

    question = state.get("question", "")
    incident_match = re.search(
        r"(?:incident|ticket)\s*[:\s#]*([a-zA-Z0-9_-]{8,64})",
        question, re.IGNORECASE,
    )
    if not incident_match:
        state["incident_result"] = None
        state["error"] = "NO_INCIDENT_ID"
        _trace_node(state, "lookup_incident", status="completed",
                    details={"error": "NO_INCIDENT_ID"})
        return state

    incident_id = incident_match.group(1)
    try:
        from services.agent.tools.incident import lookup_incident_by_id, IncidentToolError

        result = lookup_incident_by_id(incident_id)
        state["incident_result"] = result
        if result is None:
            state["error"] = "INCIDENT_NOT_FOUND"
        _trace_node(state, "lookup_incident", status="completed",
                    details={"incident_id": incident_id,
                             "found": result is not None})
    except IncidentToolError:
        state["incident_result"] = None
        state["error"] = "INCIDENT_LOOKUP_FAILED"
        _trace_node(state, "lookup_incident", status="error",
                    details={"error": "INCIDENT_LOOKUP_FAILED"})
    except Exception as exc:
        logger.error("Incident lookup failed unexpectedly: %s", exc)
        state["incident_result"] = None
        state["error"] = "INCIDENT_LOOKUP_FAILED"
        _trace_node(state, "lookup_incident", status="error",
                    details={"error": str(exc)})
    return state


def lookup_inventory(state: AgentState) -> AgentState:
    """Look up inventory/products via the bounded typed tool."""
    if state.get("error"):
        _trace_node(state, "lookup_inventory", status="skipped")
        return state

    try:
        from services.agent.tools.inventory import (
            InventoryToolError,
            lookup_inventory,
        )

        result = lookup_inventory()
        state["inventory_result"] = result
        _trace_node(state, "lookup_inventory", status="completed",
                    details={"product_count": len(result)})
    except InventoryToolError:
        state["inventory_result"] = []
        state["error"] = "INVENTORY_LOOKUP_FAILED"
        _trace_node(state, "lookup_inventory", status="error",
                    details={"error": "INVENTORY_LOOKUP_FAILED"})
    except Exception as exc:
        logger.error("Inventory lookup failed unexpectedly: %s", exc)
        state["inventory_result"] = []
        state["error"] = "INVENTORY_LOOKUP_FAILED"
        _trace_node(state, "lookup_inventory", status="error",
                    details={"error": str(exc)})
    return state


def retrieve_context(state: AgentState) -> AgentState:
    """Retrieve relevant chunks from the knowledge base."""
    if state.get("error"):
        _trace_node(state, "retrieve_context", status="skipped")
        return state

    try:
        from data.process.rag import retrieve, RetrievedChunk

        chunks = retrieve(state["question"])
        state["retrieved_chunks"] = [
            {"score": c.score, **({"payload": c.payload} if hasattr(c, "payload") else {})}
            for c in (chunks or [])
        ]
        _trace_node(state, "retrieve_context", status="completed",
                    details={"chunk_count": len(chunks or [])})
    except Exception as exc:
        logger.warning("Retrieval failed: %s", exc)
        state["retrieved_chunks"] = []
        _trace_node(state, "retrieve_context", status="error",
                    details={"error": str(exc)})
    return state


def generate_answer(state: AgentState) -> AgentState:
    """Generate a grounded answer from retrieved chunks."""
    if state.get("error"):
        _trace_node(state, "generate_answer", status="skipped")
        return state

    chunks = state.get("retrieved_chunks") or []
    if not chunks:
        state["generated_answer"] = ""
        _trace_node(state, "generate_answer", status="completed",
                    details={"reason": "no_chunks"})
        return state

    try:
        from data.pipelines.rag import OpenAICompatibleGenerationProvider, generate_answer as gen
        from data.process.rag import RetrievedChunk

        hydrated = [
            RetrievedChunk(score=c["score"], payload=c.get("payload", {}))
            for c in chunks
        ]
        provider = OpenAICompatibleGenerationProvider.from_env()
        answer = gen(state["question"], hydrated, provider)
        state["generated_answer"] = answer
        _trace_node(state, "generate_answer", status="completed",
                    details={"answer_length": len(answer)})
    except Exception as exc:
        logger.error("Answer generation failed: %s", exc)
        state["generated_answer"] = None
        state["error"] = "GENERATION_FAILED"
        _trace_node(state, "generate_answer", status="error",
                    details={"error": str(exc)})
    return state


def fallback(state: AgentState) -> AgentState:
    """Set a fallback message when the question cannot be handled."""
    if state.get("error") in (None, "BLANK_QUESTION"):
        state["answer"] = (
            "I'm not sure how to help with that. Please ask about "
            "TrackFlow policies (returns, storage, SLA), "
            "incidents/tickets, or inventory/products."
        )
    _trace_node(state, "fallback", status="completed")
    return state


def assemble_final(state: AgentState) -> AgentState:
    """Assemble the final answer from whichever branches executed.

    If a preceding node (e.g. *fallback* or *reject_write_intent*) already
    wrote a complete answer, the existing answer is preserved.
    """
    if state.get("error"):
        messages = {
            "BLANK_QUESTION": "I need a question to work with. Please provide details.",
            "NO_INCIDENT_ID": "Please provide an incident or ticket ID (e.g. 'trf-abc123').",
            "INCIDENT_NOT_FOUND": "No incident found with that ID.",
            "INCIDENT_LOOKUP_FAILED": "The incident service is temporarily unavailable. Please try again later.",
            "INVENTORY_LOOKUP_FAILED": "The inventory service is temporarily unavailable. Please try again later.",
            "GENERATION_FAILED": "I was unable to generate an answer. Please try rephrasing your question.",
        }
        state["answer"] = messages.get(state["error"], "Something went wrong. Please try again.")
        _finish_run(state)
        return state

    # Preserve answers from fallback or reject_write_intent nodes
    existing = state.get("answer")
    classification = state.get("classification")
    if existing and classification in ("unknown", "write_intent"):
        _finish_run(state)
        return state

    parts: list[str] = []

    gen_answer = state.get("generated_answer")
    if gen_answer:
        parts.append(gen_answer)

    incident = state.get("incident_result")
    if incident:
        parts.append(
            f"**Incident details**\n"
            f"- **ID:** {incident.get('id', 'N/A')}\n"
            f"- **Title:** {incident.get('title', 'N/A')}\n"
            f"- **Status:** {incident.get('status', 'N/A')}\n"
            f"- **Category:** {incident.get('category', 'N/A')}\n"
            f"- **Branch:** {incident.get('branch', 'N/A')}\n"
            f"- **Description:** {incident.get('description', 'N/A')}"
        )

    inventory = state.get("inventory_result")
    if inventory:
        rows = "\n".join(
            f"- **{p['name']}** ({p['sku']}, {p['warehouse']}): {p['current_stock']} units"
            for p in inventory
        )
        parts.append(f"**Current inventory**\n{rows}")

    if not parts:
        if classification == "unknown":
            parts.append(
                "I'm not sure how to help with that. Please ask about "
                "TrackFlow policies (returns, storage, SLA), "
                "incidents/tickets, or inventory/products."
            )
        else:
            parts.append("No information was found for your query.")

    state["answer"] = "\n\n".join(parts)
    _finish_run(state)
    return state


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _trace_node(state: AgentState, node_name: str, status: str = "completed",
                details: dict[str, Any] | None = None) -> None:
    """Log a node visit to the trace store."""
    run_id = state.get("run_id")
    if run_id:
        save_run_node(run_id, node_name, status=status, details=details)


def _finish_run(state: AgentState) -> None:
    """Finalise the trace run."""
    run_id = state.get("run_id")
    if run_id:
        finish_run(run_id, state)


# ---------------------------------------------------------------------------
# Conditional routing functions (return a node name string)
# ---------------------------------------------------------------------------


def _classify_router(state: AgentState) -> str:
    """Route from ``route_classify`` to the appropriate branch."""
    c = state.get("classification", "unknown")
    if c == "write_intent":
        return "reject_write_intent"
    if c == "rag":
        return "retrieve_context"
    if c in ("ticket", "both"):
        return "lookup_incident"
    if c == "inventory":
        return "lookup_inventory"
    return "fallback"


def _after_incident_router(state: AgentState) -> str:
    """After incident lookup, route to RAG if classification was ``\"both\"``."""
    if state.get("classification") == "both":
        return "retrieve_context"
    return "assemble_final"


def _retrieve_router(state: AgentState) -> str:
    """After retrieval, skip generation if no chunks were found."""
    chunks = state.get("retrieved_chunks")
    if chunks:
        return "generate_answer"
    return "fallback"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_agent() -> StateGraph:
    """Construct and return the agent ``StateGraph`` (uncompiled).

    Calling ``.compile(checkpointer=...)`` on the returned graph yields a
    ``CompiledStateGraph`` ready for ``.invoke(state, config=...)``.
    """
    builder = StateGraph(AgentState)

    # ── Register nodes ───────────────────────────────────────────────────────
    builder.add_node("receive_validate", receive_validate)
    builder.add_node("route_classify", route_classify)
    builder.add_node("reject_write_intent", reject_write_intent)
    builder.add_node("lookup_incident", lookup_incident)
    builder.add_node("lookup_inventory", lookup_inventory)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("fallback", fallback)
    builder.add_node("assemble_final", assemble_final)

    # ── Entry point ──────────────────────────────────────────────────────────
    builder.set_entry_point("receive_validate")

    # ── receive → classify (unconditional) ───────────────────────────────────
    builder.add_edge("receive_validate", "route_classify")

    # ── classify → conditional branches ──────────────────────────────────────
    builder.add_conditional_edges(
        "route_classify",
        _classify_router,
        {
            "reject_write_intent": "reject_write_intent",
            "retrieve_context": "retrieve_context",
            "lookup_incident": "lookup_incident",
            "lookup_inventory": "lookup_inventory",
            "fallback": "fallback",
        },
    )

    # ── lookup_incident → after-ticket conditional ───────────────────────────
    builder.add_conditional_edges(
        "lookup_incident",
        _after_incident_router,
        {
            "retrieve_context": "retrieve_context",
            "assemble_final": "assemble_final",
        },
    )

    # ── lookup_inventory → assemble (unconditional) ──────────────────────────
    builder.add_edge("lookup_inventory", "assemble_final")

    # ── retrieve → after-retrieval conditional ────────────────────────────────
    builder.add_conditional_edges(
        "retrieve_context",
        _retrieve_router,
        {
            "generate_answer": "generate_answer",
            "fallback": "fallback",
        },
    )

    # ── generate → assemble ──────────────────────────────────────────────────
    builder.add_edge("generate_answer", "assemble_final")

    # ── reject / fallback → assemble ─────────────────────────────────────────
    builder.add_edge("reject_write_intent", "assemble_final")
    builder.add_edge("fallback", "assemble_final")

    # ── Finished ─────────────────────────────────────────────────────────────
    builder.set_finish_point("assemble_final")

    return builder