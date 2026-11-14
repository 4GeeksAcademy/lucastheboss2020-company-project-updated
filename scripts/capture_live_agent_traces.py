"""Capture live agent traces to JSON for offline replay evaluation.

Loads ``backend/.env`` **privately** (no secrets printed, no env files edited),
then runs the compiled agent graph against real Qdrant + LLM + TinyDB and saves
the resulting traces to ``data/eval/live-traces/``.

Each trace includes the final agent state **and** the ordered node execution
log from the SQLite trace store (``services/agent/traces/agent_traces.sqlite``),
enabling offline node-order assertions.

Usage::

    uv run --env-file backend/.env python scripts/capture_live_agent_traces.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── Private env load — no secrets printed, no files modified ───────────
from dotenv import load_dotenv

_env_loaded = load_dotenv("backend/.env", override=False)
assert _env_loaded, "backend/.env not found — cannot capture live evidence"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.checkpoint.memory import InMemorySaver
from services.agent.graph import build_agent
from services.agent.tools.incident import lookup_incident_by_id
from services.incidents.manager_data import get_incident
from services.agent.trace import get_run

OUT_DIR = Path("data/eval/live-traces")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _save_trace(name: str, result: dict) -> None:
    path = OUT_DIR / f"{name}.json"
    # Convert the result to a JSON-safe dict (no LangGraph internals)
    safe = {k: v for k, v in result.items() if not k.startswith("_")}

    # Append node execution order from the SQLite trace store
    run_id = result.get("run_id")
    if run_id:
        run_data = get_run(run_id)
        if run_data and run_data.get("nodes"):
            safe["_node_order"] = [
                {"node_name": n["node_name"], "status": n.get("status")}
                for n in run_data["nodes"]
            ]

    path.write_text(json.dumps(safe, indent=2, default=str))
    print(f"  → saved {path} ({len(safe.get('_node_order', []))} nodes tracked)")


def capture_rag_trace() -> None:
    """Run a policy question through the full RAG pipeline (retrieve + generate)."""
    print("\n=== RAG trace ===")
    sg = build_agent()
    graph = sg.compile(checkpointer=InMemorySaver())
    result = graph.invoke(
        {"question": "What is the return window for a damaged item?"},
        config={"configurable": {"thread_id": "live-capture-rag"}},
    )
    chunks = result.get("retrieved_chunks") or []
    answer = result.get("answer", "")
    classification = result.get("classification")
    print(f"  Classification: {classification}")
    print(f"  Chunks retrieved: {len(chunks)}")
    if chunks:
        payload = chunks[0].get("payload", {})
        print(f"  Top chunk ({payload.get('source_document','?')}/{payload.get('section','?')}): "
              f"{payload.get('text','')[:100]}…")
    print(f"  Answer: {answer[:200]}…" if answer else "  [no answer]")
    assert classification == "rag", f"Expected rag, got {classification!r}"
    assert len(chunks) >= 1, "Expected at least 1 retrieved chunk"
    assert answer and len(answer) > 20, (
        f"Expected a genuine grounded answer, got {len(answer)} chars. "
        "If generation fails, check RAG_API_* vars in backend/.env."
    )
    _save_trace("rag", result)


def capture_incident_trace() -> None:
    """Look up a real seeded incident via the tool and the full graph."""
    print("\n=== Incident trace ===")

    # First, find a real incident ID from TinyDB
    sample_id = None
    raw_data = get_incident("95b5f484-b729-4e40-a149-c023386db302")
    if raw_data:
        sample_id = raw_data.get("id")
    else:
        # Fallback: scan TinyDB for any open incident
        from services.incidents.manager_data import list_incidents
        all_incidents = list_incidents(limit=1)
        if all_incidents:
            sample_id = all_incidents[0].get("id")
    assert sample_id, "No incident found in TinyDB to capture"

    # Tool-only trace
    tool_result = lookup_incident_by_id(sample_id)
    assert tool_result is not None, f"Incident {sample_id} not found by tool"
    print(f"  Tool lookup for {sample_id}: {tool_result['title']} ({tool_result['status']})")

    # Full graph trace
    sg = build_agent()
    graph = sg.compile(checkpointer=InMemorySaver())
    result = graph.invoke(
        {"question": f"Show me incident {sample_id}"},
        config={"configurable": {"thread_id": "live-capture-incident"}},
    )
    inc = result.get("incident_result")
    classification = result.get("classification")
    print(f"  Classification: {classification}")
    print(f"  Incident: {inc['title']} ({inc['status']})" if inc else "  [no incident result]")
    print(f"  Answer: {result.get('answer','')[:200]}…")
    assert classification in ("ticket", "both"), f"Expected ticket/both, got {classification!r}"
    assert inc is not None, "Expected incident_result from graph"
    _save_trace("incident", result)


def capture_both_trace() -> None:
    """A 'both' question: RAG + incident in the same invocation.

    Uses a real incident ID from TinyDB so that the incident-lookup path
    succeeds and the ``_after_incident_router`` forwards to
    ``retrieve_context`` for the RAG side.
    """
    sample_id = None
    raw_data = get_incident("95b5f484-b729-4e40-a149-c023386db302")
    if raw_data:
        sample_id = raw_data.get("id")
    assert sample_id, "No incident found in TinyDB to use for both trace"

    print(f"\n=== Both (RAG + incident) trace (incident={sample_id}) ===")
    sg = build_agent()
    graph = sg.compile(checkpointer=InMemorySaver())
    result = graph.invoke(
        {"question": f"What is the return policy for incident {sample_id}?"},
        config={"configurable": {"thread_id": "live-capture-both"}},
    )
    classification = result.get("classification")
    chunks = result.get("retrieved_chunks") or []
    inc = result.get("incident_result")
    print(f"  Classification: {classification}")
    print(f"  Chunks: {len(chunks)}")
    print(f"  Incident found: {inc is not None}")
    if inc:
        print(f"  Incident: {inc.get('title','?')} ({inc.get('status','?')})")
    if chunks:
        top = chunks[0].get("payload", {})
        print(f"  Top chunk: {top.get('text','')[:100]}…")
    assert classification == "both", f"Expected both, got {classification!r}"
    assert inc is not None, "Expected incident_result for a real incident ID"
    assert len(chunks) >= 1, "Expected RAG chunks for a both-classified query"
    _save_trace("both", result)


if __name__ == "__main__":
    capture_rag_trace()
    capture_incident_trace()
    capture_both_trace()
    print(f"\n✅ All traces saved to {OUT_DIR}")