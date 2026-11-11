"""Authenticated endpoint for grounded TrackFlow knowledge answers."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints
from typing import Annotated

from backend.auth import get_current_user
from data.pipelines.rag import ProviderConfigurationError
from data.process.rag import KnowledgeBaseNotIndexedError
from services.knowledge_query import query

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge"])


class KnowledgeQueryRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class KnowledgeAnswerResponse(BaseModel):
    answer: str


@router.post(
    "/knowledge/query",
    response_model=KnowledgeAnswerResponse,
    summary="Answer a TrackFlow question from approved knowledge sources",
)
def query_knowledge(
    body: KnowledgeQueryRequest,
    _user: dict = Depends(get_current_user),
) -> KnowledgeAnswerResponse:
    """Return only a generated answer; citations are included inline in the answer."""
    try:
        answer = query(body.question)
    except ProviderConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except KnowledgeBaseNotIndexedError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The knowledge base is not indexed. Run `python scripts/setup_knowledge_base.py`.",
        ) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.error("Grounded knowledge query failed (%s)", type(error).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The knowledge answer could not be generated. Check Qdrant availability and model configuration.",
        ) from error
    return KnowledgeAnswerResponse(answer=answer)
