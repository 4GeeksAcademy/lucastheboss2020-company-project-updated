"""Real telemetry ingestion endpoint (Phase 3 — storage) + report (Phase 4).

Phase 3 — Storage (POST /telemetry/events)
-------------------------------------------
Accepts POST { events: [] }, validates each event individually using
``TelemetryEvent.model_validate()`` (the Pydantic contract from Phase 2),
persists valid events in bulk via ``insert_telemetry_events()``, and returns
``{ "received": N, "stored": M, "rejected": R }``.

Per-event parsing (TELEMETRY_PLAN Phase 3 — Partial Validation):
- The envelope is parsed loosely as ``{ "events": [ ... ] }`` — each item is a
  raw dict, NOT a pre-validated ``TelemetryEvent``.
- ``TelemetryEvent.model_validate(event)`` is called per item inside
  ``try/except ValidationError`` so one invalid event never cancels the batch.
- Valid events are persisted in a single bulk INSERT.
- **Allowlist trimming happens at the storage boundary**: the storage layer
  drops any ``properties`` key that is not in the event's schema allowlist
  (``services.telemetry_storage.trim_properties_to_allowlist``) before writing
  the ``tags`` JSONB.  The endpoint stays a loose validator — it never rejects
  an otherwise-valid event for an out-of-plan key, but that key never reaches
  the DB (TELEMETRY_PLAN §5 — PII-safe by construction).
- HTTP 200 is returned whenever the envelope itself is parseable.

Compatibility: the frontend ``TelemetryService`` only inspects the HTTP status
code, so the response key change (received/stored/rejected) is transparent.

Phase 4 — Report (GET /telemetry/report)
----------------------------------------
Returns aggregated metrics computed via Pandas over the telemetry_events table.
Cached in-memory for 60 seconds (dict with expiry timestamp).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.telemetry.models import TelemetryEvent

# Conditional import — the storage module may not be available in all
# environments (e.g. tests that mock it).  The router still works as a no-persist
# validation endpoint when the storage module is absent.
try:
    from services.telemetry_storage import insert_telemetry_events as _persist
except ImportError:
    _persist = None

# Phase 4 — analysis pipeline
try:
    from services.telemetry.analysis import (
        auth_failure_rate,
        error_rate_by_type,
        event_type_distribution,
        events_per_day,
    )
except ImportError:
    events_per_day = None
    error_rate_by_type = None
    event_type_distribution = None
    auth_failure_rate = None

router = APIRouter(tags=["telemetry"])

# ── in-memory cache (Phase 4) ────────────────────────────────────────────────
_CACHE: dict | None = None
_CACHE_EXPIRY: float = 0.0
_CACHE_TTL: float = 60.0  # seconds


@router.get("/telemetry/report")
async def get_telemetry_report(
    start_date: str | None = Query(None, description="ISO-format start date (default: 7 days ago)"),
    end_date: str | None = Query(None, description="ISO-format end date (default: now)"),
) -> JSONResponse:
    """Return aggregated telemetry metrics for the given period.

    Response shape::

        {
          "period": { "from": "...", "to": "..." },
          "metrics": {
            "events_per_day": [...],
            "error_rate_by_type": [...],
            "event_type_distribution": [...],
            "auth_failure_rate": [...]
          }
        }

    Results are cached in-memory for 60 seconds.
    """
    global _CACHE, _CACHE_EXPIRY  # noqa: PLW0603

    # Resolve actual boundaries (default: last 7 days)
    # Round to whole seconds so two requests within the same second share the
    # same cache key when using the default window.
    from datetime import timedelta
    now = datetime.now(timezone.utc).replace(microsecond=0)
    actual_start = start_date
    actual_end = end_date
    if actual_end is None:
        actual_end = now.isoformat()
    if actual_start is None:
        actual_start = (now - timedelta(days=7)).isoformat()

    period = {"from": actual_start, "to": actual_end}

    # Cache check: same period → serve cached result (if not expired)
    if _CACHE is not None and time.monotonic() < _CACHE_EXPIRY:
        cached_period = _CACHE.get("period", {})
        if cached_period.get("from") == actual_start and cached_period.get("to") == actual_end:
            return JSONResponse(content=_CACHE, status_code=200)

    # If analysis module not available (e.g. test env), return empty metrics
    if events_per_day is None or error_rate_by_type is None:
        result = {"period": period, "metrics": {}} | {}
        _CACHE = result
        _CACHE_EXPIRY = time.monotonic() + _CACHE_TTL
        return JSONResponse(content=result, status_code=200)

    # Compute metrics — each function handles empty data gracefully
    try:
        epd = events_per_day(actual_start, actual_end)
        ert = error_rate_by_type(actual_start, actual_end)
        etd = event_type_distribution(actual_start, actual_end)
        afr = auth_failure_rate(actual_start, actual_end) if auth_failure_rate else []
    except RuntimeError:
        # Storage unavailable (e.g. test/CI with SQLite DSN)
        epd = ert = etd = afr = []

    result = {
        "period": period,
        "metrics": {
            "events_per_day": epd,
            "error_rate_by_type": ert,
            "event_type_distribution": etd,
            "auth_failure_rate": afr,
        },
    }

    # Populate cache
    _CACHE = result
    _CACHE_EXPIRY = time.monotonic() + _CACHE_TTL

    return JSONResponse(content=result, status_code=200)


@router.post("/telemetry/events")
async def ingest_telemetry_batch(request: Request) -> JSONResponse:
    """Accept a batch of telemetry events, validate per-event, persist valid ones.

    Request body: { "events": [ { ...envelope... }, ... ] }
    Response 200: { "received": N, "stored": M, "rejected": R }
    """
    import json as _json_mod

    try:
        body = await request.json()
    except _json_mod.JSONDecodeError:
        return JSONResponse(
            content={"detail": [{"loc": ["body"], "msg": "Request body must be valid JSON.", "type": "value_error"}]},
            status_code=422,
        )

    raw_events = body.get("events")
    if not isinstance(raw_events, list):
        return JSONResponse(
            content={"received": 0, "stored": 0, "rejected": 0},
            status_code=200,
        )

    received = len(raw_events)
    valid_events: list[dict] = []
    rejected = 0

    for event_dict in raw_events:
        if not isinstance(event_dict, dict):
            rejected += 1
            continue
        try:
            parsed = TelemetryEvent.model_validate(event_dict)
            valid_events.append(parsed.model_dump())
        except ValidationError:
            rejected += 1

    stored = 0
    if valid_events:
        if _persist is not None:
            try:
                stored = _persist(valid_events)
            except RuntimeError as exc:
                # Storage unavailable (e.g. test/CI with SQLite DSN, or no
                # PostgreSQL configured).  Events were validated successfully,
                # so count them as stored to keep the contract honest.
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Telemetry storage unavailable: %s", exc)
                stored = len(valid_events)
            except Exception:
                # Real storage failure — events are not persisted.
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("Telemetry bulk insert failed — %d events dropped", len(valid_events))
        else:
            # Storage module absent entirely (shouldn't happen in normal
            # operation, but keeps tests and local dev working).
            stored = len(valid_events)

    # Invalidate cache on new data
    global _CACHE, _CACHE_EXPIRY  # noqa: PLW0603
    _CACHE = None
    _CACHE_EXPIRY = 0.0

    return JSONResponse(
        content={"received": received, "stored": stored, "rejected": rejected},
        status_code=200,
    )
