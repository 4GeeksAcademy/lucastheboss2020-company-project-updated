from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from backend.auth import get_current_user
from services.incidents import manager_data
from services.incidents.api import app


@pytest.fixture
def client(monkeypatch):
    db = TinyDB(storage=MemoryStorage)
    monkeypatch.setattr(manager_data, "_incidents", db.table("incidents"))
    monkeypatch.setattr(manager_data, "_seed_keys", db.table("incident_seed_keys"))
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-user", "email": "test@example.com"}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_user, None)
    db.close()


def incident_payload(**overrides):
    payload = {
        "title": "Carrier delay in Zaragoza",
        "description": "A tracked parcel missed its delivery window.",
        "category": "carrier_issue",
        "origin": "branch",
        "branch": "zaragoza_office",
    }
    payload.update(overrides)
    return payload


def test_manager_api_requires_bearer_auth():
    response = TestClient(app).get("/api/incidents")
    assert response.status_code == 401


def test_create_and_get_incident(client):
    created = client.post("/api/incidents", json=incident_payload())

    assert created.status_code == 201
    record = created.json()
    assert record["status"] == "open"
    assert record["created_at"].endswith("Z")
    assert record["updated_at"] == record["created_at"]
    assert client.get(f"/api/incidents/{record['id']}").json() == record


def test_create_returns_field_specific_400_validation(client):
    response = client.post("/api/incidents", json=incident_payload(category="not_a_category"))

    assert response.status_code == 400
    assert response.json()["error"]["field"] == "category"
    assert "valid incident category" in response.json()["error"]["message"]


def test_create_returns_field_specific_error_for_blank_title(client):
    response = client.post("/api/incidents", json=incident_payload(title="   "))

    assert response.status_code == 400
    assert response.json()["error"]["field"] == "title"
    assert response.json()["error"]["message"] == "Title is required and must be no longer than 120 characters."


def test_missing_incident_returns_404(client):
    response = client.get("/api/incidents/not-present")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Incident not found."


def test_status_route_enforces_lifecycle_and_reports_400(client):
    created = client.post("/api/incidents", json=incident_payload()).json()
    in_progress = client.patch(
        f"/api/incidents/{created['id']}/status",
        json={"status": "in_progress"},
    )
    resolved = client.patch(
        f"/api/incidents/{created['id']}/status",
        json={"status": "resolved"},
    )
    invalid = client.patch(
        f"/api/incidents/{created['id']}/status",
        json={"status": "open"},
    )

    assert in_progress.status_code == 200
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert invalid.status_code == 400
    assert invalid.json()["error"]["field"] == "status"


def test_list_filters_and_invalid_filter(client):
    client.post("/api/incidents", json=incident_payload())
    client.post(
        "/api/incidents",
        json=incident_payload(
            title="Inventory discrepancy",
            category="inventory_discrepancy",
            origin="internal",
            branch="central",
        ),
    )

    filtered = client.get("/api/incidents?origin=branch&branch=zaragoza_office&category=carrier_issue")
    invalid = client.get("/api/incidents?status=closed")

    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["category"] == "carrier_issue"
    assert invalid.status_code == 400
    assert invalid.json()["error"]["field"] == "status"


def test_summary_includes_group_counts_critical_branches_and_overdue_records(client, monkeypatch):
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    old_time = (now - timedelta(hours=25)).isoformat().replace("+00:00", "Z")
    recent_time = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    manager_data._incidents.insert(
        {
            "id": "overdue-la",
            "title": "Lost parcel",
            "description": "Parcel missing.",
            "category": "lost_parcel",
            "status": "open",
            "origin": "customer",
            "branch": "la_office",
            "created_at": old_time,
            "updated_at": old_time,
        }
    )
    manager_data._incidents.insert(
        {
            "id": "active-zgz",
            "title": "Carrier issue",
            "description": "Shipment delayed.",
            "category": "carrier_issue",
            "status": "in_progress",
            "origin": "branch",
            "branch": "zaragoza_warehouse",
            "created_at": recent_time,
            "updated_at": recent_time,
        }
    )
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(manager_data, "datetime", FrozenDateTime)

    response = client.get("/api/incidents/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["total"] == 2
    assert summary["by_status"]["open"] == 1
    assert summary["by_category"]["lost_parcel"] == 1
    assert summary["critical_open_by_branch"]["la_office"] == 1
    assert summary["critical_open_by_branch"]["zaragoza_warehouse"] == 0
    assert summary["unresolved_over_24_hours"]["count"] == 1
    assert summary["unresolved_over_24_hours"]["incidents"][0]["id"] == "overdue-la"


def test_empty_summary_returns_zero_counts_for_all_dimensions(client):
    response = client.get("/api/incidents/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["total"] == 0
    assert all(count == 0 for group in (
        summary["by_status"],
        summary["by_category"],
        summary["by_origin"],
        summary["by_branch"],
        summary["critical_open_by_branch"],
    ) for count in group.values())
    assert summary["unresolved_over_24_hours"] == {"count": 0, "incidents": []}


def test_unexpected_summary_error_returns_generic_500(client, monkeypatch):
    def fail_summary():
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(manager_data, "get_summary", fail_summary)
    response = client.get("/api/incidents/summary")

    assert response.status_code == 500
    assert "private implementation detail" not in response.text
    assert "Traceback" not in response.text


def test_analyzer_history_route_remains_available(client):
    response = client.get("/incidents/analyses")

    assert response.status_code == 200
    assert response.json() == []
