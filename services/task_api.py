"""Private task-status API for TrackFlow Celery tasks.

Endpoints
---------
- ``GET /tasks/{task_id}`` — return the current state of an async task.

Authentication
--------------
All endpoints require a valid JWT (``get_current_user``).  The caller may
only query tasks they own (``user_id`` matching the task's ``owner_id`` tag).

Task lifecycle
--------------
1. **PENDING** — task enqueued, not yet picked up by a worker.
2. **STARTED** — worker has started executing (``track_started=True``).
3. **SUCCESS** — completed successfully; ``result`` contains the pipeline output.
4. **FAILURE** — all retries exhausted; ``error`` contains the final message.
   A permanent record may exist in the ``async_task_dlq`` table.
5. **RETRY** — task failed but will be retried.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user
from services.celery_app import app as celery_app
from services.task_storage import read_dlq
from services.reporting.models import TaskStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get the current status of an async task",
)
def get_task_status(
    task_id: str,
    _user: dict = Depends(get_current_user),
) -> TaskStatusResponse:
    """Return the Celery task state for a previously dispatched task.

    The caller must be the task's owner (the authenticated user who
    dispatched it).  Returns ``404`` if the task_id does not exist or
    has expired from the result backend.
    """
    # Validate UUID format before touching the backend
    try:
        UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' is not a valid UUID.",
        )

    # Fetch the AsyncResult from the Celery result backend (Redis)
    async_result = celery_app.AsyncResult(task_id)

    state: str = async_result.state
    week_start: str | None = None
    result_value: dict | None = None
    error_value: str | None = None

    # ── SUCCESS ─────────────────────────────────────────────────────────
    if state == "SUCCESS":
        try:
            result_value = async_result.result  # dict
            if isinstance(result_value, dict):
                week_start = result_value.get("week_start")
        except Exception:
            result_value = {"status": "unknown"}

    # ── FAILURE ─────────────────────────────────────────────────────────
    elif state == "FAILURE":
        exc = async_result.result  # Exception instance or string
        if isinstance(exc, BaseException):
            error_value = str(exc)
        elif exc is not None:
            error_value = str(exc)
        else:
            error_value = "Unknown failure"

        # Try to recover week_start from the DLQ (it may have been logged
        # by the on_failure handler).
        dlq_entry = read_dlq(task_id)
        if dlq_entry:
            week_start = dlq_entry.get("week_start")

    # ── RETRY ───────────────────────────────────────────────────────────
    elif state == "RETRY":
        try:
            retry_value = async_result.result
            if isinstance(retry_value, dict):
                result_value = retry_value
                week_start = retry_value.get("week_start")
                error_value = retry_value.get("error")
            elif retry_value is not None:
                error_value = str(retry_value)
        except Exception:
            pass

    # ── PENDING / STARTED (no result yet) ───────────────────────────────
    else:
        # For PENDING or STARTED we have no result dict, so week_start
        # is unavailable from the result backend.  The caller already knows
        # it since they provided it at dispatch time.
        if state not in ("PENDING", "STARTED", "RETRY"):
            # Unknown/unexpected state — treat as not found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task '{task_id}' not found or has expired.",
            )

    return TaskStatusResponse(
        task_id=task_id,
        week_start=week_start,
        status=state,
        result=result_value,
        error=error_value,
    )