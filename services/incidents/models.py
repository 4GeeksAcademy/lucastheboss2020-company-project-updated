from pydantic import BaseModel, Field
from typing import Optional


class TrackFlowRecord(BaseModel):
    """TrackFlow logistics incident record."""
    incident_id: str = Field(min_length=1)
    date: str  # YYYY-MM-DD
    country: str = Field(pattern=r"^(US|ES)$")
    customer_type: str = Field(pattern=r"^(B2B|B2C)$")
    tracking_number: str = Field(min_length=8)
    carrier: str
    category: str
    description: str = Field(min_length=5)
    status: str = Field(pattern=r"^(OPEN|CLOSED|DISCARDED)$")
    customer_email: str = Field(min_length=1)
    satisfaction_score: Optional[int] = Field(default=None, ge=1, le=5)


class AnalysisMetrics(BaseModel):
    """Analysis metrics computed from a TrackFlow CSV file."""
    total_processed: int
    valid_records: int
    invalid_records: int
    carrier_breakdown: dict[str, int]
    category_breakdown: dict[str, int]
    status_breakdown: dict[str, int]
    country_breakdown: dict[str, int]
    average_satisfaction_index: Optional[float] = None
    invalid_breakdown: dict[str, int]


class InvalidRecordDetail(BaseModel):
    """Details of an invalid record."""
    row_number: int
    incident_id: str
    errors: list[str]


class AnalysisResult(BaseModel):
    """Complete analysis result."""
    id: str
    timestamp: int
    filename: str
    format: str = "trackflow"
    metrics: AnalysisMetrics
    invalid_records: list[InvalidRecordDetail]
    valid_record_count: int
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