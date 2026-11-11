#!/usr/bin/env python3
"""Seed the centralized incident manager from the TrackFlow analyzer CSV."""

import argparse
import csv
from hashlib import sha256
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.shared.incident_validation import validate_record
from services.incidents.manager_data import insert_seed_incident
from services.incidents.manager_models import IncidentCreate

DEFAULT_CSV = PROJECT_ROOT / "data" / "incidents-trackflow.csv"
STATUS_MAP = {
    "OPEN": "open",
    "CLOSED": "resolved",
    "DISCARDED": "discarded",
}
CATEGORY_MAP = {
    "LOST_PARCEL": "lost_parcel",
    "DELAYED_DELIVERY": "carrier_issue",
    "WRONG_ADDRESS": "delivery_failure",
    "RETURN_REQUEST": "returns_issue",
    "DAMAGE": "carrier_issue",
}
BRANCH_MAP = {
    "US": "la_office",
    "ES": "zaragoza_office",
}


@dataclass
class SeedReport:
    total_rows: int = 0
    inserted: int = 0
    duplicates: int = 0
    skipped: list[dict[str, Any]] = field(default_factory=list)
    status_counts: Counter = field(default_factory=Counter)
    category_counts: Counter = field(default_factory=Counter)


def _timestamp_for_date(value: str) -> str:
    parsed = datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z")


def transform_row(row: dict[str, str], row_number: int) -> tuple[dict[str, Any], str] | tuple[None, str]:
    validation_row = dict(row)
    source_id = (row.get("incident_id") or "").strip()
    if not source_id:
        validation_row["incident_id"] = f"temporary-seed-row-{row_number}"

    errors = validate_record(validation_row)
    if errors:
        return None, f"failed source validation ({len(errors)} validation issues)"

    description = row.get("description", "")
    title = description.strip()[:120].strip()
    if not title:
        return None, "empty description cannot produce an incident title"

    source_date = (row.get("date") or "").strip()
    country = (row.get("country") or "").strip().upper()
    source_status = (row.get("status") or "").strip().upper()
    source_category = (row.get("category") or "").strip()
    created_at = _timestamp_for_date(source_date)
    branch = BRANCH_MAP.get(country)
    status = STATUS_MAP.get(source_status)
    category = CATEGORY_MAP.get(source_category)
    if not branch or not status or not category:
        return None, "country, status, or category has no manager mapping"

    try:
        manager_payload = IncidentCreate.model_validate({
            "title": title,
            "description": description,
            "category": category,
            "origin": "customer",
            "branch": branch,
        }).model_dump(mode="json")
    except ValidationError:
        return None, "transformed manager fields failed shared validation"

    record = {
        "id": str(uuid4()),
        **manager_payload,
        "status": status,
        "created_at": created_at,
        "updated_at": created_at,
    }
    if source_id:
        dedupe_material = f"csv-id:{source_id}"
    else:
        dedupe_material = f"fallback:{title}\x1f{created_at}"
    dedupe_key = sha256(dedupe_material.encode("utf-8")).hexdigest()
    return record, dedupe_key


def seed_csv(csv_path: str | Path = DEFAULT_CSV) -> SeedReport:
    report = SeedReport()
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("The incident seed CSV is missing its header row.")

        for row_number, row in enumerate(reader, start=2):
            report.total_rows += 1
            record, detail = transform_row(row, row_number)
            if record is None:
                report.skipped.append({"row_number": row_number, "reason": detail})
                continue

            if not insert_seed_incident(record, detail):
                report.duplicates += 1
                continue

            report.inserted += 1
            report.status_counts[record["status"]] += 1
            report.category_counts[record["category"]] += 1

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", default=DEFAULT_CSV, type=Path)
    args = parser.parse_args()

    try:
        report = seed_csv(args.csv_path)
    except FileNotFoundError:
        print("Incident seed CSV was not found.", file=sys.stderr)
        return 1
    except PermissionError:
        print("Incident seed CSV could not be read due to file permissions.", file=sys.stderr)
        return 1
    except (csv.Error, UnicodeDecodeError):
        print("Incident seed CSV could not be parsed. Check its encoding and format.", file=sys.stderr)
        return 1
    except ValueError:
        print("Incident seed data could not be transformed.", file=sys.stderr)
        return 1

    print(f"Incident seed complete: {report.inserted} inserted, {report.duplicates} duplicates, {len(report.skipped)} skipped.")
    print(f"Rows processed: {report.total_rows}")
    print(f"Status counts inserted: {dict(report.status_counts)}")
    print(f"Category counts inserted: {dict(report.category_counts)}")
    for skipped in report.skipped:
        print(f"Skipped row {skipped['row_number']}: {skipped['reason']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
