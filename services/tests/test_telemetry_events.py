"""Tests for the Phase 2 telemetry stub ingestion endpoint (/telemetry/events).

The endpoint must accept a batch of frontend telemetry events, validate each
against event-schemas.json (via backend.telemetry.registry), and return
200/400 accordingly. It must NOT persist anything yet (Phase 3 concern).
"""

from services.main import app as combined_app

from fastapi.testclient import TestClient


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
    client = TestClient(combined_app)
    response = client.post("/telemetry/events", json={"events": []})
    assert response.status_code == 200
    assert response.json() == {"received": 0}


def test_telemetry_events_accepts_valid_batch():
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
    assert response.json() == {"received": 2}


def test_telemetry_events_rejects_unknown_event_type():
    client = TestClient(combined_app)
    payload = {"events": [_envelope(event_type="not_a_real_event")]}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["received"] == 0
    assert len(body["errors"]) == 1
    assert any("not_a_real_event" in e for e in body["errors"])


def test_telemetry_events_rejects_disallowed_property():
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
    assert response.status_code == 400
    assert "errors" in response.json()
    assert response.json()["received"] == 0


def test_telemetry_events_rejects_missing_envelope_fields():
    client = TestClient(combined_app)
    payload = {"events": [{"event_type": "page_view"}]}  # missing envelope fields
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 400
    assert "errors" in response.json()


def test_telemetry_events_rejects_malformed_body():
    """Pydantic models provide automatic body validation — bad shapes → 422."""
    client = TestClient(combined_app)
    # Missing 'events' key
    resp = client.post("/telemetry/events", json={"not": "events"})
    assert resp.status_code == 422
    # Wrong type for 'events'
    resp = client.post("/telemetry/events", json={"events": "nope"})
    assert resp.status_code == 422
    # Invalid JSON body
    resp = client.post("/telemetry/events", content=b"not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


def test_telemetry_events_does_not_persist():
    """Phase 2 is capture/validate only — the stub must not write anything.

    If the event were persisted, a second identical emission would need to be
    deduplicated; since the stub returns clean 200s for valid events and there
    is no storage hook, we assert the obvious contract: valid batches succeed.
    """
    client = TestClient(combined_app)
    payload = {"events": [_envelope()]}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    assert response.json() == {"received": 1}