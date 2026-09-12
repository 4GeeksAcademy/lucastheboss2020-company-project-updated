from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class SupplierInput(BaseModel):
    name: str = Field(min_length=2)
    country: str = Field(min_length=2)
    product_categories: list[str] = Field(min_length=1)
    rate: float = Field(gt=0)
    status: SupplierStatus = SupplierStatus.ACTIVE

    @field_validator("name", "country")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class Supplier(SupplierInput):
    id: int
    updated_at: datetime


class RateUpdate(BaseModel):
    rate: float = Field(gt=0)


class StatusUpdate(BaseModel):
    status: SupplierStatus


class SupplierResponse(Supplier):
    pass
