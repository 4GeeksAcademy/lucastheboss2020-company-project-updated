"""TrackFlow telemetry foundation (backend).

Public, stable API used by routers and middleware:

    emit(event_type, *, user_id=..., session_id=..., request_id=..., properties=...)
        Build an Event Envelope, validate it, buffer it for delivery. Never raises.

    emit_threshold(event_type, *, dedupe_key, ...)
        Same as emit() but fires at most once per day per dedupe_key
        (used for stock_threshold_triggered, TELEMETRY_PLAN / CONTEXT_6 §2).

    validate_event(event) -> list[str]
        Documented, dependency-free structural validation against
        event-schemas.json (the single source of truth). Empty list = valid.

    telemetry_enabled() -> bool
        Honours the TELEMETRY_ENABLED env flag. When disabled the whole
        package is a fast no-op so existing behavior/tests are unaffected.

    flush(), buffer_size()
        Force a buffer flush (structured stream delivery) / inspect depth.

Design references: TELEMETRY_PLAN §2 (event envelope + allowlists + PII),
§3.1 stream vs batch, CONTEXT_6 §2/5 (mandatory 5 events, warehouse + client_id
normalization, no carrier/end-recipient data).
"""
from .context import (
    CLIENT_NAME_SLUGS,
    COUNTRY_BY_WAREHOUSE,
    DEFAULT_LOW_STOCK_THRESHOLD,
    WAREHOUSE_MAP,
    client_id_from_name,
    country_for_warehouse,
    normalize_warehouse,
)
from .core import (
    SCHEMA_VERSION,
    buffer_size,
    current_request_id,
    emit,
    emit_threshold,
    flush,
    reset_state_for_tests,
    set_request_id,
    telemetry_enabled,
)
from .middleware import install_telemetry
from .registry import KNOWN_EVENTS, get_properties_allowlist, validate_event

__all__ = [
    "KNOWN_EVENTS",
    "SCHEMA_VERSION",
    "CLIENT_NAME_SLUGS",
    "COUNTRY_BY_WAREHOUSE",
    "DEFAULT_LOW_STOCK_THRESHOLD",
    "WAREHOUSE_MAP",
    "buffer_size",
    "client_id_from_name",
    "country_for_warehouse",
    "current_request_id",
    "emit",
    "emit_threshold",
    "flush",
    "get_properties_allowlist",
    "install_telemetry",
    "normalize_warehouse",
    "reset_state_for_tests",
    "set_request_id",
    "telemetry_enabled",
    "validate_event",
]