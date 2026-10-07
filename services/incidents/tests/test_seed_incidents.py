import csv
from hashlib import sha256

import pytest

from packages.shared.incident_validation import validate_record as shared_validate_record
from scripts.analyze_incidents import validate_record as analyzer_validate_record
from scripts.seed_incidents import seed_csv, transform_row
from services.incidents import manager_data
from services.incidents.manager_models import IncidentCreate


def test_analyzer_and_manager_api_reuse_shared_validation():
    assert analyzer_validate_record is shared_validate_record
    with pytest.raises(ValueError, match="Title cannot be blank"):
        IncidentCreate(
            title="   ",
            description="Description exists",
            category="other",
            origin="customer",
            branch="central",
        )


def test_shared_csv_validator_reports_null_cells_without_crashing():
    errors = shared_validate_record({
        "incident_id": None,
        "date": None,
        "country": None,
        "customer_type": None,
        "tracking_number": None,
        "carrier": None,
        "category": None,
        "description": None,
        "status": None,
        "customer_email": None,
        "satisfaction_score": None,
    })

    assert errors
    assert any("incident_id" in error for error in errors)


def valid_source_row(**overrides):
    row = {
        "incident_id": "TRF-000001",
        "date": "2026-10-01",
        "country": "US",
        "customer_type": "B2C",
        "tracking_number": "TRACK123456",
        "carrier": "UPS",
        "category": "DELAYED_DELIVERY",
        "description": "  Parcel delayed by carrier.  ",
        "status": "OPEN",
        "customer_email": "sensitive@example.com",
        "satisfaction_score": "",
    }
    row.update(overrides)
    return row


def test_transform_applies_context_mapping_and_does_not_store_source_id_or_email():
    record, dedupe_key = transform_row(valid_source_row(), 2)

    assert record["title"] == "Parcel delayed by carrier."
    assert record["description"] == "  Parcel delayed by carrier.  "
    assert record["category"] == "carrier_issue"
    assert record["status"] == "open"
    assert record["origin"] == "customer"
    assert record["branch"] == "la_office"
    assert record["created_at"] == "2026-10-01T00:00:00Z"
    assert record["updated_at"] == record["created_at"]
    assert "incident_id" not in record
    assert "customer_email" not in record
    assert dedupe_key == sha256(b"csv-id:TRF-000001").hexdigest()


def test_transform_uses_title_and_created_at_when_source_id_is_missing():
    row = valid_source_row(incident_id="")

    record, dedupe_key = transform_row(row, 17)

    assert record is not None
    assert dedupe_key == sha256(
        b"fallback:Parcel delayed by carrier.\x1f2026-10-01T00:00:00Z"
    ).hexdigest()


def test_transform_rejects_invalid_source_without_echoing_sensitive_email():
    row = valid_source_row(category="INVALID", customer_email="private@example.com")

    record, reason = transform_row(row, 2)

    assert record is None
    assert "private@example.com" not in reason


def test_seed_skips_invalid_and_is_idempotent(tmp_path, monkeypatch):
    rows = [valid_source_row(), valid_source_row(category="INVALID", incident_id="TRF-000002")]
    csv_path = tmp_path / "incidents.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as source:
        writer = csv.DictWriter(source, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    incident_rows = []
    seed_rows = set()

    def insert_seed_incident(record, dedupe_key):
        if dedupe_key in seed_rows:
            return False
        seed_rows.add(dedupe_key)
        incident_rows.append(record)
        return True

    monkeypatch.setattr(manager_data, "insert_seed_incident", insert_seed_incident)
    monkeypatch.setattr("scripts.seed_incidents.insert_seed_incident", insert_seed_incident)

    first = seed_csv(csv_path)
    second = seed_csv(csv_path)

    assert first.total_rows == 2
    assert first.inserted == 1
    assert first.duplicates == 0
    assert first.skipped == [{"row_number": 3, "reason": "failed source validation (1 validation issues)"}]
    assert second.inserted == 0
    assert second.duplicates == 1
    assert len(incident_rows) == 1
