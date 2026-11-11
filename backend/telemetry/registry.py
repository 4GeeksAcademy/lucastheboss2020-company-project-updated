"""Registry + dependency-free validation. Single source of truth is
event-schemas.json at the repo root (TELEMETRY_PLAN §2.8); this module loads and
compiles it once into per-event validation specs, then provides ``validate_event``.

The validation is intentionally defensive: it enforces the envelope fields, the
known-event set, and the property allowlist (additionalProperties=False) so that an
invalid — or potentially PII-leaking — event is rejected at emission time, before it
ever reaches a sink. No third-party jsonschema dependency is required.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("trackflow.telemetry.registry")

# Repo root contains event-schemas.json; registry.py lives in backend/telemetry/.
_DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "event-schemas.json"
_SCHEMA_PATH_ENV = "TELEMETRY_SCHEMA_PATH"

# Envelope fields every event must carry (TELEMETRY_PLAN §2 Event Envelope).
REQUIRED_ENVELOPE_FIELDS = ("eventId", "timestamp", "sessionId", "userId", "event_type", "schemaVersion", "requestId")

_ENVELOPE_FIELD_TYPES = {
    "eventId": str,
    "timestamp": str,
    "sessionId": str,
    "userId": str,
    "event_type": str,
    "schemaVersion": int,
    "requestId": str,
}


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    """Load + compile event-schemas.json into {event_type: spec}."""
    path = Path(__import__("os").getenv(_SCHEMA_PATH_ENV, "") or _DEFAULT_SCHEMA_PATH)
    if not path.exists():
        raise FileNotFoundError(f"event-schemas.json not found at {path}. Set {_SCHEMA_PATH_ENV} if relocated.")
    with path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    defs = document.get("$defs", {})
    value_defs = defs.get("valueTypes", {})
    enum_defs = defs.get("enums", {})
    base_defs = defs.get("base", {})
    events = defs.get("events", {})
    if not events:
        raise ValueError("event-schemas.json is missing $defs.events")

    def resolve(node: dict[str, Any]) -> dict[str, Any]:
        """Resolve $ref chains within the local document (draft-07 subset)."""
        ref = node.get("$ref")
        if not ref:
            return node
        pointer = ref.lstrip("#/").split("/")
        target: Any = document
        for part in pointer:
            target = target[part]
        return resolve(target) if isinstance(target, dict) and "$ref" in target else target

    def prop_schema(name: str, spec: dict[str, Any]) -> dict[str, Any]:
        """Resolve a property definition from base/valueTypes/enums where needed."""
        node = spec
        if "$ref" in node:
            node = resolve(node)
            if node.get("$ref"):  # double hop like base -> valueTypes
                node = resolve(node)
        return node

    compiled: dict[str, Any] = {}
    for event_type, schema in events.items():
        event_props_block = schema.get("properties", {}).get("properties", {})
        props_schema = event_props_block.get("properties", {})
        required = list(event_props_block.get("required", []))
        allowlist: dict[str, dict[str, Any]] = {}
        for name, raw in props_schema.items():
            allowlist[name] = prop_schema(name, raw)
        compiled[event_type] = {
            "required": required,
            "properties": allowlist,
            "envelope_required": list(schema.get("required", [])),
        }
    return {
        "document": document,
        "events": compiled,
        "value_types": value_defs,
        "enums": enum_defs,
        "base": base_defs,
    }


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _matches_type(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_matches_type(value, item) for item in expected)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def validate_event(event: dict[str, Any]) -> list[str]:
    """Structural validation of a full event envelope against the registry.

    Returns a list of human-readable problems; an empty list means the event is
    valid (matching event-schemas.json for the given event_type).
    """
    errors: list[str] = []
    if not isinstance(event, dict):
        return ["event is not an object"]

    for field in REQUIRED_ENVELOPE_FIELDS:
        if field not in event:
            errors.append(f"envelope missing '{field}'")
        elif event[field] is None:
            errors.append(f"envelope field '{field}' is null")

    event_type = event.get("event_type")
    if not isinstance(event_type, str) or event_type not in KNOWN_EVENTS:
        errors.append(f"unknown event_type {event_type!r}")
        return errors  # cannot validate properties of an unknown event

    expected_type = _ENVELOPE_FIELD_TYPES.get("event_type")
    for field, ftype in _ENVELOPE_FIELD_TYPES.items():
        if field in event and event[field] is not None and not isinstance(event[field], ftype):
            errors.append(f"envelope field '{field}' must be {ftype.__name__}")

    spec = _registry()["events"][event_type]
    props = event.get("properties")
    if props is None:
        errors.append("missing 'properties'")
        return errors
    if not isinstance(props, dict):
        errors.append("'properties' must be an object")
        return errors

    allowed = spec["properties"]
    for key in props:
        if key not in allowed:
            errors.append(f"property '{key}' is not in the allowlist for {event_type}")

    for required in spec["required"]:
        if required not in props:
            errors.append(f"{event_type} missing required property '{required}'")
        elif props[required] is None:
            errors.append(f"{event_type} property '{required}' is null")

    for key, prop in allowed.items():
        if key not in props or props[key] is None:
            continue
        value = props[key]
        prop_type = prop.get("type")
        if prop_type and not _matches_type(value, prop_type):
            errors.append(f"property '{key}' must be of type {prop_type!r}")
            continue
        enum_values = prop.get("enum")
        if enum_values and value not in enum_values:
            errors.append(f"property '{key}' value {value!r} is not one of {enum_values!r}")
        minimum = prop.get("minimum")
        if isinstance(value, (int, float)) and isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"property '{key}' {value!r} is below minimum {minimum!r}")
        pattern = prop.get("pattern")
        if pattern and isinstance(value, str):
            import re

            if not re.match(pattern, value):
                errors.append(f"property '{key}' value {value!r} does not match pattern {pattern!r}")
    return errors


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    return load_registry()


@lru_cache(maxsize=1)
def _known_events() -> frozenset[str]:
    return frozenset(load_registry()["events"].keys())


KNOWN_EVENTS = _known_events()


@lru_cache(maxsize=256)
def get_properties_allowlist(event_type: str) -> frozenset[str]:
    """Allowlisted property names for an event type (frozen set, empty if unknown)."""
    events = load_registry()["events"]
    spec = events.get(event_type)
    if not spec:
        return frozenset()
    return frozenset(spec["properties"].keys())