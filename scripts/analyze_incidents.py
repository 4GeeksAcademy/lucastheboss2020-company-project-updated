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
4. Prints a formatted summary to console
5. Optionally exports results to CSV
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
    # Allow digits, +, spaces, (), -, .
    allowed_chars = set('0123456789+() -.')
    return all(c in allowed_chars for c in phone) and any(c.isdigit() for c in phone)


def validate_satisfaction_score(score: Optional[str]) -> Tuple[bool, Optional[float]]:
    """Validate satisfaction score - must be numeric if provided."""
    if not score or score.strip() == '':
        return True, None
    try:
        val = float(score)
        if 0 <= val <= 10:  # Assume 0-10 scale
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
        'satisfaction_scores': [],  # Track for average calculation
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
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 because row 1 is headers
                metrics['total_processed'] += 1
                
                is_valid, errors = validate_record(row, row_num)
                
                if is_valid:
                    metrics['valid_records'] += 1
                    # Track category
                    category = row.get('category', '').strip().lower()
                    if category in metrics['category_breakdown']:
                        metrics['category_breakdown'][category] += 1
                    # Track status
                    status = row.get('status', '').strip().lower()
                    if status in metrics['status_breakdown']:
                        metrics['status_breakdown'][status] += 1
                    # Track satisfaction score for closed incidents
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
        
        # Calculate average satisfaction index
        avg_satisfaction = None
        if metrics['satisfaction_scores']:
            avg_satisfaction = sum(metrics['satisfaction_scores']) / len(metrics['satisfaction_scores'])
        
        # Remove temporary tracking list
        del metrics['satisfaction_scores']
        
        return {
            'error': None,
            'metrics': metrics,
            'average_satisfaction_index': avg_satisfaction,
            'invalid_records': invalid_records,
        }
    
    except FileNotFoundError:
        return {
            'error': f"File not found: {file_path}",
            'metrics': None,
            'invalid_records': []
        }
    except Exception as e:
        return {
            'error': f"Error reading CSV file: {str(e)}",
            'metrics': None,
            'invalid_records': []
        }


def print_summary(analysis: Dict) -> None:
    """Print a formatted summary of the analysis to console."""
    if analysis['error']:
        print(f"\nERROR: {analysis['error']}\n")
        return
    
    metrics = analysis['metrics']
    
    print("\n" + "=" * 70)
    print("INCIDENT FILE ANALYSIS SUMMARY")
    print("=" * 70)
    
    print(f"\nTotal Records Processed:      {metrics['total_processed']}")
    print(f"Valid Records:                {metrics['valid_records']}")
    print(f"Invalid Records:              {metrics['invalid_records']}")
    
    print(f"\n--- Breakdown by Category ---")
    print(f"  Complaints:                 {metrics['category_breakdown']['complaints']}")
    print(f"  Requests:                   {metrics['category_breakdown']['requests']}")
    print(f"  Operational Failures:       {metrics['category_breakdown']['operational_failures']}")
    
    print(f"\n--- Breakdown by Status ---")
    print(f"  Open:                       {metrics['status_breakdown']['open']}")
    print(f"  Closed:                     {metrics['status_breakdown']['closed']}")
    print(f"  Discarded:                  {metrics['status_breakdown']['discarded']}")
    
    if analysis['average_satisfaction_index'] is not None:
        print(f"\nAverage Satisfaction Index:   {analysis['average_satisfaction_index']:.2f} / 10")
    else:
        print(f"\nAverage Satisfaction Index:   N/A (no satisfaction scores recorded)")
    
    if metrics['invalid_records'] > 0:
        print(f"\n--- Invalid Records ---")
        for invalid in analysis['invalid_records'][:10]:  # Show first 10
            print(f"\n  Row {invalid['row_number']} (ID: {invalid['incident_id']}):")
            for error in invalid['errors']:
                print(f"    • {error}")
        
        if len(analysis['invalid_records']) > 10:
            print(f"\n  ... and {len(analysis['invalid_records']) - 10} more invalid records")
    
    print("\n" + "=" * 70 + "\n")


def export_to_csv(analysis: Dict, output_file: str = 'results.csv') -> bool:
    """Export analysis results to CSV file."""
    if analysis['error'] or not analysis['metrics']:
        print(f"Cannot export: {analysis['error']}")
        return False
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['Metric', 'Value'])
            
            # Write metrics
            metrics = analysis['metrics']
            writer.writerow(['', ''])
            writer.writerow(['SUMMARY METRICS', ''])
            writer.writerow(['Total Records Processed', metrics['total_processed']])
            writer.writerow(['Valid Records', metrics['valid_records']])
            writer.writerow(['Invalid Records', metrics['invalid_records']])
            
            writer.writerow(['', ''])
            writer.writerow(['CATEGORY BREAKDOWN', ''])
            writer.writerow(['Complaints', metrics['category_breakdown']['complaints']])
            writer.writerow(['Requests', metrics['category_breakdown']['requests']])
            writer.writerow(['Operational Failures', metrics['category_breakdown']['operational_failures']])
            
            writer.writerow(['', ''])
            writer.writerow(['STATUS BREAKDOWN', ''])
            writer.writerow(['Open', metrics['status_breakdown']['open']])
            writer.writerow(['Closed', metrics['status_breakdown']['closed']])
            writer.writerow(['Discarded', metrics['status_breakdown']['discarded']])
            
            writer.writerow(['', ''])
            if analysis['average_satisfaction_index'] is not None:
                writer.writerow(['Average Satisfaction Index', f"{analysis['average_satisfaction_index']:.2f}"])
            else:
                writer.writerow(['Average Satisfaction Index', 'N/A'])
            
            # Write invalid records details
            if analysis['invalid_records']:
                writer.writerow(['', ''])
                writer.writerow(['INVALID RECORDS', ''])
                writer.writerow(['Row Number', 'Incident ID', 'Errors'])
                for invalid in analysis['invalid_records']:
                    errors_text = ' | '.join(invalid['errors'])
                    writer.writerow([invalid['row_number'], invalid['incident_id'], errors_text])
        
        print(f"✓ Results exported to: {output_file}")
        return True
    except Exception as e:
        print(f"✗ Error exporting to CSV: {str(e)}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python analyze_incidents.py <csv_file_path>")
        print("Example: python analyze_incidents.py incidents.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    # Analyze the CSV
    analysis = analyze_csv(csv_file)
    
    # Print summary to console
    print_summary(analysis)
    
    # Ask about export
    if not analysis['error']:
        response = input("Export results to CSV? [y/n]: ").strip().lower()
        if response == 'y':
            export_to_csv(analysis, 'results.csv')
    
    # Output JSON for API parsing
    if analysis['error']:
        json_output = {
            'error': analysis['error'],
            'total_processed': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'category_breakdown': {'complaints': 0, 'requests': 0, 'operational_failures': 0},
            'status_breakdown': {'open': 0, 'closed': 0, 'discarded': 0},
            'average_satisfaction_index': None,
            'invalid_record_details': []
        }
    else:
        json_output = {
            'total_processed': analysis['metrics']['total_processed'],
            'valid_records': analysis['metrics']['valid_records'],
            'invalid_records': analysis['metrics']['invalid_records'],
            'category_breakdown': analysis['metrics']['category_breakdown'],
            'status_breakdown': analysis['metrics']['status_breakdown'],
            'average_satisfaction_index': analysis['average_satisfaction_index'],
            'invalid_record_details': analysis['invalid_records']
        }
    
    print(json.dumps(json_output))
    
    # Exit with appropriate code
    sys.exit(0 if not analysis['error'] else 1)


if __name__ == '__main__':
    main()
