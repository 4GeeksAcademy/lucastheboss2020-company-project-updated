import json

with open("event-schemas.json") as f:
    doc = json.load(f)

defs = doc["$defs"]
print("=== defs keys ===")
print(list(defs.keys()))
print()
print("=== valueTypes ===")
def walk(node, path=""):
    if isinstance(node, dict):
        if "enum" in node:
            print(f"{path}: enum={node['enum']} type={node.get('type')} default={node.get('default')}")
        for k, v in node.items():
            walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]")

walk(defs.get("valueTypes", {}), "valueTypes")
print()
print("=== events page_view/frontend_page_load/frontend_error_uncaught full ===")
for name in ["page_view", "frontend_page_load", "frontend_error_uncaught", "flow_abandoned"]:
    ev = defs["events"].get(name)
    print()
    print(name, "=>", json.dumps(ev, indent=1)[:1200])