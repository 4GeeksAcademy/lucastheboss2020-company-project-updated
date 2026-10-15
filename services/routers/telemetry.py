"""Stub telemetry ingestion endpoint (Phase 2 — frontend capture).

Accepts POST { events: [] }, validates each event against event-schemas.json
using the existing backend.telemetry.registry.validate_event(), returns 200/400.
Does NOT persist anything — the real storage endpoint replaces this in Phase 3.

Uses the Pydantic ``TelemetryEvent`` / ``TelemetryBatch`` models for basic
envelope structure, then ``validate_event`` for deep per-event-type semantics.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.telemetry.models import TelemetryBatch
from backend.telemetry.registry import validate_event

router = APIRouter(tags=["telemetry"])


@router.post("/telemetry/events")
async def ingest_telemetry_batch(batch: TelemetryBatch) -> JSONResponse:
    """Accept a batch of telemetry events, validate each, return 200/400.

    Request body: { "events": [ { ...envelope... }, ... ] }
    Response 200: { "received": N }
    Response 400: { "received": N, "errors": [ ... ] }
    """
    errors: list[str] = []
    for i, event in enumerate(batch.events):
        event_errors = validate_event(event.model_dump())
        if event_errors:
            errors.append(f"events[{i}]: {'; '.join(event_errors)}")

    if errors:
        return JSONResponse(
            content={"received": len(batch.events) - len(errors), "errors": errors},
            status_code=400,
        )

    return JSONResponse(content={"received": len(batch.events)})