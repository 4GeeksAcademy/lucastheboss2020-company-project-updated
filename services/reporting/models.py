"""Pydantic models for the reporting API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class PerformanceEntry(BaseModel):
    """A single KPI row for a warehouse × client combination in a given week."""

    warehouse: str
    client_id: str
    inbound_units_count: int
    outbound_orders_count: int
    stockout_events_count: int
    discrepancy_events_count: int
    discrepancy_rate: float


class PerformanceResponse(BaseModel):
    """Response body for GET /reporting/weekly-warehouse-client-performance."""

    week_start: str
    computed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    entries: list[PerformanceEntry]


class WatermarkResponse(BaseModel):
    """Response body for GET /reporting/pipeline-runs/latest.

    Now includes fields from the pipeline_run_log table: started_at,
    completed_at, rows_extracted, rows_upserted, and error_message.
    """

    pipeline_name: str
    last_completed_week: str | None = None
    last_run_at: str | None = None
    status: str
    rows_extracted: int | None = None
    rows_upserted: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None


class TriggerRequest(BaseModel):
    """Request body for POST /reporting/pipeline-runs."""

    week_start: str | None = None


class TriggerResponse(BaseModel):
    """Response body for POST /reporting/pipeline-runs."""

    week_start: str
    status: str
    rows_upserted: int = 0
    error: str | None = None