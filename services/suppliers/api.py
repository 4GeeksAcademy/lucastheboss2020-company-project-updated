from fastapi import FastAPI, HTTPException, status
from .models import SupplierInput, RateUpdate, StatusUpdate
from .data import get_all, get_one, create, update_rate, update_status, delete_one

app = FastAPI(title="Suppliers API")


@app.get("/suppliers")
def list_suppliers(country: str = None, category: str = None):
    results = get_all()
    if country:
        results = [r for r in results if r.get("country", "").lower() == country.lower()]
    if category:
        results = [r for r in results if category.lower() in [c.lower() for c in r.get("product_categories", [])]]
    return results


@app.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int):
    record = get_one(supplier_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return record


@app.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierInput):
    data = payload.model_dump()
    data["status"] = data["status"].value
    return create(data)


@app.patch("/suppliers/{supplier_id}/rate")
def change_rate(supplier_id: int, payload: RateUpdate):
    record = update_rate(supplier_id, payload.rate)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return record


@app.patch("/suppliers/{supplier_id}/status")
def change_status(supplier_id: int, payload: StatusUpdate):
    record = update_status(supplier_id, payload.status.value)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return record


@app.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(supplier_id: int):
    if not delete_one(supplier_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")