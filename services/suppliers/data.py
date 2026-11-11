from tinydb import TinyDB, Query
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
db = TinyDB(DATA_DIR / "suppliers.json")
table = db.table("suppliers")
query = Query()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_id() -> int:
    all_records = table.all()
    return max((r["id"] for r in all_records), default=0) + 1


def get_all() -> list[dict]:
    return table.all()


def get_one(supplier_id: int) -> dict | None:
    return table.get(query.id == supplier_id)


def create(data: dict) -> dict:
    data["id"] = _next_id()
    data["updated_at"] = _now()
    table.insert(data)
    return get_one(data["id"])


def update_rate(supplier_id: int, rate_per_shipment: float) -> dict | None:
    record = get_one(supplier_id)
    if not record:
        return None
    table.update({"rate_per_shipment": rate_per_shipment, "updated_at": _now()}, query.id == supplier_id)
    return get_one(supplier_id)


def update_status(supplier_id: int, status: str) -> dict | None:
    record = get_one(supplier_id)
    if not record:
        return None
    table.update({"status": status, "updated_at": _now()}, query.id == supplier_id)
    return get_one(supplier_id)


def delete_one(supplier_id: int) -> bool:
    record = get_one(supplier_id)
    if not record:
        return False
    table.remove(query.id == supplier_id)
    return True


def seed(records: list[dict]) -> None:
    for r in records:
        create(r)