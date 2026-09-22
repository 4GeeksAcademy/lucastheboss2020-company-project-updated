SEED_SUPPLIERS = [
    {"name": "LogiTrans GmbH", "country": "Germany", "product_categories": ["Pallets", "Containers"], "rate": 24.50, "status": "active"},
    {"name": "FastFreight BV", "country": "Netherlands", "product_categories": ["Express", "Documents"], "rate": 18.00, "status": "active"},
    {"name": "CargoLink Spain SL", "country": "Spain", "product_categories": ["Fragile", "Pallets"], "rate": 22.00, "status": "active"},
    {"name": "EuroTruck Logistics", "country": "France", "product_categories": ["Bulk", "Containers"], "rate": 30.00, "status": "active"},
    {"name": "AirSpeed Couriers", "country": "UK", "product_categories": ["Express", "Documents"], "rate": 45.00, "status": "suspended"},
]

from .data import get_all, create


def main():
    existing = get_all()
    existing_names = {s["name"] for s in existing}

    inserted = 0
    skipped = 0

    for record in SEED_SUPPLIERS:
        if record["name"] in existing_names:
            skipped += 1
        else:
            create(dict(record))
            inserted += 1

    total = len(get_all())
    print(f"Suppliers seeded: {inserted} inserted, {skipped} skipped.")
    print(f"Total suppliers in database: {total}")


if __name__ == "__main__":
    main()