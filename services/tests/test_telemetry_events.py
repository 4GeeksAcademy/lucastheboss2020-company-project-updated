"""Tests for the Phase 3 real telemetry ingestion endpoint (/telemetry/events).

The endpoint must accept a batch of frontend telemetry events, validate each
individually via ``TelemetryEvent.model_validate()`` (per-event parsing),
persist valid events in bulk (via ``insert_telemetry_events``), and return
``{ "received": N, "stored": M, "rejected": R }`` with HTTP 200.

Key contract changes from Phase 2 stub:
- No more 400 responses for invalid events — the batch is always accepted at
  the HTTP level; individual failures are reported in ``rejected``.
- Validation uses the Pydantic ``TelemetryEvent`` model (envelope structure),
  not the deep ``validate_event()`` registry (Phase 2 approach).
- The ``received``/``stored``/``rejected`` keys replace the old ``received``/
  ``errors`` contract so the frontend TelemetryService (which only checks HTTP
  status) is unaffected.
- **Allowlist trimming is a storage-layer guarantee, not an endpoint rejection.**
  The endpoint still accepts an event carrying an out-of-plan property (it is
  counted as ``stored``), but ``services.telemetry_storage`` drops that key
  before writing the ``tags`` JSONB — see the trimming tests below.
"""


from fastapi.testclient import TestClient

from services.main import app as combined_app


def _envelope(**overrides):
    """Build a valid event envelope with default values, overridable per call."""
    payload = {
        "eventId": "11111111-1111-4111-8111-111111111111",
        "timestamp": "2024-01-01T00:00:00.000Z",
        "sessionId": "session-abc",
        "userId": "user-1",
        "event_type": "page_view",
        "schemaVersion": 1,
        "requestId": "req-1",
        "properties": {"route": "/uis/backoffice", "section": "dashboard"},
    }
    payload.update(overrides)
    if "properties" not in overrides:
        payload["properties"] = {"route": "/uis/backoffice", "section": "dashboard"}
    return payload


def test_telemetry_events_endpoint_is_registered():
    """Empty batch → received=0, stored=0, rejected=0."""
    client = TestClient(combined_app)
    response = client.post("/telemetry/events", json={"events": []})
    assert response.status_code == 200
    assert response.json() == {"received": 0, "stored": 0, "rejected": 0}


def test_telemetry_events_accepts_valid_batch():
    """All events valid → stored == received, rejected == 0."""
    client = TestClient(combined_app)
    payload = {
        "events": [
            _envelope(),
            _envelope(
                eventId="22222222-2222-4222-8222-222222222222",
                event_type="auth_login_succeeded",
                properties={"method": "password"},
            ),
        ]
    }
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 2
    # In test/CI environment, DSN is SQLite → storage unavailable → stored = len(valid_events)
    assert body["stored"] == 2
    assert body["rejected"] == 0


def test_telemetry_events_unknown_event_type_is_accepted():
    """Phase 3 contract: Pydantic model is the validator, not the registry.

    An unknown event_type has the right type (str) → passes Pydantic
    model_validate → accepted (not rejected).
    """
    client = TestClient(combined_app)
    payload = {"events": [_envelope(event_type="not_a_real_event")]}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 1
    assert body["stored"] == 1
    assert body["rejected"] == 0


def test_telemetry_events_disallowed_property_is_accepted():
    """Phase 3 contract: properties is a freeform dict — no deep allowlist.

    An event with an unexpected property passes Pydantic model_validate since
    the model only checks that ``properties`` is a dict.
    """
    client = TestClient(combined_app)
    payload = {
        "events": [
            _envelope(
                event_type="auth_login_succeeded",
                properties={"method": "password", "password_raw": "supersecret"},
            )
        ]
    }
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 1
    assert body["stored"] == 1
    assert body["rejected"] == 0


def test_telemetry_events_rejects_missing_event_type():
    """Missing required 'event_type' field fails Pydantic model_validate."""
    client = TestClient(combined_app)
    payload = {"events": [{"timestamp": "2024-01-01T00:00:00Z"}]}  # no event_type
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 1
    assert body["stored"] == 0
    assert body["rejected"] == 1


def test_telemetry_events_rejects_wrong_types():
    """Wrong types for envelope fields fail Pydantic model_validate."""
    client = TestClient(combined_app)
    payload = {"events": [_envelope(schemaVersion="not-an-int")]}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 1
    assert body["stored"] == 0
    assert body["rejected"] == 1


def test_telemetry_events_partial_acceptance():
    """Mix of valid + invalid events → stored + rejected > 0.

    ``{"bad": "object"}`` lacks the required ``event_type`` field → fails
    Pydantic model_validate → rejected.
    """
    client = TestClient(combined_app)
    payload = {
        "events": [
            _envelope(),  # valid
            {"bad": "object"},  # missing event_type → rejected
            _envelope(  # valid
                eventId="22222222-2222-4222-8222-222222222222",
                event_type="auth_login_succeeded",
                properties={"method": "password"},
            ),
        ]
    }
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 3
    assert body["stored"] == 2
    assert body["rejected"] == 1


def test_telemetry_events_malformed_envelope():
    """Non-dict items in events array, or missing events key, return 200.

    The endpoint parses the body loosely — missing ``events`` key or wrong type
    yields received=0, stored=0, rejected=0.
    """
    client = TestClient(combined_app)
    # Missing 'events' key
    resp = client.post("/telemetry/events", json={"not": "events"})
    assert resp.status_code == 200
    assert resp.json() == {"received": 0, "stored": 0, "rejected": 0}
    # Wrong type for 'events'
    resp = client.post("/telemetry/events", json={"events": "nope"})
    assert resp.status_code == 200
    assert resp.json() == {"received": 0, "stored": 0, "rejected": 0}
    # Non-dict item in events
    resp = client.post("/telemetry/events", json={"events": ["string-item"]})
    assert resp.status_code == 200
    assert resp.json() == {"received": 1, "stored": 0, "rejected": 1}


def test_telemetry_events_invalid_json():
    """Truly malformed body (not JSON) returns 422 from endpoint's own check."""
    client = TestClient(combined_app)
    resp = client.post("/telemetry/events", content=b"not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


def test_telemetry_storage_requires_postgresql_dsn():
    """Storage module raises RuntimeError when no PostgreSQL DSN is configured.

    In the test/CI environment, DATABASE_URL is ``sqlite://`` which is not a
    PostgreSQL DSN — the storage module should refuse to connect rather than
    produce a confusing psycopg2 error.
    """
    import pytest

    from services.telemetry_storage import insert_telemetry_events
    with pytest.raises(RuntimeError, match="requires a PostgreSQL DSN"):
        insert_telemetry_events([{"eventId": "x"}])


def test_telemetry_events_partial_persistence():
    """Batch with mix of valid/invalid: stored counts valid, rejected counts invalid.

    ``{"event_type": "page_view"}`` *passes* Pydantic model_validate because
    all other envelope fields have Pydantic defaults — it is counted as stored,
    not rejected.  Only truly invalid items (missing event_type, wrong types)
    count as rejected.
    """
    client = TestClient(combined_app)
    payload = {
        "events": [
            _envelope(event_type="page_view"),  # valid
            {"bad": "object"},                   # missing event_type → rejected
            _envelope(                            # valid
                eventId="33333333-3333-4333-8333-333333333333",
                event_type="inbound_order_created",
                properties={
                    "warehouse": "los_angeles",
                    "client_id": "purestep_footwear",
                    "product_id": 1,
                    "product_category": "fashion",
                    "quantity": 50,
                },
            ),
        ]
    }
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 3
    assert body["stored"] == 2  # two pass model_validate
    assert body["rejected"] == 1


# ── allowlist trimming at the storage boundary (resubmit) ────────────────────


def test_trim_properties_to_allowlist_keeps_only_allowlisted_keys():
    """Storage drops out-of-plan keys from ``properties`` before insert.

    ``auth_login_succeeded`` allowlist is {method, role, region}; any extra key
    (e.g. a raw password) is removed so it never reaches the ``tags`` JSONB.
    """
    from services.telemetry_storage import trim_properties_to_allowlist

    result = trim_properties_to_allowlist(
        "auth_login_succeeded",
        {"method": "password", "region": "ES", "password_raw": "supersecret"},
    )
    assert result == {"method": "password", "region": "ES"}
    assert "password_raw" not in result


def test_trim_properties_keeps_inbound_mandatory_properties():
    """Required inventory properties survive trimming untouched."""
    from services.telemetry_storage import trim_properties_to_allowlist

    result = trim_properties_to_allowlist(
        "inbound_order_created",
        {
            "warehouse": "los_angeles",
            "client_id": "purestep_footwear",
            "product_id": 1,
            "product_category": "fashion",
            "quantity": 50,
            "tracking_number": "1Z999AA10123456784",  # never allowlisted (TELEMETRY_PLAN §6.1)
        },
    )
    assert result == {
        "warehouse": "los_angeles",
        "client_id": "purestep_footwear",
        "product_id": 1,
        "product_category": "fashion",
        "quantity": 50,
    }
    assert "tracking_number" not in result


def test_trim_properties_empty_for_unknown_event_type():
    """Unknown event types have an empty allowlist → tags stored as {}.

    The event is still persisted (the endpoint contract counts it as stored);
    only the properties are cut so no undeclared key can leak into the DB.
    """
    from services.telemetry_storage import trim_properties_to_allowlist

    assert trim_properties_to_allowlist("not_a_real_event", {"anything": 1}) == {}


def test_trim_properties_handles_non_dict():
    """Non-dict properties are normalised to {} (never None)."""
    from services.telemetry_storage import trim_properties_to_allowlist

    assert trim_properties_to_allowlist("page_view", None) == {}
    assert trim_properties_to_allowlist("page_view", "nope") == {}


def test_prepare_rows_trims_properties_end_to_end():
    """_prepare_rows emits already-trimmed tags for the row tuple.

    This is the exact shape ``insert_telemetry_events`` sends to psycopg2
    ``execute_values`` — proving the out-of-plan key is gone before the INSERT.
    """
    from services.telemetry_storage import _prepare_rows

    rows = _prepare_rows([
        {
            "eventId": "11111111-1111-4111-8111-111111111111",
            "timestamp": "2024-01-01T00:00:00.000Z",
            "sessionId": "s",
            "userId": "u",
            "event_type": "auth_login_succeeded",
            "schemaVersion": 1,
            "requestId": "r",
            "properties": {"method": "password", "password_raw": "supersecret"},
        }
    ])
    assert len(rows) == 1
    row = rows[0]
    assert row[4] == "auth_login_succeeded"   # event_type
    # tags is a JSON string (json.dumps for psycopg2 JSONB adaptation)
    assert row[8] == '{"method": "password"}'    # tags already trimmed
    assert '"password_raw"' not in row[8]
