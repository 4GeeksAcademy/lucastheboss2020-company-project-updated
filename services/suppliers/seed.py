SEED_SUPPLIERS = [
    # ── United States (USD) ──
    {
        "name": "LA Warehouse Partners",
        "country": "United States",
        "services": ["warehouse-management"],
        "rate_per_shipment": 4.50,
        "currency": "USD",
        "status": "active",
    },
    {
        "name": "Pacific Last Mile Co.",
        "country": "United States",
        "services": ["last-mile-delivery"],
        "rate_per_shipment": 6.75,
        "currency": "USD",
        "status": "active",
    },
    {
        "name": "West Coast Reverse Logistics",
        "country": "United States",
        "services": ["reverse-logistics"],
        "rate_per_shipment": 8.25,
        "currency": "USD",
        "status": "active",
    },
    {
        "name": "UPS Logistics Solutions",
        "country": "United States",
        "services": ["warehouse-management", "last-mile-delivery"],
        "rate_per_shipment": 5.00,
        "currency": "USD",
        "status": "active",
    },
    {
        "name": "FedEx Supply Chain",
        "country": "United States",
        "services": ["last-mile-delivery", "reverse-logistics"],
        "rate_per_shipment": 7.50,
        "currency": "USD",
        "status": "active",
    },
    {
        "name": "DHL Ecommerce US",
        "country": "United States",
        "services": ["warehouse-management", "last-mile-delivery", "reverse-logistics"],
        "rate_per_shipment": 5.80,
        "currency": "USD",
        "status": "active",
    },
    {
        "name": "California Freight Systems",
        "country": "United States",
        "services": ["warehouse-management"],
        "rate_per_shipment": 3.95,
        "currency": "USD",
        "status": "suspended",
    },
    {
        "name": "American Express Logistics",
        "country": "United States",
        "services": ["last-mile-delivery"],
        "rate_per_shipment": 9.00,
        "currency": "USD",
        "status": "active",
    },
    # ── Spain (EUR) ──
    {
        "name": "Zaragoza Almacenes",
        "country": "Spain",
        "services": ["warehouse-management"],
        "rate_per_shipment": 3.80,
        "currency": "EUR",
        "status": "active",
    },
    {
        "name": "MRW Paquetería",
        "country": "Spain",
        "services": ["last-mile-delivery"],
        "rate_per_shipment": 5.50,
        "currency": "EUR",
        "status": "active",
    },
    {
        "name": "SEUR Reverse Logistics",
        "country": "Spain",
        "services": ["reverse-logistics"],
        "rate_per_shipment": 7.20,
        "currency": "EUR",
        "status": "active",
    },
    {
        "name": "DHL Supply Chain Spain",
        "country": "Spain",
        "services": ["warehouse-management", "last-mile-delivery"],
        "rate_per_shipment": 4.90,
        "currency": "EUR",
        "status": "active",
    },
    {
        "name": "Logística del Mediterráneo",
        "country": "Spain",
        "services": ["warehouse-management", "reverse-logistics"],
        "rate_per_shipment": 6.10,
        "currency": "EUR",
        "status": "active",
    },
    {
        "name": "Iberian Last Mile Express",
        "country": "Spain",
        "services": ["last-mile-delivery"],
        "rate_per_shipment": 5.95,
        "currency": "EUR",
        "status": "suspended",
    },
    {
        "name": "Red Logistic Española",
        "country": "Spain",
        "services": ["warehouse-management", "last-mile-delivery", "reverse-logistics"],
        "rate_per_shipment": 6.50,
        "currency": "EUR",
        "status": "active",
    },
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