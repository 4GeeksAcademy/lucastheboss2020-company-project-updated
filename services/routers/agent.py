"""FastAPI endpoint for the TrackFlow LangGraph agent.

Synchronous POST endpoint at ``/agent/query`` that invokes the compiled
LangGraph agent with read-only tool routing (RAG, incident lookup,
inventory lookup) and returns a structured answer.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints
from typing import Annotated

from backend.auth import get_current_user
from langgraph.checkpoint.memory import InMemorySaver

from services.agent.graph import build_agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])

# ── Compiled agent (lazy singleton) ──────────────────────────────────────
_compiled_agent = None


def _get_agent():
    """Return the compiled agent singleton.

    Compilation failures (e.g. invalid graph structure) are surfaced here
    as ``RuntimeError`` so the endpoint can return a sanitised 500 instead
    of crashing the uvicorn worker.
    """
    global _compiled_agent
    if _compiled_agent is None:
        try:
            graph = build_agent()
            _compiled_agent = graph.compile(checkpointer=InMemorySaver())
        except Exception as exc:
            logger.exception("Agent compilation failed")
            raise RuntimeError("Agent initialisation failed.") from exc
    return _compiled_agent


# ── Request / response models ────────────────────────────────────────────


class AgentQueryRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AgentQueryResponse(BaseModel):
    answer: str
    classification: str | None = None
    run_id: str | None = None
    elapsed_ms: int | None = None


@router.post(
    "/agent/query",
    response_model=AgentQueryResponse,
    summary="Route a question through the TrackFlow agent (RAG / incident / inventory)",
)
def query_agent(
    body: AgentQueryRequest,
    _user: dict = Depends(get_current_user),
) -> AgentQueryResponse:
    """Classify the question, execute the appropriate tool branch, and return an answer."""
    t0 = time.perf_counter()

    try:
        agent = _get_agent()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The agent encountered an internal error.",
        ) from exc

    try:
        # Use uuid4 thread_id; omit checkpoint_ns and checkpoint_id for
        # root graph so get_state_history works without a subgraph key.
        thread_id = str(uuid.uuid4())
        result = agent.invoke(
            {"question": body.question},
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:
        logger.exception("Agent invocation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The agent encountered an internal error.",
        ) from exc

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    return AgentQueryResponse(
        answer=result.get("answer", ""),
        classification=result.get("classification"),
        run_id=result.get("run_id"),
        elapsed_ms=elapsed_ms,
    )