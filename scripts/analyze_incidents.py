#!/usr/bin/env python3
"""
Incident File Analyzer
Validates customer support incident CSV files and generates analysis metrics.

Usage:
    python analyze_incidents.py <csv_file_path>

The script:
1. Reads the CSV file
2. Validates each record against required fields and allowed values
3. Calculates metrics: total processed, invalid count, category breakdown, status breakdown, satisfaction index
4. Prints a JSON summary to stdout
"""

import sys
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Configuration
REQUIRED_FIELDS = ['incident_id', 'category', 'status', 'description', 'customer_name', 'email', 'date']
OPTIONAL_FIELDS = ['phone', 'satisfaction_score', 'notes']
ALLOWED_CATEGORIES = {'complaints', 'requests', 'operational_failures'}
ALLOWED_STATUSES = {'open', 'closed', 'discarded'}


def validate_email(email: str) -> bool:
    """Basic email validation."""
    return '@' in email and '.' in email.split('@')[-1]


def validate_phone(phone: str) -> bool:
    """Basic phone validation - must contain at least digits and standard phone chars."""
    if not phone:
        return True  # Optional field
    allowed_chars = set('0123456789+() -.')
    return all(c in allowed_chars for c in phone) and any(c.isdigit() for c in phone)


def validate_satisfaction_score(score: Optional[str]) -> Tuple[bool, Optional[float]]:
    """Validate satisfaction score - must be numeric if provided."""
    if not score or score.strip() == '':
        return True, None
    try:
        val = float(score)
        if 0 <= val <= 10:
            return True, val
        return False, None
    except ValueError:
        return False, None


def validate_date(date_str: str) -> bool:
    """Validate date format - accepts YYYY-MM-DD."""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def validate_record(row: Dict[str, str], row_number: int) -> Tuple[bool, List[str]]:
    """
    Validate a single record against all rules.
    Returns (is_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in row or row[field].strip() == '':
            errors.append(f"Missing required field '{field}'")

    # If essential fields missing, return early
    if not row.get('category') or not row.get('status'):
        return False, errors

    # Validate category
    category = row.get('category', '').strip().lower()
    if category and category not in ALLOWED_CATEGORIES:
        errors.append(f"Invalid category '{row.get('category')}'; must be one of: {', '.join(ALLOWED_CATEGORIES)}")

    # Validate status
    status = row.get('status', '').strip().lower()
    if status and status not in ALLOWED_STATUSES:
        errors.append(f"Invalid status '{row.get('status')}'; must be one of: {', '.join(ALLOWED_STATUSES)}")

    # Validate email
    email = row.get('email', '').strip()
    if email and not validate_email(email):
        errors.append(f"Invalid email format: '{email}'")

    # Validate phone if present
    phone = row.get('phone', '').strip()
    if phone and not validate_phone(phone):
        errors.append(f"Invalid phone format: '{phone}'")

    # Validate date
    date_str = row.get('date', '').strip()
    if date_str and not validate_date(date_str):
        errors.append(f"Invalid date format '{date_str}'; must be YYYY-MM-DD")

    # Validate satisfaction score if present
    satisfaction_score = row.get('satisfaction_score', '').strip()
    if satisfaction_score:
        is_valid, _ = validate_satisfaction_score(satisfaction_score)
        if not is_valid:
            errors.append(f"Invalid satisfaction score '{satisfaction_score}'; must be a number between 0-10")

    return len(errors) == 0, errors


def analyze_csv(file_path: str) -> Dict:
    """
    Analyze a CSV file containing incident records.
    Returns a dictionary with metrics and validation errors.
    """
    metrics = {
        'total_processed': 0,
        'valid_records': 0,
        'invalid_records': 0,
        'category_breakdown': {
            'complaints': 0,
            'requests': 0,
            'operational_failures': 0,
        },
        'status_breakdown': {
            'open': 0,
            'closed': 0,
            'discarded': 0,
        },
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
                    'invalid_records': []
                }

            for row_num, row in enumerate(reader, start=2):
                metrics['total_processed'] += 1

                is_valid, errors = validate_record(row, row_num)

                if is_valid:
                    metrics['valid_records'] += 1
                    category = row.get('category', '').strip().lower()
                    if category in metrics['category_breakdown']:
                        metrics['category_breakdown'][category] += 1
                    status = row.get('status', '').strip().lower()
                    if status in metrics['status_breakdown']:
                        metrics['status_breakdown'][status] += 1
                    if status == 'closed':
                        score_str = row.get('satisfaction_score', '').strip()
                        if score_str:
                            try:
                                metrics['satisfaction_scores'].append(float(score_str))
                            except ValueError:
                                pass
                else:
                    metrics['invalid_records'] += 1
                    invalid_records.append({
                        'row_number': row_num,
                        'incident_id': row.get('incident_id', 'N/A'),
                        'errors': errors,
                    })

        avg_satisfaction = None
        if metrics['satisfaction_scores']:
            avg_satisfaction = sum(metrics['satisfaction_scores']) / len(metrics['satisfaction_scores'])

        return {
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
    """Print a human-readable summary of analysis results to the console."""
    if 'error' in result:
        print(f"\n❌ ERROR: {result['error']}\n")
        return

    print("\n" + "=" * 55)
    print("   INCIDENT ANALYSIS REPORT")
    print("=" * 55)

    print(f"\n{'📊 SUMMARY':^55}")
    print("-" * 55)
    print(f"  {'Total records processed':<35} {result['total_processed']:>8}")
    print(f"  {'Valid records':<35} {result['valid_records']:>8}")
    print(f"  {'Invalid records':<35} {result['invalid_records']:>8}")

    print(f"\n{'📂 CATEGORY BREAKDOWN':^55}")
    print("-" * 55)
    for cat, count in result['category_breakdown'].items():
        label = cat.replace('_', ' ').title()
        print(f"  {label:<35} {count:>8}")

    print(f"\n{'📋 STATUS BREAKDOWN':^55}")
    print("-" * 55)
    for status, count in result['status_breakdown'].items():
        label = status.title()
        print(f"  {label:<35} {count:>8}")

    sat = result['average_satisfaction_index']
    print(f"\n{'⭐ SATISFACTION INDEX':^55}")
    print("-" * 55)
    if sat is not None:
        print(f"  {'Average satisfaction (0-10)':<35} {sat:>8.2f}")
    else:
        print(f"  {'Average satisfaction (0-10)':<35} {'N/A':>8}")

    invalids = result.get('invalid_record_details', [])
    if invalids:
        print(f"\n{'⚠️  INVALID RECORDS':^55}")
        print("-" * 55)
        for rec in invalids[:5]:  # Show first 5 only
            errors = '; '.join(rec['errors'])
            print(f"  Row {rec['row_number']} ({rec.get('incident_id', 'N/A')}):")
            for err in rec['errors']:
                print(f"    - {err}")
        if len(invalids) > 5:
            print(f"  ... and {len(invalids) - 5} more invalid record(s)")

    print("=" * 55 + "\n")


def export_to_csv(result: Dict, filename: str = 'results.csv') -> None:
    """Export analysis metrics to a CSV file (one row per metric)."""
    import os

    rows = [
        ['Metric', 'Value'],
        ['Total Records Processed', str(result.get('total_processed', ''))],
        ['Valid Records', str(result.get('valid_records', ''))],
        ['Invalid Records', str(result.get('invalid_records', ''))],
    ]

    for cat, count in result.get('category_breakdown', {}).items():
        rows.append([f'Category - {cat.replace("_", " ").title()}', str(count)])

    for status, count in result.get('status_breakdown', {}).items():
        rows.append([f'Status - {status.title()}', str(count)])

    sat = result.get('average_satisfaction_index')
    rows.append(['Average Satisfaction Index', f'{sat:.2f}' if sat is not None else 'N/A'])

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

    # Print JSON for programmatic consumption
    print(json.dumps(result))

    # Ask user if they want to export to CSV
    if 'error' not in result:
        try:
            answer = input('\nExport results to CSV? [y/n]: ').strip().lower()
            if answer == 'y' or answer == 'yes':
                export_to_csv(result)
        except (EOFError, KeyboardInterrupt):
            print()  # Graceful handling if no interactive terminal