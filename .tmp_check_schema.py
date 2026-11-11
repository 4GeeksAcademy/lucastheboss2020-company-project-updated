import json

with open("event-schemas.json") as f:
    doc = json.load(f)

events = doc["$defs"]["events"]

targets = [
    "auth_registration_created",
    "auth_registration_failed",
    "auth_password_reset_requested",
    "auth_password_reset_completed",
    "session_expired",
    "session_ended",
    "page_view",
    "frontend_page_load",
    "frontend_error_uncaught",
    "flow_abandoned",
    "inbound_order_created",
    "outbound_order_created",
    "outbound_order_rejected",
    "inventory_order_validation_error",
    "inventory_products_viewed",
    "auth_login_failed",
    "auth_login_succeeded",
]
for name in targets:
    ev = events.get(name)
    if not ev:
        print(f"!! {name} NOT FOUND")
        continue
    props_block = ev["properties"]["properties"]
    props = list(props_block.get("properties", {}).keys())
    required = props_block.get("required", [])
    print(f"{name}:")
    print(f"  properties={props}")
    print(f"  required_props={required}")