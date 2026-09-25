#!/usr/bin/env python3
"""
Incident File Analyzer — TrackFlow TRF (Tracking Record Format)
Validates TrackFlow tracking record CSV files and generates analysis metrics.

Usage:
    python analyze_incidents.py <csv_file_path>

The script:
1. Reads the CSV file using TRF (Tracking Record Format) columns
2. Validates each record against TrackFlow carriers, incident categories, and field rules
3. Calculates metrics: total processed, valid/invalid counts, carrier breakdown,
   category breakdown, status breakdown, average declared value
4. Prints a JSON summary to stdout
"""

import sys
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# ─── TRF (Tracking Record Format) Configuration ───────────────────────────

# TRF required columns for TrackFlow tracking records
REQUIRED_FIELDS = [
    'tracking_id', 'carrier', 'category', 'status',
    'origin', 'destination',
    'shipment_date', 'weight_kg', 'declared_value',
    'customer_name', 'customer_email',
]
OPTIONAL_FIELDS = ['delivery_date', 'notes']

# TrackFlow carriers (from CONTEXT.md — US: UPS, FedEx, DHL; Spain: MRW, SEUR, DHL)
ALLOWED_CARRIERS = {'UPS', 'FEDEX', 'DHL', 'MRW', 'SEUR'}

# TrackFlow tracking incident categories (logistics exception types)
ALLOWED_CATEGORIES = {
    'LOST_PARCEL',      # Package lost in transit
    'DELAYED',          # Delivery delayed beyond committed window
    'DAMAGED',          # Package damaged in transit
    'RETURNED',         # Package returned to sender
    'WRONG_ITEM',       # Wrong item delivered
    'ADDRESS_ISSUE',    # Address problems (incomplete, invalid, not found)
    'MISSING_LABEL',    # Label issues (damaged, illegible, barcode failure)
    'CUSTOMER_CANCELLATION',  # Customer cancelled after dispatch
}

# TrackFlow record statuses
ALLOWED_STATUSES = {'open', 'closed', 'exception'}

# Carrier-to-country mapping for reference
CARRIER_COUNTRIES = {
    'UPS': 'US',
    'FedEx': 'US',
    'DHL': 'Both',  # Operates in both US and Spain
    'MRW': 'Spain',
    'SEUR': 'Spain',
}


def validate_email(email: str) -> bool:
    """Basic email validation — must contain @ and a domain with a dot."""
    return '@' in email and '.' in email.split('@')[-1]


def validate_positive_number(value: str, field_name: str) -> Tuple[bool, Optional[float]]:
    """Validate a numeric field is present and positive."""
    if not value or value.strip() == '':
        return False, None
    try:
        val = float(value)
        if val > 0:
            return True, val
        return False, None
    except ValueError:
        return False, None


def validate_date(date_str: str) -> bool:
    """Validate date format — must be YYYY-MM-DD."""
    if not date_str or date_str.strip() == '':
        return False
    try:
        datetime.strptime(date_str.strip(), '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_record(row: Dict[str, str], row_number: int) -> Tuple[bool, List[str]]:
    """
    Validate a single TRF tracking record against all TrackFlow rules.
    Returns (is_valid, list_of_errors)
    """
    errors = []

    # ── Check required fields exist and are non-empty ──
    for field in REQUIRED_FIELDS:
        if field not in row or row[field].strip() == '':
            errors.append(f"Missing required field '{field}'")

    # ── Carrier validation ──
    carrier = row.get('carrier', '').strip().upper()
    if carrier and carrier not in ALLOWED_CARRIERS:
        errors.append(
            f"Invalid carrier '{row.get('carrier')}'; "
            f"must be one of: UPS, FedEx, DHL, MRW, SEUR"
        )

    # ── Category validation ──
    category = row.get('category', '').strip().upper()
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

    # ── Weight validation (must be > 0) ──
    weight_str = row.get('weight_kg', '').strip()
    if weight_str:
        weight_valid, weight_val = validate_positive_number(weight_str, 'weight_kg')
        if not weight_valid:
            errors.append(f"Invalid weight_kg '{weight_str}'; must be a positive number")

    # ── Declared value validation (must be > 0) ──
    value_str = row.get('declared_value', '').strip()
    if value_str:
        value_valid, value_val = validate_positive_number(value_str, 'declared_value')
        if not value_valid:
            errors.append(f"Invalid declared_value '{value_str}'; must be a positive number")

    # ── Customer email validation ──
    email = row.get('customer_email', '').strip()
    if email and not validate_email(email):
        errors.append(f"Invalid customer_email format: '{email}'")

    # ── Shipment date validation ──
    ship_date = row.get('shipment_date', '').strip()
    if ship_date and not validate_date(ship_date):
        errors.append(f"Invalid shipment_date '{ship_date}'; must be YYYY-MM-DD")

    # ── Delivery date validation (optional, but must be valid if provided) ──
    del_date = row.get('delivery_date', '').strip()
    if del_date and not validate_date(del_date):
        errors.append(f"Invalid delivery_date '{del_date}'; must be YYYY-MM-DD")

    return len(errors) == 0, errors


def analyze_csv(file_path: str) -> Dict:
    """
    Analyze a CSV file containing TRF tracking records.
    Returns a dictionary with metrics and validation errors.
    """
    metrics = {
        'total_processed': 0,
        'valid_records': 0,
        'invalid_records': 0,
        'carrier_breakdown': {c: 0 for c in sorted(ALLOWED_CARRIERS)},
        'category_breakdown': {c: 0 for c in sorted(ALLOWED_CATEGORIES)},
        'status_breakdown': {s: 0 for s in sorted(ALLOWED_STATUSES)},
        'declared_values': [],
    }

    invalid_records = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames:
                return {
                    'error': 'CSV file is empty or has no headers',
                    'metrics': None,
                    'invalid_records': []
                }

            for row_num, row in enumerate(reader, start=2):
                metrics['total_processed'] += 1

                is_valid, errors = validate_record(row, row_num)

                if is_valid:
                    metrics['valid_records'] += 1

                    # Track carrier breakdown
                    carrier = row.get('carrier', '').strip().upper()
                    if carrier in metrics['carrier_breakdown']:
                        metrics['carrier_breakdown'][carrier] += 1

                    # Track category breakdown
                    category = row.get('category', '').strip().upper()
                    if category in metrics['category_breakdown']:
                        metrics['category_breakdown'][category] += 1

                    # Track status breakdown
                    status = row.get('status', '').strip().lower()
                    if status in metrics['status_breakdown']:
                        metrics['status_breakdown'][status] += 1

                    # Track declared values for average
                    value_str = row.get('declared_value', '').strip()
                    if value_str:
                        try:
                            metrics['declared_values'].append(float(value_str))
                        except ValueError:
                            pass
                else:
                    metrics['invalid_records'] += 1
                    invalid_records.append({
                        'row_number': row_num,
                        'tracking_id': row.get('tracking_id', 'N/A'),
                        'errors': errors,
                    })

        avg_declared_value = None
        if metrics['declared_values']:
            avg_declared_value = round(
                sum(metrics['declared_values']) / len(metrics['declared_values']), 2
            )

        return {
            'format': 'TRF',
            'total_processed': metrics['total_processed'],
            'valid_records': metrics['valid_records'],
            'invalid_records': metrics['invalid_records'],
            'carrier_breakdown': metrics['carrier_breakdown'],
            'category_breakdown': metrics['category_breakdown'],
            'status_breakdown': metrics['status_breakdown'],
            'average_declared_value': avg_declared_value,
            'invalid_record_details': invalid_records,
        }
    except FileNotFoundError:
        return {'error': f'File not found: {file_path}', 'metrics': None, 'invalid_records': []}
    except csv.Error as e:
        return {'error': f'CSV parsing error: {e}', 'metrics': None, 'invalid_records': []}


def print_summary(result: Dict) -> None:
    """Print a human-readable summary of analysis results to the console."""
    if 'error' in result:
        print(f"\n❌ ERROR: {result['error']}\n")
        return

    print("\n" + "=" * 60)
    print("   TRACKFLOW TRF ANALYSIS REPORT")
    print("=" * 60)

    print(f"\n{'📊 SUMMARY':^60}")
    print("-" * 60)
    print(f"  {'Total records processed':<40} {result['total_processed']:>8}")
    print(f"  {'Valid records':<40} {result['valid_records']:>8}")
    print(f"  {'Invalid records':<40} {result['invalid_records']:>8}")

    print(f"\n{'🚚 CARRIER BREAKDOWN':^60}")
    print("-" * 60)
    for carrier, count in result.get('carrier_breakdown', {}).items():
        print(f"  {carrier:<40} {count:>8}")

    print(f"\n{'📂 CATEGORY BREAKDOWN':^60}")
    print("-" * 60)
    for cat, count in result.get('category_breakdown', {}).items():
        print(f"  {cat:<40} {count:>8}")

    print(f"\n{'📋 STATUS BREAKDOWN':^60}")
    print("-" * 60)
    for status, count in result.get('status_breakdown', {}).items():
        label = status.title()
        print(f"  {label:<40} {count:>8}")

    avg_dv = result.get('average_declared_value')
    print(f"\n{'💰 AVERAGE DECLARED VALUE':^60}")
    print("-" * 60)
    if avg_dv is not None:
        print(f"  {'Average declared value (€)':<40} {avg_dv:>10.2f}")
    else:
        print(f"  {'Average declared value (€)':<40} {'N/A':>8}")

    invalids = result.get('invalid_record_details', [])
    if invalids:
        print(f"\n{'⚠️  INVALID RECORDS':^60}")
        print("-" * 60)
        for rec in invalids[:5]:
            for err in rec['errors']:
                print(f"  Row {rec['row_number']} ({rec.get('tracking_id', 'N/A')}):")
                print(f"    └─ {err}")
        if len(invalids) > 5:
            print(f"  ... and {len(invalids) - 5} more invalid record(s)")

    print("=" * 60 + "\n")


def export_to_csv(result: Dict, filename: str = 'results.csv') -> None:
    """Export analysis metrics to a CSV file (one row per metric)."""
    import os

    rows = [
        ['Metric', 'Value'],
        ['Format', 'TRF'],
        ['Total Records Processed', str(result.get('total_processed', ''))],
        ['Valid Records', str(result.get('valid_records', ''))],
        ['Invalid Records', str(result.get('invalid_records', ''))],
    ]

    for carrier, count in result.get('carrier_breakdown', {}).items():
        rows.append([f'Carrier - {carrier}', str(count)])

    for cat, count in result.get('category_breakdown', {}).items():
        rows.append([f'Category - {cat}', str(count)])

    for status, count in result.get('status_breakdown', {}).items():
        rows.append([f'Status - {status.title()}', str(count)])

    avg_dv = result.get('average_declared_value')
    rows.append(['Average Declared Value (€)', f'{avg_dv:.2f}' if avg_dv is not None else 'N/A'])

    invalids = result.get('invalid_record_details', [])
    rows.append(['Invalid Record Count', str(len(invalids))])

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
    result = analyze_csv(file_path)

    # Print human-readable summary
    print_summary(result)

    # Print JSON for programmatic consumption (API route parses this)
    print(json.dumps(result))