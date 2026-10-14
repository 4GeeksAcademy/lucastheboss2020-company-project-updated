from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from time import monotonic
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
_SUMMARY_CACHE_TTL_SECONDS = 5.0
_LIST_CACHE_TTL_SECONDS = 5.0
_LIST_CACHE_MAX_ENTRIES = 128
_summary_cache: dict[str, Any] = {"expires_at": 0.0, "value": None}
_list_cache: dict[tuple[str | None, str | None, str | None, str | None], dict[str, Any]] = {}


class InvalidStatusTransition(ValueError):
    pass


def invalidate_summary_cache() -> None:
    """Drop incident read snapshots after an incident mutation."""
    with _lock:
        _summary_cache["expires_at"] = 0.0
        _summary_cache["value"] = None
        _list_cache.clear()


def get_incident(incident_id: str) -> dict[str, Any] | None:
    return _incidents.get(Query().id == incident_id)


def list_incidents(
    *,
    status: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    cache_key = (status, origin, branch, category)
    now = monotonic()
    with _lock:
        cached = _list_cache.get(cache_key)
        if cached is not None and now < cached["expires_at"]:
            return deepcopy(cached["value"])

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
        result = sorted(records, key=lambda record: record.get("created_at", ""), reverse=True)

        # Bound memory if callers issue many distinct filter combinations.
        expired_keys = [key for key, entry in _list_cache.items() if now >= entry["expires_at"]]
        for key in expired_keys:
            del _list_cache[key]
        if len(_list_cache) >= _LIST_CACHE_MAX_ENTRIES and cache_key not in _list_cache:
            _list_cache.pop(next(iter(_list_cache)))
        _list_cache[cache_key] = {
            "expires_at": now + _LIST_CACHE_TTL_SECONDS,
            "value": result,
        }
        return deepcopy(result)


def create_incident(payload: IncidentCreate) -> dict[str, Any]:
    now = utc_isoformat()
    record = IncidentRecord(
        **payload.model_dump(),
        created_at=now,
        updated_at=now,
    ).model_dump(mode="json")
    with _lock:
        _incidents.insert(record)
        invalidate_summary_cache()
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
        invalidate_summary_cache()
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


def _build_summary(records: list[dict[str, Any]], current_time: datetime) -> dict[str, Any]:
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


def get_summary(now: datetime | None = None) -> dict[str, Any]:
    """Return the incident summary, caching live requests briefly.

    Explicit timestamps are used by deterministic callers/tests and intentionally
    bypass the wall-clock cache. Cached snapshots expire quickly and are cleared
    synchronously by every supported incident write path.
    """
    if now is not None:
        return _build_summary(_incidents.all(), now)

    current_time = datetime.now(timezone.utc)
    now_monotonic = monotonic()
    with _lock:
        cached = _summary_cache["value"]
        if cached is not None and now_monotonic < _summary_cache["expires_at"]:
            return deepcopy(cached)

        summary = _build_summary(_incidents.all(), current_time)
        _summary_cache["value"] = summary
        _summary_cache["expires_at"] = now_monotonic + _SUMMARY_CACHE_TTL_SECONDS
        return deepcopy(summary)


def insert_seed_incident(record: dict[str, Any], dedupe_key: str) -> bool:
    query = Query()
    with _lock:
        if _seed_keys.contains(query.key == dedupe_key):
            return False
        if _incidents.contains(query.id == record["id"]):
            return False
        _incidents.insert(record)
        _seed_keys.insert({"key": dedupe_key, "incident_id": record["id"]})
        invalidate_summary_cache()
    return True
