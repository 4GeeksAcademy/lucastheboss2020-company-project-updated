"""FastAPI router for business performance reporting endpoints.

Three endpoints:
    - GET  /reporting/weekly-warehouse-client-performance
    - GET  /reporting/pipeline-runs/latest
    - POST /reporting/pipeline-runs

All endpoints import pipeline logic from ``data/pipelines/pipeline`` — the
pipeline implementation lives there, not duplicated here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth import get_current_user
from data.pipelines.pipeline import (
    compute_weekly_kpis,
    get_latest_watermark,
    run_pipeline,
)

from .models import (
    PerformanceEntry,
    PerformanceResponse,
    TriggerRequest,
    TriggerResponse,
    WatermarkResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reporting", tags=["reporting"])


@router.get(
    "/weekly-warehouse-client-performance",
    response_model=PerformanceResponse,
    summary="Query weekly KPIs per warehouse and client",
)
def get_weekly_performance(
    week_start: str | None = Query(
        None,
        description="ISO date for the Monday of the target week (defaults to most recent computed week)",
    ),
    _user: dict = Depends(get_current_user),
) -> PerformanceResponse:
    """Return all warehouse × client KPI rows for the given week.

    The response shape matches the contract defined in the BRIEFING:
        ``{ week_start, entries: [{ warehouse, client_id, ... }] }``
    """
    # If no week_start specified, find the latest computed week
    if week_start is None:
        watermark = get_latest_watermark()
        week_start = watermark.get("last_completed_week")
        if not week_start:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pipeline runs found. Trigger a run first or specify week_start.",
            )

    # Validate date format
    try:
        parsed = datetime.strptime(week_start, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid week_start format: '{week_start}'. Expected YYYY-MM-DD (ISO date).",
        )

    if parsed.weekday() != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"week_start '{week_start}' is not a Monday. Week must start on Monday.",
        )

    # Query the destination table via the pipeline function
    rows = compute_weekly_kpis(week_start)

    entries = [
        PerformanceEntry(
            warehouse=r["warehouse"],
            client_id=r["client_id"],
            inbound_units_count=int(r["inbound_units_count"]),
            outbound_orders_count=int(r["outbound_orders_count"]),
            stockout_events_count=int(r["stockout_events_count"]),
            discrepancy_events_count=int(r["discrepancy_events_count"]),
            discrepancy_rate=float(r["discrepancy_rate"]),
        )
        for r in rows
    ]

    return PerformanceResponse(
        week_start=week_start,
        computed_at=datetime.now(timezone.utc).isoformat(),
        entries=entries,
    )


@router.get(
    "/pipeline-runs/latest",
    response_model=WatermarkResponse,
    summary="Get status and metadata of the last pipeline run",
)
def get_latest_pipeline_run(
    _user: dict = Depends(get_current_user),
) -> WatermarkResponse:
    """Return the most recent pipeline run record from pipeline_run_log.

    Includes started_at, completed_at, rows_extracted, rows_upserted,
    and error_message alongside the traditional watermark fields.
    """
    watermark = get_latest_watermark()
    return WatermarkResponse(
        pipeline_name=watermark.get("pipeline_name", "weekly_client_performance"),
        last_completed_week=watermark.get("last_completed_week"),
        last_run_at=watermark.get("last_run_at"),
        status=watermark.get("status", "never_run"),
        rows_extracted=watermark.get("rows_extracted"),
        rows_upserted=watermark.get("rows_upserted"),
        started_at=watermark.get("started_at"),
        completed_at=watermark.get("completed_at"),
        error_message=watermark.get("error_message"),
    )


@router.post(
    "/pipeline-runs",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a manual pipeline run",
)
def trigger_pipeline_run(
    body: TriggerRequest,
    _user: dict = Depends(get_current_user),
) -> TriggerResponse:
    """Trigger a full extract → transform → load pipeline run synchronously.

    The pipeline reads from ``telemetry_events`` and upserts into
    ``reporting.weekly_warehouse_client_performance``.
    """
    # Resolve week_start: default to the most recent Monday
    week_start = body.week_start
    if week_start is None:
        today = datetime.now(timezone.utc)
        days_since_monday = today.weekday()
        from datetime import timedelta

        last_monday = today - timedelta(days=days_since_monday + 7)
        week_start = last_monday.strftime("%Y-%m-%d")

    logger.info("Manual pipeline run triggered for week %s", week_start)

    try:
        result = run_pipeline(week_start)
        return TriggerResponse(
            week_start=result.get("week_start", week_start),
            status=result.get("status", "unknown"),
            rows_upserted=result.get("rows_upserted", 0),
            error=result.get("error"),
        )
    except Exception as exc:
        logger.exception("Manual pipeline run failed")
        return TriggerResponse(
            week_start=week_start,
            status="failed",
            rows_upserted=0,
            error=str(exc),
        )