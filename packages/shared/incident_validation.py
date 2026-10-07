"""Shared TrackFlow incident validation used by analyzer, seeder, and API."""

from datetime import datetime
from typing import Mapping

VALID_COUNTRIES = {"US", "ES"}
CARRIERS_BY_COUNTRY = {
    "US": {"UPS", "FEDEX", "DHL_US"},
    "ES": {"MRW", "SEUR", "DHL_ES", "LOCAL_ES"},
}
ALL_CARRIERS = CARRIERS_BY_COUNTRY["US"] | CARRIERS_BY_COUNTRY["ES"]
VALID_CATEGORIES = {
    "LOST_PARCEL",
    "DELAYED_DELIVERY",
    "WRONG_ADDRESS",
    "RETURN_REQUEST",
    "DAMAGE",
}
VALID_STATUSES = {"OPEN", "CLOSED", "DISCARDED"}
SATISFACTION_MIN = 1
SATISFACTION_MAX = 5


def validate_ymd(date_str: str) -> bool:
    """Return True if date_str is a valid YYYY-MM-DD date."""
    if not date_str or not date_str.strip():
        return False
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def has_at(email: str) -> bool:
    """Minimal email check -- must contain @."""
    return bool(email and "@" in email.strip())


def validate_record(row: Mapping[str, str]) -> list[str]:
    """Validate an analyzer CSV record without exposing its customer email."""
    errors: list[str] = []

    def field(name: str) -> str:
        value = row.get(name)
        return str(value).strip() if value is not None else ""

    incident_id = field("incident_id")
    date_str = field("date")
    country = field("country").upper()
    customer_type = field("customer_type").upper()
    tracking = field("tracking_number")
    carrier = field("carrier")
    category = field("category")
    description = field("description")
    status = field("status").upper()
    score_str = field("satisfaction_score")
    email = field("customer_email")

    if not incident_id:
        errors.append("Missing required field 'incident_id'")

    if not date_str:
        errors.append("Missing required field 'date'")
    elif not validate_ymd(date_str):
        errors.append(f"Invalid date '{date_str}'; must be YYYY-MM-DD")

    if not country:
        errors.append("Missing required field 'country'")
    elif country not in VALID_COUNTRIES:
        errors.append(f"Invalid country '{field('country')}'; must be US or ES")

    if not customer_type:
        errors.append("Missing required field 'customer_type'")
    elif customer_type not in ("B2B", "B2C"):
        errors.append(f"Invalid customer_type '{field('customer_type')}'; must be B2B or B2C")

    if not tracking:
        errors.append("Missing required field 'tracking_number'")
    elif len(tracking) < 8:
        errors.append(f"Invalid tracking number '{tracking}'; must be at least 8 characters")

    if not carrier:
        errors.append("Missing required field 'carrier'")
    elif carrier not in ALL_CARRIERS:
        errors.append(f"Invalid carrier '{carrier}'; unknown carrier")
    elif country in VALID_COUNTRIES and carrier not in CARRIERS_BY_COUNTRY.get(country, set()):
        errors.append(f"Carrier '{carrier}' not valid for country '{country}'")

    if not category:
        errors.append("Missing required field 'category'")
    elif category not in VALID_CATEGORIES:
        errors.append(f"Invalid category '{category}'; must be one of: {', '.join(sorted(VALID_CATEGORIES))}")

    if not description:
        errors.append("Missing required field 'description'")
    elif len(description) < 5:
        errors.append(f"Description too short ({len(description)} chars); minimum 5 characters")

    if not status:
        errors.append("Missing required field 'status'")
    elif status not in VALID_STATUSES:
        errors.append(f"Invalid status '{field('status')}'; must be one of: {', '.join(sorted(VALID_STATUSES))}")

    if not email:
        errors.append("Missing required field 'customer_email'")
    elif not has_at(email):
        errors.append("Invalid or missing customer_email")

    if status == "CLOSED":
        if not score_str:
            errors.append("Closed incident without satisfaction_score")
        else:
            try:
                score = int(score_str)
                if score < SATISFACTION_MIN or score > SATISFACTION_MAX:
                    errors.append(
                        f"Invalid satisfaction_score '{score_str}'; "
                        f"must be between {SATISFACTION_MIN} and {SATISFACTION_MAX}"
                    )
            except (ValueError, TypeError):
                errors.append(
                    f"Invalid satisfaction_score '{score_str}'; "
                    f"must be an integer between {SATISFACTION_MIN} and {SATISFACTION_MAX}"
                )
    elif score_str:
        try:
            score = int(score_str)
            if score < SATISFACTION_MIN or score > SATISFACTION_MAX:
                errors.append(
                    f"Invalid satisfaction_score '{score_str}'; "
                    f"must be between {SATISFACTION_MIN} and {SATISFACTION_MAX}"
                )
        except (ValueError, TypeError):
            pass

    return errors


def validate_manager_text(field: str, value: str) -> str:
    """Shared required-text validation for manager API and imported records."""
    if field == "title":
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be blank")
        if len(value) > 120:
            raise ValueError("Title must be no longer than 120 characters")
        return value
    if field == "description":
        if not value.strip():
            raise ValueError("Description cannot be blank")
        return value
    raise ValueError("Unsupported incident text field")
