from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.shared.incident_validation import validate_manager_text


class IncidentCategory(str, Enum):
    LOST_PARCEL = "lost_parcel"
    DELIVERY_FAILURE = "delivery_failure"
    INVENTORY_DISCREPANCY = "inventory_discrepancy"
    CARRIER_ISSUE = "carrier_issue"
    RETURNS_ISSUE = "returns_issue"
    WAREHOUSE_INCIDENT = "warehouse_incident"
    SYSTEM_FAILURE = "system_failure"
    CLIENT_COMPLAINT = "client_complaint"
    OTHER = "other"


class IncidentStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISCARDED = "discarded"


class IncidentOrigin(str, Enum):
    CUSTOMER = "customer"
    BRANCH = "branch"
    INTERNAL = "internal"


class IncidentBranch(str, Enum):
    CENTRAL = "central"
    LA_WAREHOUSE = "la_warehouse"
    LA_OFFICE = "la_office"
    ZARAGOZA_WAREHOUSE = "zaragoza_warehouse"
    ZARAGOZA_OFFICE = "zaragoza_office"


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    category: IncidentCategory
    origin: IncidentOrigin
    branch: IncidentBranch

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        return validate_manager_text("title", value)

    @field_validator("description")
    @classmethod
    def require_description(cls, value: str) -> str:
        return validate_manager_text("description", value)


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class IncidentRecord(IncidentCreate):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


ALLOWED_STATUS_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.OPEN: {IncidentStatus.IN_PROGRESS, IncidentStatus.DISCARDED},
    IncidentStatus.IN_PROGRESS: {IncidentStatus.RESOLVED, IncidentStatus.DISCARDED},
    IncidentStatus.RESOLVED: set(),
    IncidentStatus.DISCARDED: set(),
}


def utc_isoformat(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
