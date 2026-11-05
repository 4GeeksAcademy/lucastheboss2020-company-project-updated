"""Reporting pipeline task definition for the TrackFlow Celery worker.

Exports a single Celery shared task ``run_reporting_pipeline`` that wraps
``data/pipelines.pipeline.run_pipeline`` with retry, logging, and durable
dead-letter queue recording.

Design decisions
----------------
- **Date validation first**: invalid / future / too-old dates are rejected
  before the Celery retry loop, so we never burn retries on bad requests.
- **Failure → exception**: if ``run_pipeline`` returns a non-``success``
  status (including ``failed``), we raise ``TaskFailure`` so Celery treats it
  as a failure and, if retries remain, retries it.  Legitimate ``success``
  is the only path to Celery SUCCESS.
- Three total executions (initial + two retries), with exponential backoff:
    10 s, then 20 s.
- **DLQ on exhaustion**: after the final attempt fails, we write a permanent
  dead-letter record via ``services.task_storage.write_dlq``.
- **Pipeline contract** (verified from pipeline.py): ``run_pipeline(week_start)``
  returns ``{"status": "success", "rows_upserted": N}`` on success, or
  ``{"status": "failed", "error": "..."}`` / validation status on failure.
  The pipeline is idempotent (ON CONFLICT DO UPDATE on KPI table) and already
  writes to ``reporting.pipeline_run_log``.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from celery import Task as CeleryTask
from services.celery_app import app

from services.task_storage import write_dlq

logger = logging.getLogger(__name__)

TASK_NAME = "run_reporting_pipeline"
MAX_RETRIES = 2  # 3 total attempts

_VALIDATION_STATUSES = frozenset({
    "invalid_date", "not_a_monday", "future_date", "too_far_in_past",
})


class TaskFailure(Exception):
    """Raised when the business pipeline returns a non-success status.

    Celery treats this as a task failure and, if retries remain, will
    retry the task according to the task's ``autoretry_for`` / ``max_retries``.
    """


@app.task(
    name=TASK_NAME,
    bind=True,
    max_retries=MAX_RETRIES,
    retry_backoff=10,
    retry_backoff_max=60,
    retry_jitter=False,
    autoretry_for=(TaskFailure,),
    acks_late=True,
    reject_on_worker_lost=False,  # do not requeue killed tasks (avoid poison)
    track_started=True,
)
def run_reporting_pipeline(
    self: CeleryTask,
    week_start: str,
) -> dict[str, Any]:
    """Execute the weekly-client-performance pipeline for *week_start*.

    Parameters
    ----------
    week_start : str
        ISO-8601 date string (``YYYY-MM-DD``) for the Monday of the target
        week.  Must be a Monday, not in the future, and not > 365 days ago.

    Returns
    -------
    dict
        The pipeline result dict on success.  Typical shape::

            {"week_start": str, "status": "success", "rows_upserted": int}

    Raises
    ------
    TaskFailure
        If the pipeline returns a non-``success`` status.  Celery will retry
        according to ``autoretry_for`` + ``max_retries``.
    """
    attempt = self.request.retries + 1  # 1-based
    log_prefix = f"{TASK_NAME}[{self.request.id}] attempt={attempt}/{MAX_RETRIES + 1}"
    t0 = time.monotonic()
    is_final = self.request.retries >= MAX_RETRIES  # no retries remain

    logger.info("%s started for week_start=%s", log_prefix, week_start)

    # ── fast validation before any retry burn ────────────────────────────
    try:
        parsed = datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        msg = f"week_start '{week_start}' is not a valid ISO date (YYYY-MM-DD)"
        logger.error("%s %s", log_prefix, msg)
        exc = TaskFailure(msg)
        if is_final:
            _write_dlq_on_exhaustion(self.request.id, week_start, exc)
        raise exc from None

    if parsed.weekday() != 0:
        msg = f"week_start '{week_start}' is not a Monday"
        logger.error("%s %s", log_prefix, msg)
        exc = TaskFailure(msg)
        if is_final:
            _write_dlq_on_exhaustion(self.request.id, week_start, exc)
        raise exc from None

    now = datetime.utcnow()
    if parsed > now:
        msg = f"week_start '{week_start}' is in the future"
        logger.error("%s %s", log_prefix, msg)
        exc = TaskFailure(msg)
        if is_final:
            _write_dlq_on_exhaustion(self.request.id, week_start, exc)
        raise exc from None

    if (now - parsed).days > 365:
        msg = f"week_start '{week_start}' is more than 365 days in the past"
        logger.error("%s %s", log_prefix, msg)
        exc = TaskFailure(msg)
        if is_final:
            _write_dlq_on_exhaustion(self.request.id, week_start, exc)
        raise exc from None

    # ── execute the business pipeline ────────────────────────────────────
    # Lazy import so the Celery app can be loaded without the full
    # pipeline dependency chain at import time.
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from data.pipelines.pipeline import run_pipeline

    try:
        result: dict[str, Any] = run_pipeline(week_start)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        logger.exception(
            "%s unhandled exception after %.2f s: %s", log_prefix, elapsed, exc
        )
        task_exc = TaskFailure(str(exc))
        if is_final:
            _write_dlq_on_exhaustion(self.request.id, week_start, task_exc)
        raise task_exc from exc

    elapsed = time.monotonic() - t0
    status: str = result.get("status", "unknown")

    if status == "success":
        logger.info(
            "%s succeeded in %.2f s (rows_upserted=%d)",
            log_prefix, elapsed, result.get("rows_upserted", 0),
        )
        return result

    if status in _VALIDATION_STATUSES:
        msg = (
            f"Pipeline rejected week_start '{week_start}' "
            f"with status='{status}'"
        )
        logger.error("%s %s (%.2f s)", log_prefix, msg, elapsed)
        exc = TaskFailure(msg)
        if is_final:
            _write_dlq_on_exhaustion(self.request.id, week_start, exc)
        raise exc

    # status == "failed" or any other non-success status
    err: str = result.get("error", result.get("status", "unknown failure"))
    logger.error(
        "%s pipeline returned status='%s' after %.2f s: %s",
        log_prefix, status, elapsed, err,
    )
    exc = TaskFailure(err)
    if is_final:
        _write_dlq_on_exhaustion(self.request.id, week_start, exc)
    raise exc


# ── helper: record exhausted failures in the DLQ ────────────────────────────

def _write_dlq_on_exhaustion(
    task_id: str,
    week_start: str,
    exception: Exception,
) -> None:
    """Write a dead-letter record when all retries are exhausted.

    Called directly from the task body after the final ``raise``, so it
    executes *before* the Celery result backend is updated, guaranteeing
    the DLQ entry is durable even if the worker is killed immediately
    after returning.
    """
    attempt = MAX_RETRIES + 1
    error = str(exception)

    logger.critical(
        "DLQ record for task %s (week=%s, attempt=%d): %s",
        task_id, week_start, attempt, error,
    )

    ok = write_dlq(
        task_id=task_id,
        task_name=TASK_NAME,
        week_start=week_start,
        attempt=attempt,
        error=error,
    )
    if not ok:
        logger.critical(
            "DLQ database write FAILED for task %s — audit metadata "
            "remains in Redis result backend (expires in 24 h).  "
            "Inspect Redis keys 'celery-task-meta-%s' manually.",
            task_id, task_id,
        )