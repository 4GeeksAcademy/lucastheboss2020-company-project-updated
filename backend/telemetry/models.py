"""Pydantic models for the TrackFlow telemetry system.

These models define the standard TelemetryEvent envelope used both on the
backend (emit) and frontend (ingestion stub), matching event-schemas.json.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    """Standard telemetry envelope matching event-schemas.json §/$defs/envelope.

    All fields except ``properties`` are auto-generated when not provided.
    """

    eventId: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    sessionId: str = "anonymous"
    userId: str = "anonymous"
    event_type: str
    schemaVersion: int = 1
    requestId: str = Field(default_factory=lambda: str(uuid4()))
    properties: dict[str, Any] = Field(default_factory=dict)


class TelemetryBatch(BaseModel):
    """Request body for the POST /telemetry/events endpoint."""

    events: list[TelemetryEvent]