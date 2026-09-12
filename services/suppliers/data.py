from datetime import datetime, timezone

INITIAL_SUPPLIERS = [
    {"name": "West Coast Packaging", "country": "United States", "product_categories": ["Packaging", "Warehouse supplies"], "rate": 12.5, "status": "active"},
    {"name": "Zaragoza Fulfilment Materials", "country": "Spain", "product_categories": ["Packaging", "Labels"], "rate": 10.0, "status": "active"},
    {"name": "Iberia Transport Partners", "country": "Spain", "product_categories": ["Transport", "Last-mile delivery"], "rate": 18.75, "status": "suspended"},
]


def with_timestamp(supplier: dict) -> dict:
    return {**supplier, "updated_at": datetime.now(timezone.utc).isoformat()}
