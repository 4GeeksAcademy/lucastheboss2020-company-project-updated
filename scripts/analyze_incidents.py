#!/usr/bin/env python3
"""
Incident File Analyzer — TrackFlow Incident Analysis (Syllabus Format)
Validates incident CSV files per CONTEXT.md TrackFlow spec and generates metrics.

Usage:
    python analyze_incidents.py <csv_file_path> [--export y|n]

Columns (per CONTEXT.md TrackFlow syllabus):
  - incident_id (required, non-empty)
  - category (required: complaints, requests, operational_failures)
  - status (required: open, closed, discarded)
  - description (required, non-empty)
  - customer_name (required, non-empty)
  - email (required, valid email with @ and domain)
  - phone (optional, but validated for format if present)
  - date (required, YYYY-MM-DD)
  - satisfaction_score (optional, validated 0-10 if present)
  - notes (optional, free text)

Outputs JSON to stdout for API consumption.
"""

import sys
import csv
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# ─── CONTEXT Syllabus Configuration ───────────────────────────────────────

REQUIRED_FIELDS = [
    'incident_id', 'category', 'status', 'description',
    'customer_name', 'email', 'date',
]

OPTIONAL_FIELDS = ['phone', 'satisfaction_score', 'notes']

# TrackFlow incident categories (per CONTEXT syllabus)
ALLOWED_CATEGORIES = {'complaints', 'requests', 'operational_failures'}

# TrackFlow incident statuses
ALLOWED_STATUSES = {'open', 'closed', 'discarded'}

# Score range
SATISFACTION_MIN = 0
SATISFACTION_MAX = 10


def validate_email(email: str) -> bool:
    """Validate email has @ and domain with at least one dot."""
    if not email:
        return False
    return '@' in email and '.' in email.split('@')[-1]


def validate_phone(phone: str) -> bool:
    """Validate phone starts with + followed by digits."""
    if not phone or not phone.strip():
        return True  # Phone is optional
    stripped = phone.strip()
    return bool(stripped.startswith('+') and re.search(r'\d', stripped))


def validate_date(date_str: str) -> bool:
    """Validate YYYY-MM-DD format."""
    if not date_str or not date_str.strip():
        return False
    try:
        datetime.strptime(date_str.strip(), '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_satisfaction_score(value: str) -> Tuple[bool, Optional[float]]:
    """Validate satisfaction score is 0-10. Optional field."""
    if not value or value.strip() == '':
        return True, None
    try:
        score = float(value)
        if SATISFACTION_MIN <= score <= SATISFACTION_MAX:
            return True, score
        return False, None
    except (ValueError, TypeError):
        return False, None


def validate_record(row: Dict[str, str], row_number: int) -> Tuple[bool, List[str]]:
    """
    Validate a single incident record per CONTEXT syllabus.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    # ── Required fields (must exist and be non-empty) ──
    for field in REQUIRED_FIELDS:
        if field not in row or row[field].strip() == '':
            errors.append(f"Missing required field '{field}'")

    # ── Category validation ──
    category = row.get('category', '').strip().lower()
    if category and category not in ALLOWED_CATEGORIES:
        errors.append(
            f"Invalid category '{row.get('category')}'; "
            f"must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}"
        )

    # ── Status validation ──
    status = row.get('status', '').strip().lower()
    if status and status not in ALLOWED_STATUSES:
        errors.append(
            f"Invalid status '{row.get('status')}'; "
            f"must be one of: {', '.join(sorted(ALLOWED_STATUSES))}"
        )

    # ── Email validation ──
    email = row.get('email', '').strip()
    if email and not validate_email(email):
        errors.append(f"Invalid email format: '{email}'")

    # ── Phone validation (optional but validated if provided) ──
    phone = row.get('phone', '').strip()
    if phone and not validate_phone(phone):
        errors.append(f"Invalid phone format '{phone}'; must start with +")

    # ── Date validation ──
    date_val = row.get('date', '').strip()
    if date_val and not validate_date(date_val):
        errors.append(f"Invalid date '{date_val}'; must be YYYY-MM-DD")

    # ── Satisfaction score validation ──
    score_str = row.get('satisfaction_score', '').strip()
    if score_str:
        score_valid, _ = validate_satisfaction_score(score_str)
        if not score_valid:
            errors.append(
                f"Invalid satisfaction_score '{score_str}'; "
                f"must be a number between {SATISFACTION_MIN} and {SATISFACTION_MAX}"
            )

    return len(errors) == 0, errors


def analyze_csv(file_path: str) -> Dict:
    """
    Analyze a CSV file with TrackFlow incident records.
    Returns a dict with metrics and validation errors.
    """
    metrics = {
        'total_processed': 0,
        'valid_records': 0,
        'invalid_records': 0,
        'category_breakdown': {c: 0 for c in sorted(ALLOWED_CATEGORIES)},
        'status_breakdown': {s: 0 for s in sorted(ALLOWED_STATUSES)},
        'satisfaction_scores': [],
    }

    invalid_records = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames:
                return {
                    'error': 'CSV file is empty or has no headers',
                    'metrics': None,
                    'invalid_records': [],
                }

            for row_num, row in enumerate(reader, start=2):
                metrics['total_processed'] += 1

                is_valid, errors = validate_record(row, row_num)

                if is_valid:
                    metrics['valid_records'] += 1

                    # Category breakdown
                    cat = row.get('category', '').strip().lower()
                    if cat in metrics['category_breakdown']:
                        metrics['category_breakdown'][cat] += 1

                    # Status breakdown
                    st = row.get('status', '').strip().lower()
                    if st in metrics['status_breakdown']:
                        metrics['status_breakdown'][st] += 1

                    # Satisfaction scores for average
                    score_str = row.get('satisfaction_score', '').strip()
                    if score_str:
                        try:
                            score = float(score_str)
                            if SATISFACTION_MIN <= score <= SATISFACTION_MAX:
                                metrics['satisfaction_scores'].append(score)
                        except (ValueError, TypeError):
                            pass
                else:
                    metrics['invalid_records'] += 1
                    invalid_records.append({
                        'row_number': row_num,
                        'incident_id': row.get('incident_id', 'N/A'),
                        'errors': errors,
                    })

        # Calculate average satisfaction
        avg_satisfaction = None
        if metrics['satisfaction_scores']:
            avg_satisfaction = round(
                sum(metrics['satisfaction_scores']) / len(metrics['satisfaction_scores']), 2
            )

        return {
            'format': 'trackflow',
            'total_processed': metrics['total_processed'],
            'valid_records': metrics['valid_records'],
            'invalid_records': metrics['invalid_records'],
            'category_breakdown': metrics['category_breakdown'],
            'status_breakdown': metrics['status_breakdown'],
            'average_satisfaction_index': avg_satisfaction,
            'invalid_record_details': invalid_records,
        }

    except FileNotFoundError:
        return {'error': f'File not found: {file_path}', 'metrics': None, 'invalid_records': []}
    except csv.Error as e:
        return {'error': f'CSV parsing error: {e}', 'metrics': None, 'invalid_records': []}


def print_summary(result: Dict) -> None:
    """Print human-readable summary."""
    if 'error' in result:
        print(f"\n❌ ERROR: {result['error']}\n")
        return

    print("\n" + "=" * 60)
    print("   TRACKFLOW INCIDENT ANALYSIS REPORT")
    print("=" * 60)

    print(f"\n{'📊 SUMMARY':^60}")
    print("-" * 60)
    print(f"  {'Total records processed':<42} {result['total_processed']:>8}")
    print(f"  {'Valid records':<42} {result['valid_records']:>8}")
    print(f"  {'Invalid records':<42} {result['invalid_records']:>8}")

    print(f"\n{'📂 CATEGORY BREAKDOWN':^60}")
    print("-" * 60)
    for cat, count in result.get('category_breakdown', {}).items():
        label = cat.replace('_', ' ').title()
        print(f"  {label:<42} {count:>8}")

    print(f"\n{'📋 STATUS BREAKDOWN':^60}")
    print("-" * 60)
    for status, count in result.get('status_breakdown', {}).items():
        label = status.title()
        print(f"  {label:<42} {count:>8}")

    avg_sat = result.get('average_satisfaction_index')
    print(f"\n{'⭐ CUSTOMER SATISFACTION':^60}")
    print("-" * 60)
    if avg_sat is not None:
        print(f"  {'Average satisfaction index':<42} {avg_sat:>10.2f}")
    else:
        print(f"  {'Average satisfaction index':<42} {'N/A':>8}")

    invalids = result.get('invalid_record_details', [])
    if invalids:
        print(f"\n{'⚠️  INVALID RECORDS':^60}")
        print("-" * 60)
        for rec in invalids[:5]:
            row_info = f"  Row {rec['row_number']} ({rec.get('incident_id', 'N/A')}):"
            print(row_info)
            for err in rec['errors']:
                print(f"    └─ {err}")
        if len(invalids) > 5:
            print(f"  ... and {len(invalids) - 5} more invalid record(s)")

    print("=" * 60 + "\n")


def export_to_csv(result: Dict, filename: str = 'results.csv') -> None:
    """Export analysis metrics to CSV file (one row per metric)."""
    rows = [
        ['Metric', 'Value'],
        ['Format', 'trackflow'],
        ['Total Records Processed', str(result.get('total_processed', ''))],
        ['Valid Records', str(result.get('valid_records', ''))],
        ['Invalid Records', str(result.get('invalid_records', ''))],
    ]

    for cat, count in result.get('category_breakdown', {}).items():
        label = cat.replace('_', ' ').title()
        rows.append([f'Category — {label}', str(count)])

    for status, count in result.get('status_breakdown', {}).items():
        label = status.title()
        rows.append([f'Status — {label}', str(count)])

    avg_sat = result.get('average_satisfaction_index')
    rows.append(['Average Satisfaction Index', f'{avg_sat:.2f}' if avg_sat is not None else 'N/A'])

    invalids = result.get('invalid_record_details', [])
    rows.append(['Invalid Record Count', str(len(invalids))])

    if invalids:
        rows.append([])
        rows.append(['INVALID RECORD DETAILS', ''])
        rows.append(['Row Number', 'Incident ID', 'Errors'])
        for rec in invalids:
            errs = ' | '.join(rec.get('errors', []))
            rows.append([
                str(rec.get('row_number', '')),
                rec.get('incident_id', 'N/A'),
                errs,
            ])

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print(f"✅ Results exported to {os.path.abspath(filename)}")
    except Exception as e:
        print(f"❌ Failed to export results: {e}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'No CSV file path provided'}))
        sys.exit(1)

    file_path = sys.argv[1]

    # Parse optional --export flag
    export_file = None
    remaining = sys.argv[2:]
    if remaining and remaining[0] == '--export':
        if len(remaining) > 1:
            val = remaining[1].lower()
            if val in ('y', 'yes', '1', 'true'):
                export_file = f'analysis-results-{Path(file_path).stem}.csv'

    result = analyze_csv(file_path)

    # Print human-readable summary
    print_summary(result)

    # Export CSV if requested
    if export_file:
        export_to_csv(result, export_file)

    # Print JSON for programmatic consumption (API route parses this LAST)
    print(json.dumps(result))