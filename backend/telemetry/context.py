"""Normalization helpers called at emission time (TELEMETRY_PLAN §1.3, Appendix A/B).

These bridge the persisted domain values (LA/ZGZ warehouses, client_name) to the
canonical event vocabulary agreed with operations (los_angeles/zaragoza, client_id).
"""
from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache

# CONTEXT_6 §2 normalized warehouse values; maps the DB codes LA/ZGZ.
WAREHOUSE_MAP: dict[str, str] = {
    "LA": "los_angeles",
    "ZGZ": "zaragoza",
}

# TELEMETRY_PLAN Appendix A: stable client_id slugs for known clients.
CLIENT_NAME_SLUGS: dict[str, str] = {
    "PureStep Footwear": "purestep_footwear",
    "SoundWave Electronics": "soundwave_electronics",
    "GlowLab Cosmetics": "glowlab_cosmetics",
    "UrbanThread": "urban_thread",
}

# CONTEXT_6: derived country enrichment (US for LA, ES for ZGZ).
COUNTRY_BY_WAREHOUSE: dict[str, str] = {
    "los_angeles": "US",
    "zaragoza": "ES",
}

# Default low-stock threshold (units) matching the backoffice UI constant (20) but
# overridable via env for different clients/environments.
DEFAULT_LOW_STOCK_THRESHOLD: int = int(os.getenv("TELEMETRY_LOW_STOCK_THRESHOLD", "20"))


@lru_cache(maxsize=64)
def normalize_warehouse(warehouse: str | None) -> str | None:
    """Map a DB warehouse code (LA/ZGZ) to its canonical event value.

    Returns None for unknown codes so callers can skip emitting rather than
    produce an out-of-schema event.
    """
    if not warehouse:
        return None
    key = str(warehouse).strip().upper()
    return WAREHOUSE_MAP.get(key)


@lru_cache(maxsize=128)
def client_id_from_name(client_name: str | None) -> str | None:
    """Stable slug used as client_id (TELEMETRY_PLAN Appendix A).

    Known clients map to curated slugs; any other name is slugified deterministically
    so future clients stay consistent between events.
    """
    if not client_name:
        return None
    name = unicodedata.normalize("NFC", str(client_name).strip())
    if name in CLIENT_NAME_SLUGS:
        return CLIENT_NAME_SLUGS[name]
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or None


@lru_cache(maxsize=16)
def country_for_warehouse(normalized_warehouse: str | None) -> str | None:
    """Derived country for an already-normalized warehouse value."""
    if not normalized_warehouse:
        return None
    return COUNTRY_BY_WAREHOUSE.get(normalized_warehouse)