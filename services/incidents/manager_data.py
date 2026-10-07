from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from tinydb import Query, TinyDB

from .manager_models import (
    ALLOWED_STATUS_TRANSITIONS,
    IncidentBranch,
    IncidentCategory,
    IncidentCreate,
    IncidentOrigin,
    IncidentRecord,
    IncidentStatus,
    utc_isoformat,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
_db = TinyDB(DATA_DIR / "incidents-manager.json")
_incidents = _db.table("incidents")
_seed_keys = _db.table("incident_seed_keys")
_lock = RLock()


class InvalidStatusTransition(ValueError):
    pass


def get_incident(incident_id: str) -> dict[str, Any] | None:
    return _incidents.get(Query().id == incident_id)


def list_incidents(
    *,
    status: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    records = _incidents.all()
    filters = {
        "status": status,
        "origin": origin,
        "branch": branch,
        "category": category,
    }
    for field, value in filters.items():
        if value is not None:
            records = [record for record in records if record.get(field) == value]
    return sorted(records, key=lambda record: record.get("created_at", ""), reverse=True)


def create_incident(payload: IncidentCreate) -> dict[str, Any]:
    now = utc_isoformat()
    record = IncidentRecord(
        **payload.model_dump(),
        created_at=now,
        updated_at=now,
    ).model_dump(mode="json")
    with _lock:
        _incidents.insert(record)
    return record


def update_incident_status(incident_id: str, new_status: IncidentStatus) -> dict[str, Any] | None:
    with _lock:
        record = get_incident(incident_id)
        if record is None:
            return None

        current = IncidentStatus(record["status"])
        if new_status not in ALLOWED_STATUS_TRANSITIONS[current]:
            raise InvalidStatusTransition(
                f"Status cannot transition from '{current.value}' to '{new_status.value}'."
            )

        _incidents.update(
            {"status": new_status.value, "updated_at": utc_isoformat()},
            Query().id == incident_id,
        )
        return get_incident(incident_id)


def _counts(records: list[dict[str, Any]], field: str, values: list[str]) -> dict[str, int]:
    counts = Counter(record[field] for record in records)
    return {value: counts.get(value, 0) for value in values}


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_summary(now: datetime | None = None) -> dict[str, Any]:
    records = _incidents.all()
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    cutoff = current_time.astimezone(timezone.utc) - timedelta(hours=24)
    unresolved = [record for record in records if record["status"] in ("open", "in_progress")]
    overdue = []
    for record in unresolved:
        created_at = _parse_datetime(record.get("created_at", ""))
        if created_at is not None and created_at < cutoff:
            overdue.append(record)

    critical_open = [
        record
        for record in records
        if record["status"] == IncidentStatus.OPEN.value
        and record["category"] in (IncidentCategory.LOST_PARCEL.value, IncidentCategory.CARRIER_ISSUE.value)
    ]

    return {
        "total": len(records),
        "by_status": _counts(records, "status", [value.value for value in IncidentStatus]),
        "by_category": _counts(records, "category", [value.value for value in IncidentCategory]),
        "by_origin": _counts(records, "origin", [value.value for value in IncidentOrigin]),
        "by_branch": _counts(records, "branch", [value.value for value in IncidentBranch]),
        "critical_open_by_branch": _counts(critical_open, "branch", [value.value for value in IncidentBranch]),
        "unresolved_over_24_hours": {
            "count": len(overdue),
            "incidents": overdue,
        },
    }


def insert_seed_incident(record: dict[str, Any], dedupe_key: str) -> bool:
    query = Query()
    with _lock:
        if _seed_keys.contains(query.key == dedupe_key):
            return False
        if _incidents.contains(query.id == record["id"]):
            return False
        _incidents.insert(record)
        _seed_keys.insert({"key": dedupe_key, "incident_id": record["id"]})
    return True
