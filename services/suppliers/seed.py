from pathlib import Path
from tinydb import TinyDB

from .data import INITIAL_SUPPLIERS, with_timestamp
from .models import SupplierInput

DB_PATH = Path(__file__).with_name("suppliers.json")


def seed() -> int:
    db = TinyDB(DB_PATH)
    inserted = 0
    existing_names = {record["name"] for record in db.all()}
    for raw_supplier in INITIAL_SUPPLIERS:
        supplier = SupplierInput.model_validate(raw_supplier)
        if supplier.name in existing_names:
            continue
        db.insert(with_timestamp(supplier.model_dump(mode="json")))
        existing_names.add(supplier.name)
        inserted += 1
    db.close()
    print(f"Inserted {inserted} suppliers.")
    return inserted


if __name__ == "__main__":
    seed()
