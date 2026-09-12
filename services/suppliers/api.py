from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from tinydb import TinyDB, Query as TinyQuery

from .models import RateUpdate, StatusUpdate, Supplier, SupplierInput
from .seed import DB_PATH, seed

app = FastAPI(title="TrackFlow Supplier Management API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])


def database() -> TinyDB:
    if not Path(DB_PATH).exists():
        seed()
    return TinyDB(DB_PATH)


def to_supplier(record: dict) -> Supplier:
    data = dict(record)
    return Supplier(id=int(record.doc_id), **data)


@app.on_event("startup")
def seed_on_startup() -> None:
    seed()


@app.post("/suppliers", response_model=Supplier, status_code=201)
def create_supplier(payload: SupplierInput) -> Supplier:
    db = database()
    if db.search(TinyQuery().name == payload.name):
        db.close()
        raise HTTPException(status_code=409, detail="A supplier with this name already exists")
    record = {**payload.model_dump(mode="json"), "updated_at": datetime.now(timezone.utc).isoformat()}
    doc_id = db.insert(record)
    db.close()
    return Supplier(id=doc_id, **record)


@app.get("/suppliers", response_model=list[Supplier])
def list_suppliers(
    country: str | None = None,
    category: str | None = Query(default=None),
) -> list[Supplier]:
    db = database()
    records = db.all()
    db.close()
    if country:
        records = [record for record in records if record["country"].casefold() == country.casefold()]
    if category:
        records = [record for record in records if any(item.casefold() == category.casefold() for item in record["product_categories"])]
    return [to_supplier(record) for record in records]


@app.get("/suppliers/{supplier_id}", response_model=Supplier)
def get_supplier(supplier_id: int) -> Supplier:
    db = database()
    record = db.get(doc_id=supplier_id)
    db.close()
    if record is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return to_supplier(record)


@app.patch("/suppliers/{supplier_id}/rate", response_model=Supplier)
def update_rate(supplier_id: int, payload: RateUpdate) -> Supplier:
    db = database()
    record = db.get(doc_id=supplier_id)
    if record is None:
        db.close()
        raise HTTPException(status_code=404, detail="Supplier not found")
    updated_at = datetime.now(timezone.utc).isoformat()
    db.update({"rate": payload.rate, "updated_at": updated_at}, doc_ids=[supplier_id])
    record.update(rate=payload.rate, updated_at=updated_at)
    db.close()
    return to_supplier({**record, "doc_id": supplier_id})


@app.patch("/suppliers/{supplier_id}/status", response_model=Supplier)
def update_status(supplier_id: int, payload: StatusUpdate) -> Supplier:
    db = database()
    record = db.get(doc_id=supplier_id)
    if record is None:
        db.close()
        raise HTTPException(status_code=404, detail="Supplier not found")
    db.update({"status": payload.status.value}, doc_ids=[supplier_id])
    record["status"] = payload.status.value
    db.close()
    return to_supplier({**record, "doc_id": supplier_id})


@app.delete("/suppliers/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int) -> None:
    db = database()
    if db.get(doc_id=supplier_id) is None:
        db.close()
        raise HTTPException(status_code=404, detail="Supplier not found")
    db.remove(doc_ids=[supplier_id])
    db.close()
