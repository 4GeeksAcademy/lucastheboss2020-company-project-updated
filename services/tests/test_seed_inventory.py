from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from services import seed_inventory as seed_module
from services.database import engine
from services.models import SKU, StockEntry, StockExit
from services.routers.inventory import _current_stock
from services.seed_inventory import SEED_ENTRIES, SEED_EXITS, SEED_SKUS, seed_inventory


def test_seed_creates_context_records_with_real_user_and_per_warehouse_stock(inventory_client):
    with Session(engine) as session:
        result = seed_inventory(session, "existing-tinydb-user-uuid")
        products = session.exec(select(SKU)).all()
        entries = session.exec(select(StockEntry)).all()
        exits = session.exec(select(StockExit)).all()
        product_ids = {(product.sku, product.warehouse): product.id for product in products}
        la_stock = _current_stock(session, product_ids[("CLT-SNK-W-42", "LA")], "LA")
        zgz_stock = _current_stock(session, product_ids[("CLT-SNK-W-42-Z", "ZGZ")], "ZGZ")

    assert result == {"inserted": True, "skus": 6, "entries": 7, "exits": 5}
    assert len(products) == len(SEED_SKUS) == 6
    assert len(entries) == len(SEED_ENTRIES) >= 4
    assert len(exits) == len(SEED_EXITS) >= 3
    assert all(entry.user_uuid == "existing-tinydb-user-uuid" for entry in entries)
    assert all(exit_record.user_uuid == "existing-tinydb-user-uuid" for exit_record in exits)
    assert la_stock == 44
    assert zgz_stock == 27
    assert any(exit_record.exit_type == "dispatch" and exit_record.tracking_number for exit_record in exits)
    assert any(exit_record.exit_type == "loss" and exit_record.tracking_number is None for exit_record in exits)


def test_seed_is_safe_to_repeat_without_duplicate_rows(inventory_client):
    with Session(engine) as session:
        first = seed_inventory(session, "existing-tinydb-user-uuid")
        second = seed_inventory(session, "existing-tinydb-user-uuid")
        product_count = len(session.exec(select(SKU)).all())
        entry_count = len(session.exec(select(StockEntry)).all())
        exit_count = len(session.exec(select(StockExit)).all())

    assert first["inserted"] is True
    assert second["inserted"] is False
    assert (product_count, entry_count, exit_count) == (6, 7, 5)


def test_seed_requires_an_existing_user_uuid(inventory_client):
    with Session(engine) as session:
        with pytest.raises(ValueError, match="TinyDB user"):
            seed_inventory(session, "")


def test_seed_refuses_partial_inventory_without_mixing_data(inventory_client):
    with Session(engine) as session:
        session.add(SKU(**SEED_SKUS[0]))
        session.commit()
        with pytest.raises(ValueError, match="not empty"):
            seed_inventory(session, "existing-tinydb-user-uuid")
        assert len(session.exec(select(SKU)).all()) == 1
        assert session.exec(select(StockEntry)).all() == []


def test_seed_command_attributes_movements_to_active_tinydb_user(inventory_client, monkeypatch):
    tinydb_user = {"id": "real-tinydb-user-id", "is_active": True}
    monkeypatch.setattr(seed_module, "tinydb_users", SimpleNamespace(search=lambda _query: [tinydb_user]))

    assert seed_module.main() == 0

    with Session(engine) as session:
        entries = session.exec(select(StockEntry)).all()
        exits = session.exec(select(StockExit)).all()
    assert all(entry.user_uuid == tinydb_user["id"] for entry in entries)
    assert all(exit_record.user_uuid == tinydb_user["id"] for exit_record in exits)


def test_seed_command_refuses_to_run_without_active_tinydb_user(inventory_client, monkeypatch, capsys):
    monkeypatch.setattr(seed_module, "tinydb_users", SimpleNamespace(search=lambda _query: []))

    assert seed_module.main() == 1
    assert "No active TinyDB user exists" in capsys.readouterr().err

    with Session(engine) as session:
        assert session.exec(select(SKU)).all() == []
