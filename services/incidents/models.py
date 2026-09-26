from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional


class Carrier(str, Enum):
    UPS = "UPS"
    FEDEX = "FedEx"
    DHL = "DHL"
    MRW = "MRW"
    SEUR = "SEUR"


class IncidentCategory(str, Enum):
    LOST_PARCEL = "LOST_PARCEL"
    DELAYED = "DELAYED"
    DAMAGED = "DAMAGED"
    RETURNED = "RETURNED"
    WRONG_ITEM = "WRONG_ITEM"
    ADDRESS_ISSUE = "ADDRESS_ISSUE"
    MISSING_LABEL = "MISSING_LABEL"
    CUSTOMER_CANCELLATION = "CUSTOMER_CANCELLATION"


class RecordStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    EXCEPTION = "exception"


class TRFRecord(BaseModel):
    """TrackFlow TRF (Tracking Record Format) record."""
    tracking_id: str = Field(min_length=1)
    carrier: Carrier
    category: IncidentCategory
    status: RecordStatus
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    shipment_date: str  # YYYY-MM-DD
    delivery_date: Optional[str] = None  # YYYY-MM-DD if provided
    weight_kg: float = Field(gt=0)
    declared_value: float = Field(gt=0)
    customer_name: str = Field(min_length=1)
    customer_email: str = Field(min_length=3)
    notes: Optional[str] = None


class AnalysisMetrics(BaseModel):
    """Analysis metrics computed from a TRF CSV file."""
    total_processed: int
    valid_records: int
    invalid_records: int
    carrier_breakdown: dict
    category_breakdown: dict
    status_breakdown: dict
    average_declared_value: Optional[float] = None


class InvalidRecordDetail(BaseModel):
    row_number: int
    tracking_id: str
    errors: list[str]


class AnalysisResult(BaseModel):
    """Complete analysis result for a TRF CSV upload."""
    id: str
    timestamp: int
    filename: str
    metrics: AnalysisMetrics
    invalid_records: list[InvalidRecordDetail]
    valid_record_count: int