"""Request correlation + latency/error instrumentation.

Single middleware that supersedes the original ``timing_middleware`` (its exact
``METHOD path -> status | X.Xms`` log line is preserved so existing log-parsing
behavior is unchanged) and additionally:

- Correlates requests: honours an inbound ``X-Request-Id`` or mints a fresh uuid4,
  exposes it to the request context (``telemetry.current_request_id``) so event
  emissions in routers share the requestId, and echoes it on the response.
- Emits ``api_latency_recorded`` (batch/sampled) for OK responses and ``api_error``
  (streamed) for 5xx / unhandled exceptions (TELEMETRY_PLAN §3.1, §1 catalogue).

Emission is gated by ``telemetry_enabled()``; when disabled the middleware only
provides correlation + logging (inert, non-breaking).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .core import emit, set_request_id, telemetry_enabled

logger = logging.getLogger(__name__)

# Down-sample latency records once the per-second request rate is high
# (TELEMETRY_PLAN §4: batch/sample ahead of the aggregation job).
_LATENCY_SAMPLE_RATE = float(os.getenv("TELEMETRY_LATENCY_SAMPLE_RATE", "1.0"))

# Paths that never produce performance/error events (noise).
_IGNORED_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")

# Methods allowed by the api_latency_recorded / api_error schemas
# (method pattern ^(GET|POST|PUT|PATCH|DELETE)$).
_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


def _is_ignored(path: str) -> bool:
    return path == "/health" or path.startswith(_IGNORED_PREFIXES)


def _route_label(path: str) -> str:
    """Normalized route label: exact endpoint shape, no query string.

    Keeps the endpoint shape (e.g. /inventory/orders/inbound) without leaking
    per-entity identifiers into aggregates.
    """
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "/"
    return "/" + "/".join(parts)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Correlation + latency/error event emission around every request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._requests_window: list[float] = []

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        inbound_request_id = request.headers.get("X-Request-Id")
        request_id = inbound_request_id or str(uuid4())
        set_request_id(request_id)

        status_code: int | str = "exception"
        error_type: str | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers.setdefault("X-Request-Id", request_id)
            return response
        except Exception as exc:  # noqa: BLE001 - any failure is captured below
            status_code = 500
            error_type = type(exc).__name__
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # Preserve the original timing_middleware log line exactly.
            logger.info(
                "%s %s -> %s | %.1fms",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )
            if telemetry_enabled() and not _is_ignored(request.url.path):
                self._emit_events(request, status_code, error_type, duration_ms)

    def _emit_events(self, request: Request, status_code: int | str, error_type: str | None, duration_ms: float) -> None:
        method = request.method
        if method not in _ALLOWED_METHODS:
            return
        path = request.url.path
        if isinstance(status_code, str):
            # Unhandled exception: streamed api_error event (500).
            self._emit_error(path, method, 500, error_type or "unknown", duration_ms)
            return
        code = int(status_code)
        if code >= 500:
            # Explicit 5xx response (e.g. HTTPException(status_code=500)).
            self._emit_error(path, method, code, error_type or "http_5xx", duration_ms)
        elif self._should_sample_latency():
            self._emit_latency(path, method, code, duration_ms)

    def _emit_error(self, path: str, method: str, status_code: int, error_type: str, duration_ms: float) -> None:
        emit(
            "api_error",
            properties={
                "route": _route_label(path),
                "method": method,
                "status_code": status_code,
                "error_type": error_type,
                "duration_ms": round(duration_ms, 2),
            },
        )

    def _emit_latency(self, path: str, method: str, status_code: int, duration_ms: float) -> None:
        emit(
            "api_latency_recorded",
            properties={
                "route": _route_label(path),
                "method": method,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

    def _should_sample_latency(self) -> bool:
        """Down-sample latency events when request rate is high."""
        if _LATENCY_SAMPLE_RATE >= 1.0:
            return True
        now = time.monotonic()
        self._requests_window = [t for t in self._requests_window if now - t < 1.0]
        self._requests_window.append(now)
        step = max(1, int(1 / max(_LATENCY_SAMPLE_RATE, 0.01)))
        return len(self._requests_window) % step == 0


def install_telemetry(app: Any) -> None:
    """Mount the correlation/telemetry middleware on a FastAPI app (idempotent)."""
    for middleware in getattr(app, "user_middleware", []):
        if getattr(middleware, "cls", None) is TelemetryMiddleware:
            logger.debug("TelemetryMiddleware already installed")
            return
    app.add_middleware(TelemetryMiddleware)