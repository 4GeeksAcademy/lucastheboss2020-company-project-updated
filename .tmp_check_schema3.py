import json

with open("event-schemas.json") as f:
    doc = json.load(f)

defs = doc["$defs"]
events = defs["events"]

# Extract enum/pattern/type info per property for the events we emit.
def describe(node):
    """Resolve $ref chains and return a compact description."""
    seen = set()
    while isinstance(node, dict) and "$ref" in node:
        if node["$ref"] in seen:
            break
        seen.add(node["$ref"])
        ptr = node["$ref"].lstrip("#/").split("/")
        target = doc
        for p in ptr:
            target = target[p]
        node = target
    info = {}
    if isinstance(node, dict):
        if "enum" in node:
            info["enum"] = node["enum"]
        if "pattern" in node:
            info["pattern"] = node["pattern"]
        if "type" in node:
            info["type"] = node["type"]
        if "minimum" in node:
            info["minimum"] = node["minimum"]
    return info

targets = [
    "auth_registration_created",
    "auth_registration_failed",
    "auth_login_succeeded",
    "auth_login_failed",
    "auth_password_reset_requested",
    "auth_password_reset_completed",
    "session_expired",
    "session_ended",
    "page_view",
    "frontend_page_load",
    "frontend_error_uncaught",
    "flow_abandoned",
    "inventory_order_validation_error",
    "inbound_order_created",
    "outbound_order_created",
    "outbound_order_rejected",
    "inventory_products_viewed",
]
for name in targets:
    ev = events.get(name)
    if not ev:
        print(f"!! {name} NOT FOUND")
        continue
    props_block = ev["properties"]["properties"]
    props = props_block.get("properties", {})
    print(f"--- {name} ---")
    for pname, pspec in props.items():
        info = describe(pspec)
        print(f"  {pname}: {info}")