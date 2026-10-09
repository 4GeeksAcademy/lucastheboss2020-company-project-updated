from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Warehouse = Literal["LA", "ZGZ"]
Category = Literal["fashion", "electronics", "cosmetics"]
ExitType = Literal["dispatch", "loss"]


class SKUCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    sku: str = Field(min_length=1, max_length=80)
    client_name: str = Field(min_length=1, max_length=160)
    category: Category
    warehouse: Warehouse

    @field_validator("name", "sku", "client_name")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class SKUSummary(BaseModel):
    id: int
    name: str
    sku: str
    client_name: str
    category: Category
    warehouse: Warehouse

    model_config = ConfigDict(from_attributes=True)


class SKURead(SKUSummary):
    current_stock: int


class StockEntryCreate(BaseModel):
    sku_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    reference: str = Field(min_length=1, max_length=120)
    warehouse: Warehouse

    @field_validator("reference")
    @classmethod
    def trim_reference(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reference cannot be blank")
        return value


class StockEntryRead(BaseModel):
    id: int
    sku_id: int
    quantity: int
    reference: str
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str
    sku: SKUSummary


class StockExitCreate(BaseModel):
    sku_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    exit_type: ExitType
    tracking_number: str | None = Field(default=None, min_length=1, max_length=120)
    warehouse: Warehouse

    @field_validator("tracking_number", mode="before")
    @classmethod
    def trim_tracking_number(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_tracking_number(self):
        if self.exit_type == "dispatch" and not self.tracking_number:
            raise ValueError("tracking_number is required for dispatch exits")
        if self.exit_type == "loss" and self.tracking_number is not None:
            raise ValueError("tracking_number must be null for loss exits")
        return self


class StockExitRead(BaseModel):
    id: int
    sku_id: int
    quantity: int
    exit_type: ExitType
    tracking_number: str | None
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str
    sku: SKUSummary


class InventoryOrderRead(BaseModel):
    movement_type: Literal["inbound", "outbound"]
    id: int
    sku_id: int
    quantity: int
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str
    sku: SKUSummary
    reference: str | None = None
    exit_type: ExitType | None = None
    tracking_number: str | None = None
