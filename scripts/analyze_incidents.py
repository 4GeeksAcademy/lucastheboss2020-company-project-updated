#!/usr/bin/env python3
"""
TrackFlow Incident Report Analyzer (CONTEXT-trackflow format)

Validates incident CSV files per TrackFlow logistics specification:
  - incident_id (TRF-XXXXXX), date (YYYY-MM-DD), country (US/ES)
  - customer_type (B2B/B2C), tracking_number (>=8 chars)
  - carrier (per country: US->UPS/FEDEX/DHL_US, ES->MRW/SEUR/DHL_ES/LOCAL_ES)
  - category (LOST_PARCEL/DELAYED_DELIVERY/WRONG_ADDRESS/RETURN_REQUEST/DAMAGE)
  - description (>=5 chars), status (OPEN/CLOSED/DISCARDED)
  - customer_email (valid with @) -- SENSITIVE, never printed/exported
  - satisfaction_score (1-5, required if status=CLOSED)

Usage:
    python analyze_incidents.py <csv_file_path> [--export y|n]

Outputs:
  - Human-readable table to stdout
  - JSON blob (last line) for API consumption
  - Optional CSV export with --export y
"""

import sys
import csv
import json
import os
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Dict, List
from packages.shared.incident_validation import (
    ALL_CARRIERS,
    CARRIERS_BY_COUNTRY,
    SATISFACTION_MAX,
    SATISFACTION_MIN,
    VALID_CATEGORIES,
    VALID_COUNTRIES,
    VALID_STATUSES,
    has_at,
    validate_record,
    validate_ymd,
)

# ---------------------------------------------------------------------------
# ANALYSIS
# ---------------------------------------------------------------------------

def analyze_csv(file_path: str) -> dict:
    """
    Read and validate the CSV.  Returns a dict with every metric the
    report needs, including raw satisfaction scores for printing.
    """
    total = 0
    valid = 0
    invalid = 0

    carrier_breakdown: Dict[str, int] = {}
    category_breakdown: Dict[str, int] = {}
    status_breakdown: Dict[str, int] = {}
    country_breakdown: Dict[str, int] = {}
    invalid_breakdown: Counter = Counter()
    satisfaction_scores: List[int] = []
    closed_count = 0
    invalid_details: List[dict] = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return {"error": "CSV file is empty or has no headers"}

            for row in reader:
                total += 1
                errs = validate_record(row)

                if not errs:
                    valid += 1

                    c = row.get("carrier", "").strip()
                    if c:
                        carrier_breakdown[c] = carrier_breakdown.get(c, 0) + 1

                    cat = row.get("category", "").strip()
                    if cat:
                        category_breakdown[cat] = category_breakdown.get(cat, 0) + 1

                    st = row.get("status", "").strip().upper()
                    if st:
                        status_breakdown[st] = status_breakdown.get(st, 0) + 1

                    co = row.get("country", "").strip().upper()
                    if co:
                        country_breakdown[co] = country_breakdown.get(co, 0) + 1

                    if st == "CLOSED":
                        closed_count += 1
                        sc = row.get("satisfaction_score", "").strip()
                        if sc:
                            try:
                                satisfaction_scores.append(int(sc))
                            except ValueError:
                                pass
                else:
                    invalid += 1

                    # Classify first error for the breakdown
                    fe = errs[0].lower()
                    if "tracking" in fe and ("missing" in fe or "invalid" in fe or "short" in fe or "8 " in fe or "8 character" in fe):
                        invalid_breakdown["Invalid tracking number"] += 1
                    elif "carrier" in fe and ("not valid" in fe or "country" in fe):
                        invalid_breakdown["Carrier/country mismatch"] += 1
                    elif "category" in fe:
                        invalid_breakdown["Invalid or missing category"] += 1
                    elif "email" in fe:
                        invalid_breakdown["Invalid or missing email"] += 1
                    elif "closed" in fe and "satisfaction" in fe:
                        invalid_breakdown["Closed incident, no score"] += 1
                    elif "satisfaction_score" in fe:
                        invalid_breakdown["Invalid satisfaction score"] += 1
                    elif "description" in fe:
                        invalid_breakdown["Invalid or missing description"] += 1
                    elif "country" in fe:
                        invalid_breakdown["Invalid or missing country"] += 1
                    elif "customer_type" in fe:
                        invalid_breakdown["Invalid customer type"] += 1
                    elif "date" in fe:
                        invalid_breakdown["Invalid date"] += 1
                    else:
                        invalid_breakdown["Other"] += 1

                    invalid_details.append({
                        "row_number": total + 1,
                        "incident_id": row.get("incident_id", "N/A"),
                        "errors": errs,
                    })

    except FileNotFoundError:
        return {"error": f"File not found: {file_path}"}
    except csv.Error as e:
        return {"error": f"CSV parsing error: {e}"}

    # Fix row numbers to be correct (data rows start at 2 with header=1)
    for i, det in enumerate(invalid_details):
        det["row_number"] = i + 2

    avg_sat = round(sum(satisfaction_scores) / len(satisfaction_scores), 2) if satisfaction_scores else None

    return {
        "format": "trackflow",
        "total_processed": total,
        "valid_records": valid,
        "invalid_records": invalid,
        "carrier_breakdown": carrier_breakdown,
        "category_breakdown": category_breakdown,
        "status_breakdown": status_breakdown,
        "country_breakdown": country_breakdown,
        "average_satisfaction_index": avg_sat,
        "invalid_breakdown": dict(invalid_breakdown),
        "invalid_record_details": invalid_details,
        "_satisfaction_scores": satisfaction_scores,
        "_closed_count": closed_count,
    }


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

def print_summary(result: dict, file_path: str) -> None:
    """Print the CONTEXT-trackflow formatted report to stdout."""
    if "error" in result:
        print(f"\nERROR: {result['error']}\n")
        return

    total = result["total_processed"]
    valid = result["valid_records"]
    invalid = result["invalid_records"]

    print("=" * 60)
    print("  TRACKFLOW -- INCIDENT REPORT ANALYSIS")
    print(f"  Source file: {file_path}")
    print("=" * 60)

    # Totals
    print(f"\nTOTAL RECORDS IN FILE .......... {total}")
    print(f"  |- Valid records ................ {valid}")
    print(f"  `- Invalid / incomplete .......... {invalid}")

    # Invalid breakdown
    ib = result.get("invalid_breakdown", {})
    if ib:
        print("\nINVALID RECORDS BREAKDOWN")
        items = list(ib.items())
        for i, (rule, cnt) in enumerate(items):
            pipe = "`-" if i == len(items) - 1 else "|-"
            print(f"  {pipe} {rule} ............... {cnt}")
    elif invalid:
        print("\nINVALID RECORDS BREAKDOWN")
        print(f"  `- Other ....................... {invalid}")

    # Category breakdown
    cat_bd = result.get("category_breakdown", {})
    if cat_bd:
        print("\nBREAKDOWN BY CATEGORY (valid records)")
        items = sorted(cat_bd.items(), key=lambda x: -x[1])
        for i, (cat, cnt) in enumerate(items):
            pct = cnt / valid * 100 if valid else 0
            pipe = "`-" if i == len(items) - 1 else "|-"
            print(f"  {pipe} {cat:.<28} {cnt:>4}  ({pct:.1f}%)")

    # Status breakdown
    st_bd = result.get("status_breakdown", {})
    if st_bd:
        print("\nBREAKDOWN BY STATUS (valid records)")
        items = sorted(st_bd.items(), key=lambda x: -x[1])
        for i, (st, cnt) in enumerate(items):
            pct = cnt / valid * 100 if valid else 0
            pipe = "`-" if i == len(items) - 1 else "|-"
            print(f"  {pipe} {st:.<28} {cnt:>4}  ({pct:.1f}%)")

    # Country breakdown (recommended)
    co_bd = result.get("country_breakdown", {})
    if co_bd:
        print("\nBREAKDOWN BY COUNTRY (valid records) -- recommended, not required")
        items = sorted(co_bd.items(), key=lambda x: -x[1])
        for i, (co, cnt) in enumerate(items):
            pct = cnt / valid * 100 if valid else 0
            pipe = "`-" if i == len(items) - 1 else "|-"
            print(f"  {pipe} {co:.<28} {cnt:>4}  ({pct:.1f}%)")

    # Satisfaction
    scores = result.get("_satisfaction_scores", [])
    closed_cnt = result.get("_closed_count", 0)
    avg_sat = result.get("average_satisfaction_index")

    print("\nSATISFACTION INDEX (closed incidents)")
    print(f"  Scored incidents: {len(scores)} of {closed_cnt}")
    if avg_sat is not None:
        print(f"  Average score: {avg_sat:.2f} / 5.00")
    else:
        print("  Average score: N/A")
    if scores:
        dist = Counter(scores)
        labels = {1: "Very dissatisfied", 2: "Dissatisfied", 3: "Neutral", 4: "Satisfied", 5: "Very satisfied"}
        for sc in range(1, 6):
            cnt = dist.get(sc, 0)
            pipe = "`-" if sc == 5 else "|-"
            print(f"  {pipe} Score {sc} ({labels[sc]}) ... {cnt}")

    print("\n" + "=" * 60)


def export_to_csv(result: dict, filename: str) -> None:
    """Export metrics as a one-row-per-metric CSV."""
    rows = [["Metric", "Value"]]
    rows.append(["Format", "trackflow"])
    rows.append(["Total Records Processed", str(result.get("total_processed", ""))])
    rows.append(["Valid Records", str(result.get("valid_records", ""))])
    rows.append(["Invalid Records", str(result.get("invalid_records", ""))])

    for carrier, cnt in sorted(result.get("carrier_breakdown", {}).items()):
        rows.append([f"Carrier -- {carrier}", str(cnt)])

    for cat, cnt in sorted(result.get("category_breakdown", {}).items()):
        rows.append([f"Category -- {cat}", str(cnt)])

    for st, cnt in sorted(result.get("status_breakdown", {}).items()):
        rows.append([f"Status -- {st}", str(cnt)])

    for co, cnt in sorted(result.get("country_breakdown", {}).items()):
        rows.append([f"Country -- {co}", str(cnt)])

    avg = result.get("average_satisfaction_index")
    rows.append(["Average Satisfaction Index", f"{avg:.2f}" if avg is not None else "N/A"])

    for rule, cnt in sorted(result.get("invalid_breakdown", {}).items()):
        rows.append([f"Invalid -- {rule}", str(cnt)])

    invalids = result.get("invalid_record_details", [])
    rows.append(["Invalid Record Count", str(len(invalids))])

    if invalids:
        rows.append([])
        rows.append(["INVALID RECORD DETAILS", ""])
        rows.append(["Row Number", "Incident ID", "Errors"])
        for rec in invalids:
            errs = " | ".join(rec.get("errors", []))
            rows.append([str(rec.get("row_number", "")), rec.get("incident_id", "N/A"), errs])

    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        print(f"Results exported to {os.path.abspath(filename)}")
    except Exception as e:
        print(f"Failed to export results: {e}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No CSV file path provided"}))
        sys.exit(1)

    csv_path = sys.argv[1]

    # Parse --export y/n
    export_path = None
    args = sys.argv[2:]
    if args and args[0] == "--export":
        if len(args) > 1 and args[1].lower() in ("y", "yes", "1", "true"):
            export_path = f"analysis-results-{Path(csv_path).stem}.csv"

    result = analyze_csv(csv_path)

    # Print human-readable report
    print_summary(result, csv_path)

    # Export if requested
    if export_path:
        export_to_csv(result, export_path)

    # Output JSON for API (last line, strip internal _ fields)
    public = {k: v for k, v in result.items() if not k.startswith("_")}
    print(json.dumps(public))