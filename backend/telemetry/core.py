"""Emitter core: Event Envelope construction, validation, buffering and delivery.

Emission contract (TELEMETRY_PLAN §3.1 stream vs batch):
- ``emit`` buffers an event for structured delivery; no network call is made for
  batch-classified events (aggregation job flushes them) and stream-classified events
  are only flushed when a sink is configured (``TELEMETRY_STREAM_URL``). Until a sink
  exists this package is a pure, inert instrumentation layer.
- ``emit_threshold`` dedupes fire-once-per-UTC-day events
  (stock_threshold_triggered, CONTEXT_6 §2).
- Anything that fails validation is dropped with a WARNING log — never sent, never
  buffered — so an accidental PII/property leak cannot reach a sink.
"""
from __future__ import annotations

import contextvars
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from .registry import validate_event

logger = logging.getLogger("trackflow.telemetry")

SCHEMA_VERSION = 1
_MAX_BUFFER = 1000

# Request-scoped correlation id. The HTTP middleware sets this from the inbound
# X-Request-Id header (or a fresh uuid4); routers emit() pick it up automatically
# so every event in a request shares the requestId (TELEMETRY_PLAN §2 envelope).
_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("trackflow_request_id", default=None)

_buffer: list[dict[str, Any]] = []
_threshold_fired: dict[str, str] = {}
_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


def set_request_id(request_id: str | None) -> None:
    """Called by the HTTP middleware to scope this request's correlation id."""
    _request_id_ctx.set(request_id)


def current_request_id() -> str | None:
    return _request_id_ctx.get()


def telemetry_enabled() -> bool:
    """Flag-gated enablement (TELEMETRY_PLAN §3.2 / CONTEXT_6). Disabled => no-op."""
    raw = os.getenv("TELEMETRY_ENABLED")
    return raw is None or raw.strip().lower() not in {"0", "false", "no", "off"}


def _build_envelope(
    event_type: str,
    *,
    user_id: str,
    session_id: str | None,
    request_id: str | None,
) -> dict[str, Any]:
    now = _clock()
    return {
        "eventId": str(uuid4()),
        "timestamp": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "sessionId": session_id or "anonymous",
        "userId": user_id or "anonymous",
        "event_type": event_type,
        "schemaVersion": SCHEMA_VERSION,
        "requestId": request_id or str(uuid4()),
    }


def emit(
    event_type: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Emit a single telemetry event. Returns the validated envelope, or None when
    telemetry is disabled or the event is invalid (dropped)."""
    if not telemetry_enabled():
        return None
    envelope = _build_envelope(
        event_type,
        user_id=str(user_id or "anonymous"),
        session_id=session_id,
        request_id=request_id or current_request_id(),
    )
    envelope["properties"] = properties or {}
    problems = validate_event(envelope)
    if problems:
        logger.warning("Telemetry event %s dropped: %s", event_type, "; ".join(problems))
        return None
    _buffer.append(envelope)
    if len(_buffer) >= _MAX_BUFFER:
        flush()
    logger.debug("Telemetry event buffered: %s", event_type)
    return envelope


def emit_threshold(
    event_type: str,
    *,
    dedupe_key: str,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Emit at most once per UTC day per dedupe_key (e.g. product+warehouse)."""
    if not telemetry_enabled():
        return None
    day = _clock().date().isoformat()
    cache_key = f"{event_type}:{dedupe_key}:{day}"
    if _threshold_fired.get(cache_key) == day:
        return None
    _threshold_fired[cache_key] = day
    return emit(event_type, user_id=user_id, session_id=session_id, request_id=request_id, properties=properties)


def flush() -> int:
    """Deliver buffered events to a configured sink and clear the buffer.

    Foundation stage: events are flushed to a structured JSONL file when
    TELEMETRY_SINK_PATH is set (useful for local dev/tests); otherwise the buffer is
    drained to a no-op (stream pipeline wiring is a later milestone).
    """
    if not _buffer:
        return 0
    pending = list(_buffer)
    _buffer.clear()
    sink_path = os.getenv("TELEMETRY_SINK_PATH")
    if sink_path:
        try:
            from pathlib import Path

            path = Path(sink_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                for event in pending:
                    handle.write(__import__("json").dumps(event, separators=(",", ":")) + "\n")
            logger.info("Telemetry: flushed %d events to %s", len(pending), sink_path)
        except OSError as exc:  # pragma: no cover - filesystem edge
            logger.error("Telemetry flush failed: %s", exc)
            _buffer[:0] = pending
            return 0
    else:
        logger.debug("Telemetry: %d events buffered (no sink configured)", len(pending))
    return len(pending)


def buffer_size() -> int:
    return len(_buffer)


def reset_state_for_tests() -> None:
    """Test hook: clears the in-memory buffer and threshold cache in place."""
    _buffer.clear()
    _threshold_fired.clear()


def set_clock_for_tests(callable_: Callable[[], datetime]) -> None:
    """Test hook: deterministic clock (cache marked dirty is not needed; called at build)."""
    global _clock
    _clock = callable_