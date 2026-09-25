from pydantic import BaseModel, Field, field_validator
from enum import Enum


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


TRACKFLOW_SERVICES = ["warehouse-management", "last-mile-delivery", "reverse-logistics"]
CURRENCIES = ["USD", "EUR"]
COUNTRIES = ["United States", "Spain"]


class SupplierInput(BaseModel):
    name: str = Field(min_length=2)
    country: str = Field(min_length=2)
    services: list[str] = Field(min_length=1)
    rate_per_shipment: float = Field(gt=0)
    currency: str = Field(min_length=3, default="USD")
    status: SupplierStatus = SupplierStatus.ACTIVE

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        if v not in COUNTRIES:
            raise ValueError(f"Country must be one of: {', '.join(COUNTRIES)}")
        return v

    @field_validator("services")
    @classmethod
    def validate_services(cls, v: list[str]) -> list[str]:
        invalid = [s for s in v if s not in TRACKFLOW_SERVICES]
        if invalid:
            raise ValueError(
                f"Invalid services: {invalid}. Must be one of: {', '.join(TRACKFLOW_SERVICES)}"
            )
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v not in CURRENCIES:
            raise ValueError(f"Currency must be one of: {', '.join(CURRENCIES)}")
        return v


class Supplier(SupplierInput):
    id: int
    updated_at: str


class RateUpdate(BaseModel):
    rate_per_shipment: float = Field(gt=0)


class StatusUpdate(BaseModel):
    status: SupplierStatus