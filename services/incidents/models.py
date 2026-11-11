from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from typing import Optional


class TrackFlowRecord(BaseModel):
    """TrackFlow logistics incident record."""

    incident_id: str = Field(min_length=1)
    date: str
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
    """Metrics calculated from a TrackFlow incident CSV."""

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
    """Validation details for a CSV row; analyzer generations used two ID names."""

    model_config = ConfigDict(extra="ignore")

    row_number: int
    incident_id: str = Field(
        default="N/A",
        validation_alias=AliasChoices("incident_id", "tracking_id"),
    )
    errors: list[str]


class AnalysisResult(BaseModel):
    """Canonical stored analysis response used by the TrackFlow UI."""

    model_config = ConfigDict(extra="ignore")

    id: str
    timestamp: int
    filename: str
    format: str | None = None
    metrics: AnalysisMetrics
    invalid_records: list[InvalidRecordDetail] = Field(default_factory=list)
    valid_record_count: int


class AnalysisCreateRequest(BaseModel):
    """Validated analyzer payload accepted when storing a new result."""

    model_config = ConfigDict(extra="ignore")

    filename: str
    format: str | None = None
    metrics: AnalysisMetrics
    invalid_records: list[InvalidRecordDetail] = Field(default_factory=list)
    valid_record_count: int


class AnalysisListMetrics(BaseModel):
    """Record counts sufficient for a compact analysis-history row."""

    total_processed: int
    valid_records: int
    invalid_records: int


class AnalysisListItem(BaseModel):
    """Metadata and counts needed to select an analysis from history."""

    id: str
    timestamp: int
    filename: str
    format: str | None = None
    metrics: AnalysisListMetrics
