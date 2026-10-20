"""Authentication + session telemetry helpers.

PII-safe by construction (never pass email / password / reset token):
- auth_login_succeeded / auth_login_failed (sanitised)
- auth_registration_created / auth_registration_failed (sanitised)
- auth_password_reset_requested / completed (sanitised) / auth_password_changed
- session_expired / session_ended

See TELEMETRY_PLAN §1 catalogue rows and CONTEXT_6.
"""
from __future__ import annotations

from typing import Any

from .core import emit

CONTEXT_COUNTRY = "ES"  # TrackFlow operations centre; derived later if geo is available


def emit_login_succeeded(
    *,
    user_id: str | None,
    role: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    properties: dict[str, Any] = {"method": "password", "region": CONTEXT_COUNTRY}
    if role:
        properties["role"] = role
    return emit(
        "auth_login_succeeded",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties=properties,
    )


def emit_login_failed(
    *,
    reason: str,
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    """Never receives email/password — only the reason (invalid_credentials,
    account_disabled, invalid_format)."""
    return emit(
        "auth_login_failed",
        user_id="anonymous",
        session_id=session_id,
        request_id=request_id,
        properties={"reason": reason, "method": "password", "region": CONTEXT_COUNTRY},
    )


def emit_registration_created(
    *,
    user_id: str | None,
    role: str = "user",
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    """Registration succeeded.

    ``role`` defaults to ``"user"`` when not provided (the schema requires it).
    """
    properties: dict[str, Any] = {"region": CONTEXT_COUNTRY, "method": "public_form", "role": role}
    return emit(
        "auth_registration_created",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties=properties,
    )


def emit_registration_failed(
    *,
    reason: str,
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    return emit(
        "auth_registration_failed",
        user_id="anonymous",
        session_id=session_id,
        request_id=request_id,
        properties={"reason": reason},
    )


def emit_password_reset_requested(
    *,
    token_issued: bool,
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    return emit(
        "auth_password_reset_requested",
        user_id="anonymous",
        session_id=session_id,
        request_id=request_id,
        properties={"token_issued": token_issued},
    )


def emit_password_reset_completed(
    *,
    success: bool,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    method: str = "reset",
) -> dict[str, Any] | None:
    return emit(
        "auth_password_reset_completed",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties={"success": success, "method": method},
    )


def emit_password_changed(
    *,
    user_id: str | None,
    source: str = "profile",
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    return emit(
        "auth_password_changed",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties={"source": source},
    )


def emit_session_expired(
    *,
    reason: str,
    user_id: str | None = None,
    route: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    properties: dict[str, Any] = {"reason": reason}
    if route:
        properties["route"] = route
    return emit(
        "session_expired",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties=properties,
    )


def emit_session_ended(
    *,
    reason: str,
    user_id: str | None,
    session_id: str | None = None,
    request_id: str | None = None,
    session_duration_ms: int | None = None,
) -> dict[str, Any] | None:
    properties: dict[str, Any] = {"reason": reason}
    if session_duration_ms is not None:
        properties["session_duration_ms"] = session_duration_ms
    return emit(
        "session_ended",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties=properties,
    )
