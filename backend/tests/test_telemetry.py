"""Telemetry foundation and emission tests.

Covers the packet's core contract (TELEMETRY_PLAN):
- The event registry loads the single source of truth (event-schemas.json).
- Envelope assembly (requestId correlation) and contextvar propagation.
- The 5 MANDATORY inventory events (CONTEXT_6 §5) emit schema-valid events
  through the public helpers, with PII per CONTEXT_6 §6 (no tracking_number).
- Validation drops invalid events instead of buffering them.
"""
from __future__ import annotations

import pytest

from backend.telemetry import (
    KNOWN_EVENTS,
    SCHEMA_VERSION,
    WAREHOUSE_MAP,
    buffer_size,
    client_id_from_name,
    country_for_warehouse,
    emit,
    emit_threshold,
    flush,
    get_properties_allowlist,
    normalize_warehouse,
    reset_state_for_tests,
    set_request_id,
    telemetry_enabled,
    validate_event,
)
import backend.telemetry.core as _core
from backend.telemetry.inventory_events import (
    emit_inbound_order_created,
    emit_outbound_order_created,
    emit_stock_threshold_triggered,
    inventory_context,
)


def _all_buffered() -> list[dict]:
    """Snapshot the current in-memory telemetry buffer (module-level list)."""
    return list(_core._buffer)


@pytest.fixture(autouse=True)
def reset_telemetry():
    """Each test starts from a clean, deterministic telemetry state."""
    reset_state_for_tests()
    yield
    reset_state_for_tests()


# --------------------------------------------------------------------------- #
# Registry / schema
# --------------------------------------------------------------------------- #


def test_registry_has_35_known_events():
    assert len(KNOWN_EVENTS) == 35
    for mandatory in (
        "inbound_order_created",
        "outbound_order_created",
        "stock_threshold_triggered",
        "direct_stock_edit_rejected",
        "inventory_discrepancy_detected",
    ):
        assert mandatory in KNOWN_EVENTS


def test_allowlist_is_the_schema_floor():
    props = get_properties_allowlist("inbound_order_created")
    for required in ("warehouse", "client_id", "product_id", "product_category", "quantity"):
        assert required in props, f"inbound_order_created must allow {required}"
    # No PII surfaces on inventory events (CONTEXT_6 §6).
    assert "tracking_number" not in props
    assert "recipient" not in props


def test_warehouse_and_country_normalization():
    assert normalize_warehouse("LA") == "los_angeles"
    assert normalize_warehouse("zgz") == "zaragoza"
    assert normalize_warehouse("  ZGZ  ") == "zaragoza"
    assert normalize_warehouse("MAD") is None
    assert normalize_warehouse(None) is None
    assert WAREHOUSE_MAP["ZGZ"] == "zaragoza"
    assert country_for_warehouse("los_angeles") == "US"
    assert country_for_warehouse("zaragoza") == "ES"
    assert country_for_warehouse("MAD") is None


def test_client_id_is_stable_slug():
    assert client_id_from_name("PureStep Footwear") == "purestep_footwear"
    assert client_id_from_name("  SoundWave   Electronics ") == "soundwave_electronics"
    assert client_id_from_name("GlowLab Cosmetics") == "glowlab_cosmetics"
    assert client_id_from_name("UrbanThread") == "urban_thread"
    assert client_id_from_name(None) is None
    assert client_id_from_name("") is None


# --------------------------------------------------------------------------- #
# Envelope + validation
# --------------------------------------------------------------------------- #


def test_emit_builds_valid_envelope_and_increments_buffer():
    result = emit(
        "inbound_order_created",
        properties={
            "warehouse": "los_angeles",
            "client_id": "purestep_footwear",
            "product_id": 1,
            "product_category": "fashion",
            "quantity": 10,
            "order_id": "42",
            "reference": "PO-2026-01",
            "stock_after": 100,
            "country": "US",
        },
    )
    assert result is not None
    assert validate_event(result) == []
    assert result["schemaVersion"] == SCHEMA_VERSION
    assert result["event_type"] == "inbound_order_created"
    assert buffer_size() == 1
    assert flush() == 1
    assert buffer_size() == 0


def test_emit_drops_invalid_events_without_buffering():
    # tracking_number is NOT an allowlisted property -> rejected, not buffered.
    result = emit(
        "outbound_order_created",
        properties={
            "warehouse": "zaragoza",
            "client_id": "soundwave_electronics",
            "product_id": 3,
            "product_category": "electronics",
            "quantity": 2,
            "tracking_number": "LEAK-ME",
        },
    )
    assert result is None
    assert buffer_size() == 0


@pytest.mark.parametrize(
    "warehouse,expected",
    [("LA", "los_angeles"), ("zgz", "zaragoza"), ("madrid", None)],
)
def test_inventory_context_derives_warehouse(warehouse, expected):
    # Full context requires product info; unknown warehouses are rejected.
    if expected is None:
        assert inventory_context(
            warehouse=warehouse, product_id=1, product_category="fashion", client_name="UrbanThread"
        ) == {}
        return
    ctx = inventory_context(
        warehouse=warehouse, product_id=1, product_category="fashion", client_name="UrbanThread"
    )
    assert ctx["warehouse"] == expected
    assert ctx["country"] == ("US" if expected == "los_angeles" else "ES")


def test_inventory_context_requires_product_info():
    # Missing product/category -> empty context (cannot build a valid event).
    assert inventory_context(warehouse="LA") == {}
    assert inventory_context(warehouse="LA", product_category="fashion") == {}
    # Missing client name (no product, no client_name) -> cannot resolve client_id.
    assert inventory_context(warehouse="LA", product_id=7, product_category="fashion") == {}
    # With a known client name the context includes the canonical client_id.
    ctx = inventory_context(
        warehouse="LA", product_id=7, product_category="fashion", client_name="PureStep Footwear"
    )
    assert ctx["client_id"] == "purestep_footwear"
    assert ctx["product_id"] == 7
    assert ctx["product_category"] == "fashion"
    # Unknown warehouse is rejected even with full product info.
    assert inventory_context(warehouse="MAD", product_id=7, product_category="fashion", client_name="UrbanThread") == {}


def test_emit_threshold_dedupes_same_day():
    events = [
        emit_threshold(
            "stock_threshold_triggered",
            dedupe_key="7:los_angeles",
            properties={
                "warehouse": "los_angeles",
                "client_id": "purestep_footwear",
                "product_id": 7,
                "product_category": "fashion",
                "quantity": 5,
                "threshold_value": 20,
            },
        )
        for _ in range(3)
    ]
    assert sum(1 for ev in events if ev is not None) == 1
    assert buffer_size() == 1


def test_request_id_correlation_via_contextvar():
    set_request_id("req-abc-123")
    result = emit(
        "inbound_order_created",
        properties={
            "warehouse": "zaragoza",
            "client_id": "glowlab_cosmetics",
            "product_id": 9,
            "product_category": "cosmetics",
            "quantity": 4,
        },
    )
    assert result is not None
    assert result["requestId"] == "req-abc-123"


# --------------------------------------------------------------------------- #
# MANDATORY inventory events (CONTEXT_6 §5)
# --------------------------------------------------------------------------- #


def test_inbound_order_created_helper():
    result = emit_inbound_order_created(
        context={"warehouse": "los_angeles", "client_id": "urban_thread", "product_id": 2, "product_category": "fashion"},
        quantity=12,
        user_id="u-1",
        order_id="10",
        reference="IN-2026-001",
        stock_after=55,
    )
    assert result is not None
    assert validate_event(result) == []
    assert result["userId"] == "u-1"


def test_inbound_order_created_skipped_without_context():
    assert emit_inbound_order_created(context={}, quantity=5) is None
    assert buffer_size() == 0


def test_outbound_order_created_helper_no_tracking():
    result = emit_outbound_order_created(
        context={"warehouse": "los_angeles", "client_id": "purestep_footwear", "product_id": 4, "product_category": "fashion"},
        quantity=3,
        user_id="u-1",
        order_id="11",
        exit_type="dispatch",
        stock_after=17,
    )
    assert result is not None
    assert validate_event(result) == []
    assert "tracking_number" not in result["properties"]


def test_stock_threshold_triggered_helper():
    result = emit_stock_threshold_triggered(
        context={"warehouse": "zaragoza", "client_id": "soundwave_electronics", "product_id": 6, "product_category": "electronics"},
        stock_level=3,
        threshold_value=20,
    )
    assert result is not None
    assert validate_event(result) == []
    assert result["properties"]["threshold_value"] == 20


def test_telemetry_enabled_respects_env(monkeypatch):
    monkeypatch.setenv("TELEMETRY_ENABLED", "0")
    assert telemetry_enabled() is False
    assert emit("inbound_order_created") is None
    assert buffer_size() == 0
    monkeypatch.setenv("TELEMETRY_ENABLED", "1")
    assert telemetry_enabled() is True


# --------------------------------------------------------------------------- #
# Auth events (PII-safe: NEVER capture email/password/token)
# --------------------------------------------------------------------------- #


def test_login_failed_never_carries_credentials():
    result = emit(
        "auth_login_failed",
        properties={"reason": "invalid_credentials", "method": "password", "region": "ES"},
    )
    assert result is not None
    assert validate_event(result) == []
    assert "email" not in result["properties"]
    assert "password" not in result["properties"]
    assert result["userId"] == "anonymous"


def test_password_reset_requested_has_no_email_or_token():
    result = emit(
        "auth_password_reset_requested",
        properties={"token_issued": True},
    )
    assert result is not None
    assert validate_event(result) == []
    assert "email" not in result["properties"]
    assert "token" not in result["properties"]


def test_http_login_failure_emits_sanitised_event(auth_environment):
    """401 invalid credentials -> auth_login_failed, no PII, correlated requestId."""
    from fastapi.testclient import TestClient
    from backend import main

    reset_state_for_tests()
    client = TestClient(main.app)
    response = client.post(
        "/auth/login",
        json={"email": "someone@example.com", "password": "wrong-password"},
        headers={"X-Request-Id": "req-login-fail"},
    )
    assert response.status_code == 401
    assert response.headers.get("X-Request-Id") == "req-login-fail"
    types = [e["event_type"] for e in _all_buffered()]
    assert "auth_login_failed" in types
    login_failed = next(e for e in _all_buffered() if e["event_type"] == "auth_login_failed")
    assert login_failed["requestId"] == "req-login-fail"
    assert login_failed["userId"] == "anonymous"
    assert login_failed["properties"]["reason"] == "invalid_credentials"
    assert "email" not in login_failed["properties"]
    assert "password" not in login_failed["properties"]
    reset_state_for_tests()


def test_http_register_conflict_emits_registration_failed(auth_environment):
    """409 duplicate email -> auth_registration_failed (sanitised)."""
    from fastapi.testclient import TestClient
    from backend import main

    reset_state_for_tests()
    client = TestClient(main.app)
    # First registration succeeds.
    first = client.post(
        "/users",
        json={"email": "dupe@example.com", "password": "correct-password-123", "name": "First"},
    )
    assert first.status_code == 201
    reset_state_for_tests()
    # Duplicate registration conflicts.
    second = client.post(
        "/users",
        json={"email": "DUPE@example.com", "password": "another-password-456", "name": "Second"},
    )
    assert second.status_code == 409
    types = [e["event_type"] for e in _all_buffered()]
    assert "auth_registration_failed" in types
    failed = next(e for e in _all_buffered() if e["event_type"] == "auth_registration_failed")
    assert failed["properties"]["reason"] == "email_conflict"
    assert "email" not in failed["properties"]
    reset_state_for_tests()