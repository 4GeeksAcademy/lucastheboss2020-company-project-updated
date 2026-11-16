"""Authenticated FastAPI adapter for the same secured TrackFlow MCP agent.
The response shape is unchanged. Customer resource grants are deliberately absent
until a trusted customer/order ownership source is integrated; requests fail closed.
"""
from __future__ import annotations
import logging
import time
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,status
from pydantic import BaseModel,StringConstraints
from backend.auth import get_current_user
from mcps.agent import create_agent_graph

logger=logging.getLogger(__name__)
router=APIRouter(tags=['agent'])
_compiled_agent=None

def _get_agent():
    global _compiled_agent
    if _compiled_agent is None:
        try:
            # No raw-message checkpoint, client-provided grants or shared memory scope.
            _compiled_agent=create_agent_graph()
        except Exception as exc:
            logger.error('Secured agent initialisation failed')
            raise RuntimeError('Agent initialisation failed.') from exc
    return _compiled_agent

class AgentQueryRequest(BaseModel):
    question: Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=2000)]
class AgentQueryResponse(BaseModel):
    answer: str
    classification: str | None=None
    run_id: str | None=None
    elapsed_ms: int | None=None

@router.post('/agent/query',response_model=AgentQueryResponse,summary='Query the secured TrackFlow CX agent')
async def query_agent(body:AgentQueryRequest,_user:dict=Depends(get_current_user))->AgentQueryResponse:
    start=time.perf_counter()
    try:
        result=await _get_agent().ainvoke({'question':body.question})
    except Exception as exc:
        # Never include raw question, tool data or provider exception details in logs.
        logger.error('Secured agent invocation failed')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail='The agent encountered an internal error.') from exc
    ctx=result.get('harness_context')
    route=result.get('route')
    classification='rag' if route=='knowledge' else 'inventory' if route=='tools' and any(word in body.question.casefold() for word in ['inventory','stock','sku']) else 'ticket' if route=='tools' else 'unknown'
    return AgentQueryResponse(answer=result.get('answer',''),classification=classification,run_id=ctx.request_id if ctx else None,elapsed_ms=int((time.perf_counter()-start)*1000))
