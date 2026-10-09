from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from backend.auth import get_current_user
from services.database import engine
from services.models import SKU, StockEntry, StockExit
from services.routers.inventory import _current_stock
from services.tests.conftest import TEST_USER


def sku_payload(**overrides):
    payload = {
        "name": "Classic White Sneaker - Size 42",
        "sku": "CLT-SNK-W-42",
        "client_name": "PureStep Footwear",
        "category": "fashion",
        "warehouse": "LA",
    }
    payload.update(overrides)
    return payload


def create_sku(client, **overrides):
    response = client.post("/inventory/products", json=sku_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def create_entry(client, sku_id, quantity, reference, warehouse="LA"):
    return client.post(
        "/inventory/orders/inbound",
        json={"sku_id": sku_id, "quantity": quantity, "reference": reference, "warehouse": warehouse},
    )


def test_all_inventory_endpoints_require_tinydb_auth(inventory_client):
    client = inventory_client
    db_dependency = client.app.dependency_overrides[get_current_user]
    client.app.dependency_overrides.pop(get_current_user)
    try:
        requests = [
            client.get("/inventory/products"),
            client.post("/inventory/products", json=sku_payload()),
            client.get("/inventory/products/1"),
            client.post("/inventory/orders/inbound", json={"sku_id": 1, "quantity": 1, "reference": "R-1", "warehouse": "LA"}),
            client.post("/inventory/orders/outbound", json={"sku_id": 1, "quantity": 1, "exit_type": "loss", "tracking_number": None, "warehouse": "LA"}),
            client.get("/inventory/orders"),
        ]
        assert [response.status_code for response in requests] == [401] * 6
    finally:
        client.app.dependency_overrides[get_current_user] = db_dependency


def test_product_create_list_and_detail_compute_stock(inventory_client):
    los_angeles = create_sku(inventory_client)
    zaragoza = create_sku(
        inventory_client,
        sku="CLT-SNK-W-42-Z",
        warehouse="ZGZ",
    )
    assert create_entry(inventory_client, los_angeles["id"], 20, "GR-LA-001").status_code == 201
    assert create_entry(inventory_client, zaragoza["id"], 15, "GR-ZGZ-001", "ZGZ").status_code == 201

    products = inventory_client.get("/inventory/products")
    product = inventory_client.get(f"/inventory/products/{los_angeles['id']}")

    assert products.status_code == 200
    assert {(item["warehouse"], item["current_stock"]) for item in products.json()} == {("LA", 20), ("ZGZ", 15)}
    assert product.status_code == 200
    assert product.json()["current_stock"] == 20
    assert "current_stock" not in SKU.__table__.columns


def test_duplicate_sku_code_in_same_warehouse_returns_conflict(inventory_client):
    create_sku(inventory_client)

    duplicate = inventory_client.post("/inventory/products", json=sku_payload())

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "A SKU with this code already exists in that warehouse."


def test_inbound_records_authenticated_user_and_joined_sku(inventory_client):
    product = create_sku(inventory_client)

    response = inventory_client.post(
        "/inventory/orders/inbound",
        json={
            "sku_id": product["id"],
            "quantity": 17,
            "reference": "PO-2024-0098",
            "warehouse": "LA",
            "user_uuid": "forged-client-user",
        },
    )
    orders = inventory_client.get("/inventory/orders")

    assert response.status_code == 201
    assert response.json()["user_uuid"] == TEST_USER["id"]
    assert response.json()["sku"]["sku"] == product["sku"]
    assert orders.status_code == 200
    assert orders.json()[0]["movement_type"] == "inbound"
    assert orders.json()[0]["sku"]["client_name"] == "PureStep Footwear"


def test_outbound_cannot_oversell_and_failure_does_not_persist(inventory_client):
    product = create_sku(inventory_client)
    assert create_entry(inventory_client, product["id"], 10, "GR-LA-010").status_code == 201
    before_count = len(inventory_client.get("/inventory/orders").json())

    response = inventory_client.post(
        "/inventory/orders/outbound",
        json={
            "sku_id": product["id"],
            "quantity": 11,
            "exit_type": "dispatch",
            "tracking_number": "1Z999AA10123456784",
            "warehouse": "LA",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Insufficient stock for SKU 'CLT-SNK-W-42'. Available: 10, requested: 11."
    )
    assert len(inventory_client.get("/inventory/orders").json()) == before_count


def test_outbound_dispatch_and_loss_tracking_rules(inventory_client):
    product = create_sku(inventory_client)
    assert create_entry(inventory_client, product["id"], 10, "GR-LA-011").status_code == 201

    missing_tracking = inventory_client.post(
        "/inventory/orders/outbound",
        json={"sku_id": product["id"], "quantity": 2, "exit_type": "dispatch", "warehouse": "LA"},
    )
    tracking_on_loss = inventory_client.post(
        "/inventory/orders/outbound",
        json={"sku_id": product["id"], "quantity": 2, "exit_type": "loss", "tracking_number": "TRACK123", "warehouse": "LA"},
    )
    dispatch = inventory_client.post(
        "/inventory/orders/outbound",
        json={"sku_id": product["id"], "quantity": 3, "exit_type": "dispatch", "tracking_number": "1Z999AA10123456784", "warehouse": "LA"},
    )
    loss = inventory_client.post(
        "/inventory/orders/outbound",
        json={"sku_id": product["id"], "quantity": 2, "exit_type": "loss", "tracking_number": None, "warehouse": "LA"},
    )

    assert missing_tracking.status_code == 422
    assert tracking_on_loss.status_code == 422
    assert dispatch.status_code == 201
    assert loss.status_code == 201
    assert loss.json()["tracking_number"] is None
    orders = inventory_client.get("/inventory/orders").json()
    outbound = [order for order in orders if order["movement_type"] == "outbound"]
    product_detail = inventory_client.get(f"/inventory/products/{product['id']}").json()
    assert len(outbound) == 2
    assert all(order["sku"]["sku"] == product["sku"] for order in outbound)
    assert product_detail["current_stock"] == 5


def test_order_rejects_unknown_sku_and_wrong_warehouse(inventory_client):
    missing = create_entry(inventory_client, 99999, 1, "GR-NO-SKU")
    product = create_sku(inventory_client)
    mismatch = create_entry(inventory_client, product["id"], 1, "GR-WRONG-WH", "ZGZ")

    assert missing.status_code == 404
    assert mismatch.status_code == 400


def test_database_foreign_key_rejects_orphan_movement(inventory_client):
    with Session(engine) as session:
        session.add(StockEntry(sku_id=99999, quantity=1, reference="ORPHAN", warehouse="LA", user_uuid=TEST_USER["id"]))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Foreign key allowed a movement without a SKU")


def test_database_checks_reject_invalid_exit_invariant(inventory_client):
    product = create_sku(inventory_client)
    with Session(engine) as session:
        session.add(StockExit(
            sku_id=product["id"],
            quantity=1,
            exit_type="dispatch",
            tracking_number=None,
            warehouse="LA",
            user_uuid=TEST_USER["id"],
        ))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Database allowed a dispatch without a tracking number")


def test_stock_helper_is_scoped_by_sku_and_warehouse(inventory_client):
    la_product = create_sku(inventory_client, sku="SAME-CLIENT-PRODUCT", warehouse="LA")
    zgz_product = create_sku(inventory_client, sku="SAME-CLIENT-PRODUCT-ZGZ", warehouse="ZGZ")
    create_entry(inventory_client, la_product["id"], 20, "GR-LA-020", "LA")
    create_entry(inventory_client, zgz_product["id"], 15, "GR-ZGZ-015", "ZGZ")

    with Session(engine) as session:
        assert _current_stock(session, la_product["id"], "LA") == 20
        assert _current_stock(session, zgz_product["id"], "ZGZ") == 15
