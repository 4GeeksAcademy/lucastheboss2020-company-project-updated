from fastapi.testclient import TestClient

from backend import candidates
from backend.auth import get_current_user
from backend.main import app as backend_app
from services.incidents import manager_data
from services.incidents import data as analysis_data
from services.incidents.api import app as incidents_app
from services.incidents.manager_models import IncidentBranch, IncidentCategory, IncidentOrigin, IncidentStatus
from services.suppliers import api as supplier_api
from services.suppliers.api import app as suppliers_app


def test_analysis_routes_filter_unknown_fields_and_accept_current_payload(monkeypatch):
    monkeypatch.setattr(analysis_data, "_store", {})
    client = TestClient(incidents_app)
    payload = {
        "filename": "incidents.csv",
        "format": "trackflow",
        "metrics": {
            "total_processed": 2,
            "valid_records": 1,
            "invalid_records": 1,
            "carrier_breakdown": {"UPS": 1},
            "category_breakdown": {"LOST_PARCEL": 1},
            "status_breakdown": {"CLOSED": 1},
            "country_breakdown": {"US": 1},
            "average_satisfaction_index": 4.0,
            "invalid_breakdown": {"Invalid date": 1},
            "private_metric": 999,
        },
        "invalid_records": [{"row_number": 3, "incident_id": "TRF-3", "errors": ["bad date"]}],
        "valid_record_count": 1,
        "private_root_value": "must-not-leak",
    }

    created = client.post("/incidents/analyses", json=payload)
    assert created.status_code == 201
    analysis_id = created.json()["id"]
    detail = client.get(f"/incidents/analyses/{analysis_id}")
    history = client.get("/incidents/analyses")

    assert detail.status_code == 200
    assert detail.json()["metrics"]["total_processed"] == 2
    assert detail.json()["invalid_records"][0]["incident_id"] == "TRF-3"
    assert "private_metric" not in detail.text
    assert "private_root_value" not in detail.text
    assert "private_root_value" not in created.text
    assert len(history.json()) == 1


def test_manager_incident_response_serializes_only_declared_fields(monkeypatch):
    incident = {
        "id": "incident-1",
        "title": "Carrier delay",
        "description": "Parcel missed its delivery window.",
        "category": IncidentCategory.CARRIER_ISSUE.value,
        "status": IncidentStatus.OPEN.value,
        "origin": IncidentOrigin.BRANCH.value,
        "branch": IncidentBranch.CENTRAL.value,
        "created_at": "2026-10-05T12:00:00Z",
        "updated_at": "2026-10-05T12:00:00Z",
        "private_internal": "must-not-leak",
    }
    monkeypatch.setattr(manager_data, "list_incidents", lambda **filters: [incident])
    incidents_app.dependency_overrides[get_current_user] = lambda: {"id": "test-user"}
    try:
        response = TestClient(incidents_app).get("/api/incidents")
    finally:
        incidents_app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json()[0]["created_at"].endswith("Z")
    assert set(response.json()[0]) == {"id", "title", "category", "status", "branch", "created_at"}
    assert "description" not in response.json()[0]
    assert "origin" not in response.json()[0]
    assert "private_internal" not in response.text


def test_candidate_list_and_overdue_summary_omit_detail_fields(monkeypatch):
    from tinydb import TinyDB
    from tinydb.storages import MemoryStorage

    db = TinyDB(storage=MemoryStorage)
    table = db.table("candidates")
    candidate = {
        "id": "candidate-1",
        "companyName": "Parcel Co",
        "contactPerson": "Taylor",
        "corporateEmail": "taylor@example.com",
        "phone": "+1 213 555 0188",
        "companyWebsite": None,
        "operatingCountry": "USA",
        "productType": "Fashion",
        "monthlyVolume": "1000",
        "servicesOfInterest": ["last-mile-delivery"],
        "current3pl": "Other",
        "comments": "Private long-form note",
        "privacyAccepted": True,
        "status": "new",
        "stage": "intake",
        "assignedTo": "Commercial Desk",
        "notes": [{"id": "note-1", "body": "Internal note", "createdAt": "2026-10-01T00:00:00Z"}],
        "createdAt": "2026-10-01T00:00:00Z",
        "updatedAt": "2026-10-01T00:00:00Z",
    }
    table.insert(candidate)
    monkeypatch.setattr(candidates, "candidates_table", table)
    backend_app.dependency_overrides[get_current_user] = lambda: {"id": "test-user"}
    try:
        list_response = TestClient(backend_app).get("/candidates/")
    finally:
        backend_app.dependency_overrides.pop(get_current_user, None)
        db.close()

    assert list_response.status_code == 200
    candidate_list = list_response.json()[0]
    assert set(candidate_list) == {
        "id", "companyName", "contactPerson", "corporateEmail", "operatingCountry",
        "productType", "monthlyVolume", "servicesOfInterest", "status", "stage",
    }
    assert "Internal note" not in list_response.text
    assert "Private long-form note" not in list_response.text

    overdue_record = {
        "id": "incident-overdue",
        "title": "Carrier delay",
        "description": "Long internal incident description.",
        "category": IncidentCategory.CARRIER_ISSUE.value,
        "status": IncidentStatus.OPEN.value,
        "origin": IncidentOrigin.BRANCH.value,
        "branch": IncidentBranch.CENTRAL.value,
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-01T00:00:00Z",
    }
    monkeypatch.setattr(
        manager_data,
        "get_summary",
        lambda: {
            "total": 1,
            "by_status": {value.value: int(value == IncidentStatus.OPEN) for value in IncidentStatus},
            "by_category": {value.value: int(value == IncidentCategory.CARRIER_ISSUE) for value in IncidentCategory},
            "by_origin": {value.value: int(value == IncidentOrigin.BRANCH) for value in IncidentOrigin},
            "by_branch": {value.value: int(value == IncidentBranch.CENTRAL) for value in IncidentBranch},
            "critical_open_by_branch": {value.value: int(value == IncidentBranch.CENTRAL) for value in IncidentBranch},
            "unresolved_over_24_hours": {"count": 1, "incidents": [overdue_record]},
        },
    )
    incidents_app.dependency_overrides[get_current_user] = lambda: {"id": "test-user"}
    try:
        summary_response = TestClient(incidents_app).get("/api/incidents/summary")
    finally:
        incidents_app.dependency_overrides.pop(get_current_user, None)

    assert summary_response.status_code == 200
    overdue_item = summary_response.json()["unresolved_over_24_hours"]["incidents"][0]
    assert set(overdue_item) == {"id", "title", "status", "branch", "created_at"}
    assert "Long internal incident description" not in summary_response.text


def test_supplier_responses_include_contact_fields_and_filter_unknown_data(monkeypatch):
    supplier = {
        "id": 41,
        "name": "PackSource",
        "country": "USA",
        "categories": ["packaging_materials"],
        "rate_per_shipment": 1.25,
        "currency": "USD",
        "status": "active",
        "service_zone": "West Coast",
        "contact_email": "ops@packsource.example",
        "notes": "Preferred regional partner",
        "updated_at": "2026-10-05T12:00:00+00:00",
        "services": ["warehouse-management"],
        "private_internal": "must-not-leak",
    }
    monkeypatch.setattr(supplier_api, "get_all", lambda: [supplier])
    monkeypatch.setattr(supplier_api, "get_one", lambda supplier_id: supplier if supplier_id == 41 else None)

    client = TestClient(suppliers_app)
    response = client.get("/suppliers")
    detail = client.get("/suppliers/41")

    assert response.status_code == 200
    assert response.json()[0]["categories"] == ["packaging_materials"]
    assert "contact_email" not in response.json()[0]
    assert "notes" not in response.json()[0]
    assert "private_internal" not in response.text
    assert detail.status_code == 200
    assert detail.json()["contact_email"] == "ops@packsource.example"
    assert detail.json()["notes"] == "Preferred regional partner"
    assert "private_internal" not in detail.text
