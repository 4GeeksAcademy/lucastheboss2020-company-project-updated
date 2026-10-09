#!/usr/bin/env python3
"""Seed the local TrackFlow inventory database with the Milestone 5 demo data."""

import sys
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from tinydb import Query

from services.database import engine, tinydb_users
from services.models import SKU, StockEntry, StockExit

SEED_SKUS = [
    {
        "name": "Classic White Sneaker - Size 42",
        "sku": "CLT-SNK-W-42",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "LA",
    },
    {
        "name": "Classic White Sneaker - Size 42",
        "sku": "CLT-SNK-W-42-Z",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "ZGZ",
    },
    {
        "name": "Wireless Earbuds Pro",
        "sku": "TEC-EAR-001",
        "client_name": "SoundWave Electronics",
        "category": "electronics",
        "warehouse": "LA",
    },
    {
        "name": "Hydrating Face Serum 30ml",
        "sku": "CSM-SRM-030",
        "client_name": "GlowLab Cosmetics",
        "category": "cosmetics",
        "warehouse": "ZGZ",
    },
    {
        "name": "Slim Fit Chino - Navy 32/32",
        "sku": "CLT-CHN-N-32",
        "client_name": "UrbanThread",
        "category": "fashion",
        "warehouse": "LA",
    },
    {
        "name": "USB-C Fast Charger 65W",
        "sku": "TEC-CHG-065",
        "client_name": "SoundWave Electronics",
        "category": "electronics",
        "warehouse": "ZGZ",
    },
]

SEED_ENTRIES = [
    {"sku": "CLT-SNK-W-42", "warehouse": "LA", "quantity": 40, "reference": "PO-2024-0098"},
    {"sku": "CLT-SNK-W-42", "warehouse": "LA", "quantity": 12, "reference": "GR-LA-0234"},
    {"sku": "CLT-SNK-W-42-Z", "warehouse": "ZGZ", "quantity": 30, "reference": "PO-ZGZ-0051"},
    {"sku": "TEC-EAR-001", "warehouse": "LA", "quantity": 25, "reference": "PO-LA-2210"},
    {"sku": "CSM-SRM-030", "warehouse": "ZGZ", "quantity": 48, "reference": "PO-ZGZ-3812"},
    {"sku": "CLT-CHN-N-32", "warehouse": "LA", "quantity": 36, "reference": "PO-LA-1002"},
    {"sku": "TEC-CHG-065", "warehouse": "ZGZ", "quantity": 16, "reference": "PO-ZGZ-2401"},
]

SEED_EXITS = [
    {
        "sku": "CLT-SNK-W-42",
        "warehouse": "LA",
        "quantity": 8,
        "exit_type": "dispatch",
        "tracking_number": "1Z999AA10123456784",
    },
    {
        "sku": "CLT-SNK-W-42-Z",
        "warehouse": "ZGZ",
        "quantity": 3,
        "exit_type": "dispatch",
        "tracking_number": "MRW202410080001",
    },
    {
        "sku": "TEC-EAR-001",
        "warehouse": "LA",
        "quantity": 2,
        "exit_type": "loss",
        "tracking_number": None,
    },
    {
        "sku": "CSM-SRM-030",
        "warehouse": "ZGZ",
        "quantity": 5,
        "exit_type": "dispatch",
        "tracking_number": "SEUR202410080002",
    },
    {
        "sku": "CLT-CHN-N-32",
        "warehouse": "LA",
        "quantity": 1,
        "exit_type": "loss",
        "tracking_number": None,
    },
]


def _seed_already_present(session: Session, sku_ids: dict[tuple[str, str], int]) -> bool:
    existing_skus = session.exec(select(SKU)).all()
    existing_entries = session.exec(select(StockEntry)).all()
    existing_exits = session.exec(select(StockExit)).all()
    if not existing_skus and not existing_entries and not existing_exits:
        return False

    expected_skus = {(record["sku"], record["warehouse"]) for record in SEED_SKUS}
    actual_skus = {(record.sku, record.warehouse) for record in existing_skus}
    if not expected_skus.issubset(actual_skus):
        raise ValueError("Inventory database is not empty and the complete demo seed is not present; refusing to mix seed data.")

    expected_entries = {
        (sku_ids[(record["sku"], record["warehouse"])], record["quantity"], record["reference"], record["warehouse"])
        for record in SEED_ENTRIES
    }
    actual_entries = {
        (record.sku_id, record.quantity, record.reference, record.warehouse)
        for record in existing_entries
    }
    expected_exits = {
        (
            sku_ids[(record["sku"], record["warehouse"])],
            record["quantity"],
            record["exit_type"],
            record["tracking_number"],
            record["warehouse"],
        )
        for record in SEED_EXITS
    }
    actual_exits = {
        (record.sku_id, record.quantity, record.exit_type, record.tracking_number, record.warehouse)
        for record in existing_exits
    }
    if expected_entries.issubset(actual_entries) and expected_exits.issubset(actual_exits):
        return True
    raise ValueError("Inventory database contains partial demo data; refusing to create duplicate or mixed seed rows.")


def seed_inventory(session: Session, user_uuid: str) -> dict[str, Any]:
    if not user_uuid:
        raise ValueError("An authenticated TinyDB user is required to attribute stock movements.")

    try:
        existing_skus = session.exec(select(SKU)).all()
        sku_ids = {(record.sku, record.warehouse): record.id for record in existing_skus}
        if _seed_already_present(session, sku_ids):
            return {"inserted": False, "skus": len(SEED_SKUS), "entries": len(SEED_ENTRIES), "exits": len(SEED_EXITS)}
        if existing_skus:
            raise ValueError("Inventory database must be empty before seeding.")

        product_ids: dict[tuple[str, str], int] = {}
        for sku_data in SEED_SKUS:
            product = SKU(**sku_data)
            session.add(product)
            session.flush()
            product_ids[(product.sku, product.warehouse)] = product.id

        for entry_data in SEED_ENTRIES:
            product_key = (entry_data["sku"], entry_data["warehouse"])
            session.add(StockEntry(
                sku_id=product_ids[product_key],
                quantity=entry_data["quantity"],
                reference=entry_data["reference"],
                warehouse=entry_data["warehouse"],
                user_uuid=user_uuid,
            ))

        for exit_data in SEED_EXITS:
            product_key = (exit_data["sku"], exit_data["warehouse"])
            session.add(StockExit(
                sku_id=product_ids[product_key],
                quantity=exit_data["quantity"],
                exit_type=exit_data["exit_type"],
                tracking_number=exit_data["tracking_number"],
                warehouse=exit_data["warehouse"],
                user_uuid=user_uuid,
            ))

        session.commit()
        return {"inserted": True, "skus": len(SEED_SKUS), "entries": len(SEED_ENTRIES), "exits": len(SEED_EXITS)}
    except Exception:
        session.rollback()
        raise


def main() -> int:
    active_users = tinydb_users.search(Query().is_active == True)  # noqa: E712
    if not active_users:
        print("No active TinyDB user exists. Register an operator before seeding inventory.", file=sys.stderr)
        return 1

    try:
        with Session(engine) as session:
            result = seed_inventory(session, str(active_users[0]["id"]))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print("Inventory seed failed while writing to the database.", file=sys.stderr)
        return 1

    action = "already seeded" if not result["inserted"] else "seeded"
    print(f"Inventory {action}: {result['skus']} SKUs, {result['entries']} inbound entries, {result['exits']} outbound exits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
