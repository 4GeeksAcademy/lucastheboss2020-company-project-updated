from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
from typing import Optional
from datetime import datetime, timezone


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


VALID_CATEGORIES = [
    "carrier_last_mile",
    "carrier_international",
    "warehouse_supplies",
    "packaging_materials",
    "reverse_logistics",
    "fleet_maintenance",
    "it_and_wms_software",
    "cleaning_and_facilities",
]

VALID_STATUSES = ["active", "suspended"]

COUNTRY_CURRENCY_MAP = {
    "USA": "USD",
    "Spain": "EUR",
}


class SupplierInput(BaseModel):
    name: str = Field(min_length=2)
    country: str = Field(min_length=2)
    categories: list[str] = Field(min_length=1)
    rate_per_shipment: float = Field(gt=0)
    currency: str = Field(min_length=3)
    status: SupplierStatus = SupplierStatus.ACTIVE
    service_zone: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        allowed = list(COUNTRY_CURRENCY_MAP.keys())
        if v not in allowed:
            raise ValueError(f"Country must be one of: {', '.join(allowed)}")
        return v

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: list[str]) -> list[str]:
        invalid = [c for c in v if c not in VALID_CATEGORIES]
        if invalid:
            raise ValueError(
                f"Invalid categories: {invalid}. Must be one of: {', '.join(VALID_CATEGORIES)}"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: SupplierStatus) -> SupplierStatus:
        if v.value not in VALID_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(VALID_STATUSES)}")
        return v

    @model_validator(mode="after")
    def validate_currency_country_pair(self):
        expected = COUNTRY_CURRENCY_MAP.get(self.country)
        if expected and self.currency != expected:
            raise ValueError(
                f"Currency '{self.currency}' does not match country '{self.country}'. "
                f"Expected '{expected}'."
            )
        return self


class Supplier(SupplierInput):
    id: int
    updated_at: str


class RateUpdate(BaseModel):
    rate_per_shipment: float = Field(gt=0)


class StatusUpdate(BaseModel):
    status: SupplierStatus