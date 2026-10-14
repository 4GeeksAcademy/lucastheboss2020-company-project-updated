from datetime import datetime, timedelta, timezone

import pytest
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from services.incidents import manager_data
from services.incidents.manager_models import (
    IncidentBranch,
    IncidentCategory,
    IncidentCreate,
    IncidentOrigin,
    IncidentStatus,
)


@pytest.fixture
def manager_store(monkeypatch):
    db = TinyDB(storage=MemoryStorage)
    monkeypatch.setattr(manager_data, "_incidents", db.table("incidents"))
    monkeypatch.setattr(manager_data, "_seed_keys", db.table("incident_seed_keys"))
    manager_data.invalidate_summary_cache()
    yield db
    manager_data.invalidate_summary_cache()
    db.close()


def new_payload(**overrides):
    payload = {
        "title": "Parcel located",
        "description": "A customer parcel was located in the warehouse.",
        "category": IncidentCategory.LOST_PARCEL,
        "origin": IncidentOrigin.BRANCH,
        "branch": IncidentBranch.LA_WAREHOUSE,
    }
    payload.update(overrides)
    return IncidentCreate(**payload)


def test_create_incident_sets_id_and_utc_timestamps(manager_store):
    record = manager_data.create_incident(new_payload())

    assert record["id"]
    assert record["status"] == "open"
    assert record["created_at"].endswith("Z")
    assert record["created_at"] == record["updated_at"]


def test_incident_filters_can_be_combined(manager_store):
    matching = manager_data.create_incident(new_payload())
    manager_data.create_incident(
        new_payload(
            category=IncidentCategory.CARRIER_ISSUE,
            branch=IncidentBranch.ZARAGOZA_OFFICE,
        )
    )

    result = manager_data.list_incidents(
        status="open",
        origin="branch",
        branch="la_warehouse",
        category="lost_parcel",
    )

    assert [record["id"] for record in result] == [matching["id"]]


def test_list_cache_is_keyed_by_filters_returns_copies_and_expires(monkeypatch, manager_store):
    manager_data.create_incident(new_payload())
    clock = [100.0]
    monkeypatch.setattr(manager_data, "monotonic", lambda: clock[0])
    manager_data.invalidate_summary_cache()

    first = manager_data.list_incidents(status="open")
    first[0]["title"] = "caller mutation"
    assert manager_data.list_incidents(status="open")[0]["title"] == "Parcel located"
    assert manager_data.list_incidents(status="resolved") == []

    clock[0] += manager_data._LIST_CACHE_TTL_SECONDS + 0.01
    original_all = manager_data._incidents.all
    calls = 0

    def tracked_all():
        nonlocal calls
        calls += 1
        return original_all()

    monkeypatch.setattr(manager_data._incidents, "all", tracked_all)
    manager_data.list_incidents(status="open")
    assert calls == 1


def test_incident_mutations_invalidate_list_cache(manager_store):
    incident = manager_data.create_incident(new_payload())
    assert len(manager_data.list_incidents(status="open")) == 1

    manager_data.update_incident_status(incident["id"], IncidentStatus.IN_PROGRESS)
    assert manager_data.list_incidents(status="open") == []
    assert len(manager_data.list_incidents(status="in_progress")) == 1


def test_list_cache_is_bounded_when_many_filter_combinations_are_requested(manager_store):
    for index in range(manager_data._LIST_CACHE_MAX_ENTRIES + 5):
        manager_data.list_incidents(category=f"category-{index}")

    assert len(manager_data._list_cache) <= manager_data._LIST_CACHE_MAX_ENTRIES


def test_only_allowed_status_transitions_are_accepted(manager_store):
    record = manager_data.create_incident(new_payload())
    in_progress = manager_data.update_incident_status(record["id"], IncidentStatus.IN_PROGRESS)
    resolved = manager_data.update_incident_status(record["id"], IncidentStatus.RESOLVED)

    assert in_progress["status"] == "in_progress"
    assert resolved["status"] == "resolved"
    assert resolved["updated_at"] >= in_progress["updated_at"]
    with pytest.raises(manager_data.InvalidStatusTransition):
        manager_data.update_incident_status(record["id"], IncidentStatus.OPEN)


def test_discarded_is_final(manager_store):
    record = manager_data.create_incident(new_payload())
    discarded = manager_data.update_incident_status(record["id"], IncidentStatus.DISCARDED)

    assert discarded["status"] == "discarded"
    with pytest.raises(manager_data.InvalidStatusTransition):
        manager_data.update_incident_status(record["id"], IncidentStatus.IN_PROGRESS)


def test_summary_counts_transformed_values_and_overdue_critical_by_branch(manager_store):
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    overdue_time = (now - timedelta(hours=25)).isoformat().replace("+00:00", "Z")
    recent_time = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    manager_data._incidents.insert(
        {
            "id": "old-critical",
            "title": "Lost parcel",
            "description": "A parcel is missing.",
            "category": "lost_parcel",
            "status": "open",
            "origin": "customer",
            "branch": "la_office",
            "created_at": overdue_time,
            "updated_at": overdue_time,
        }
    )
    manager_data._incidents.insert(
        {
            "id": "recent-critical",
            "title": "Carrier delay",
            "description": "A delayed carrier shipment.",
            "category": "carrier_issue",
            "status": "in_progress",
            "origin": "branch",
            "branch": "zaragoza_office",
            "created_at": recent_time,
            "updated_at": recent_time,
        }
    )
    manager_data._incidents.insert(
        {
            "id": "resolved",
            "title": "Resolved return",
            "description": "Return processed successfully.",
            "category": "returns_issue",
            "status": "resolved",
            "origin": "internal",
            "branch": "central",
            "created_at": overdue_time,
            "updated_at": recent_time,
        }
    )

    summary = manager_data.get_summary(now)

    assert summary["total"] == 3
    assert summary["by_status"] == {
        "open": 1,
        "in_progress": 1,
        "resolved": 1,
        "discarded": 0,
    }
    assert summary["by_category"]["carrier_issue"] == 1
    assert summary["critical_open_by_branch"] == {
        "central": 0,
        "la_warehouse": 0,
        "la_office": 1,
        "zaragoza_warehouse": 0,
        "zaragoza_office": 0,
    }
    assert summary["unresolved_over_24_hours"]["count"] == 1
    assert summary["unresolved_over_24_hours"]["incidents"][0]["id"] == "old-critical"


def test_empty_summary_returns_all_zero_metrics(manager_store):
    summary = manager_data.get_summary(datetime(2026, 10, 5, 12, tzinfo=timezone.utc))

    assert summary["total"] == 0
    assert all(value == 0 for value in summary["by_status"].values())
    assert all(value == 0 for value in summary["by_category"].values())
    assert all(value == 0 for value in summary["by_origin"].values())
    assert all(value == 0 for value in summary["by_branch"].values())
    assert all(value == 0 for value in summary["critical_open_by_branch"].values())
    assert summary["unresolved_over_24_hours"] == {"count": 0, "incidents": []}


def test_live_summary_cache_returns_copies_and_expires(monkeypatch, manager_store):
    manager_data.create_incident(new_payload())
    clock = [100.0]
    monkeypatch.setattr(manager_data, "monotonic", lambda: clock[0])
    manager_data.invalidate_summary_cache()

    first = manager_data.get_summary()
    first["by_status"]["open"] = 999
    assert manager_data.get_summary()["by_status"]["open"] == 1

    calls = 0
    original = manager_data._build_summary

    def tracked_build(records, current_time):
        nonlocal calls
        calls += 1
        return original(records, current_time)

    monkeypatch.setattr(manager_data, "_build_summary", tracked_build)
    manager_data.get_summary()
    assert calls == 0

    clock[0] += manager_data._SUMMARY_CACHE_TTL_SECONDS + 0.01
    manager_data.get_summary()
    assert calls == 1


def test_incident_mutations_invalidate_live_summary_cache(manager_store):
    manager_data.invalidate_summary_cache()
    assert manager_data.get_summary()["total"] == 0

    incident = manager_data.create_incident(new_payload())
    assert manager_data.get_summary()["total"] == 1

    manager_data.update_incident_status(incident["id"], IncidentStatus.IN_PROGRESS)
    summary = manager_data.get_summary()
    assert summary["by_status"]["open"] == 0
    assert summary["by_status"]["in_progress"] == 1


def test_explicit_summary_time_bypasses_live_cache(manager_store, monkeypatch):
    manager_data.create_incident(new_payload())
    live_summary = manager_data.get_summary()
    assert live_summary["total"] == 1

    def unexpected_cache_clock():
        raise AssertionError("deterministic summary timestamps must bypass the live cache")

    monkeypatch.setattr(manager_data, "monotonic", unexpected_cache_clock)
    summary = manager_data.get_summary(datetime(2026, 10, 5, 12, tzinfo=timezone.utc))
    assert summary["total"] == 1


def test_seed_insert_uses_separate_idempotency_metadata(manager_store):
    incident = manager_data.create_incident(new_payload())
    manager_data._incidents.remove(lambda record: record["id"] == incident["id"])

    assert manager_data.insert_seed_incident(incident, "source:TRF-000001") is True
    assert manager_data.insert_seed_incident(incident, "source:TRF-000001") is False
    assert "incident_id" not in manager_data.get_incident(incident["id"])
    assert len(manager_data._seed_keys.all()) == 1
