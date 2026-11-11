from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, UniqueConstraint
from sqlmodel import Field, SQLModel


class SKU(SQLModel, table=True):
    __tablename__ = "inventory_skus"
    __table_args__ = (
        UniqueConstraint("sku", "warehouse", name="uq_inventory_sku_warehouse"),
        CheckConstraint("category IN ('fashion', 'electronics', 'cosmetics')", name="ck_inventory_sku_category"),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_inventory_sku_warehouse"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=240)
    sku: str = Field(min_length=1, max_length=80, index=True)
    client_name: str = Field(min_length=1, max_length=160)
    category: str = Field(max_length=32)
    warehouse: str = Field(max_length=3, index=True)


class StockEntry(SQLModel, table=True):
    __tablename__ = "inventory_stock_entries"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_entry_positive_quantity"),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stock_entry_warehouse"),
        UniqueConstraint("warehouse", "reference", name="uq_stock_entry_reference_warehouse"),
    )

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key="inventory_skus.id", index=True)
    quantity: int = Field(gt=0)
    reference: str = Field(min_length=1, max_length=120)
    warehouse: str = Field(max_length=3, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    )
    user_uuid: str = Field(min_length=1, max_length=64, index=True)


class StockExit(SQLModel, table=True):
    __tablename__ = "inventory_stock_exits"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_exit_positive_quantity"),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stock_exit_warehouse"),
        CheckConstraint("exit_type IN ('dispatch', 'loss')", name="ck_stock_exit_type"),
        CheckConstraint(
            "(exit_type = 'dispatch' AND tracking_number IS NOT NULL) OR "
            "(exit_type = 'loss' AND tracking_number IS NULL)",
            name="ck_stock_exit_tracking_by_type",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(foreign_key="inventory_skus.id", index=True)
    quantity: int = Field(gt=0)
    exit_type: str = Field(max_length=16)
    tracking_number: str | None = Field(default=None, max_length=120)
    warehouse: str = Field(max_length=3, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)),
    )
    user_uuid: str = Field(min_length=1, max_length=64, index=True)
