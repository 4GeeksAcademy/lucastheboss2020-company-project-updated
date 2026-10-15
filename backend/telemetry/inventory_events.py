"""Inventory telemetry helpers: build the CONTEXT property set and wrap the 5
mandatory events (CONTEXT_6 §5) plus the OPPORTUNITY outbound rejection event.

CONTEXT_6 §6: inventory events NEVER carry carrier / end-recipient data — no
tracking_number, no recipient address, no carrier name. The helpers below enforce
that contract by only accepting allowlisted properties.

Event vocabulary (TELEMETRY_PLAN §1.3):
    inbound_order_created, outbound_order_created, stock_threshold_triggered,
    direct_stock_edit_rejected, inventory_discrepancy_detected (MANDATORY)
    outbound_order_rejected (OPPORTUNITY, stream)
"""
from __future__ import annotations

from typing import Any

from .context import client_id_from_name, country_for_warehouse, normalize_warehouse
from .core import emit, emit_threshold


def inventory_context(
    *,
    warehouse: str | None,
    client_name: str | None = None,
    product: Any | None = None,
    product_id: int | None = None,
    product_category: str | None = None,
) -> dict[str, Any]:
    """Build the canonical CONTEXT property set for an inventory event.

    warehouse is normalized LA/ZGZ -> los_angeles/zaragoza; client_name becomes the
    stable client_id slug (falls back to ``product.client_name``). Returns an empty
    dict when the SKU is missing or the warehouse code is unknown (caller should
    then skip emitting, since we cannot satisfy the required properties without
    corrupting the schema).
    """
    normalized = normalize_warehouse(warehouse)
    if not normalized:
        return {}
    category = product_category or getattr(product, "category", None)
    pid = product_id if product_id is not None else getattr(product, "id", None)
    if pid is None or not category:
        return {}
    name = client_name or getattr(product, "client_name", None)
    client_id = client_id_from_name(name)
    if client_id is None:
        return {}
    context: dict[str, Any] = {
        "warehouse": normalized,
        "client_id": client_id,
        "product_id": int(pid),
        "product_category": str(category),
    }
    country = country_for_warehouse(normalized)
    if country:
        context["country"] = country
    return context


def emit_inbound_order_created(
    *,
    context: dict[str, Any],
    quantity: int,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    **extra: Any,
) -> dict[str, Any] | None:
    """MANDATORY: successfully recorded inbound (stock-in) order."""
    if not context:
        return None
    return emit(
        "inbound_order_created",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties={**context, "quantity": quantity, **extra},
    )


def emit_outbound_order_created(
    *,
    context: dict[str, Any],
    quantity: int,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    **extra: Any,
) -> dict[str, Any] | None:
    """MANDATORY: successfully recorded outbound (stock-out) order.

    NB: never passes tracking_number — outbound_order_created is bound by the
    envelope allowlist which has no tracking property (CONTEXT_6 §6).
    """
    if not context:
        return None
    return emit(
        "outbound_order_created",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties={**context, "quantity": quantity, **extra},
    )


def emit_stock_threshold_triggered(
    *,
    context: dict[str, Any],
    stock_level: int,
    threshold_value: int,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    """MANDATORY: stock drops below the configured threshold.

    Deduped once per product+warehouse per UTC day (CONTEXT_6 §2) so an operator
    gets one signal, not one per outbound.
    """
    if not context:
        return None
    dedupe_key = f"{context.get('product_id')}:{context.get('warehouse')}"
    return emit_threshold(
        "stock_threshold_triggered",
        dedupe_key=dedupe_key,
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties={
            **context,
            "quantity": int(stock_level),
            "threshold_value": int(threshold_value),
        },
    )


def emit_direct_stock_edit_rejected(
    *,
    context: dict[str, Any],
    attempted_quantity: int,
    target_field: str,
    reason: str,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    """MANDATORY: an attempt to write stock directly was denied (no such endpoint;
    surfaces when a forbidden direct-write attempt is detected/rejected)."""
    if not context:
        return None
    return emit(
        "direct_stock_edit_rejected",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties={
            **context,
            "quantity": int(attempted_quantity),
            "target_field": target_field,
            "reason": reason,
        },
    )


def emit_inventory_discrepancy_detected(
    *,
    context: dict[str, Any],
    system_stock: int,
    physical_stock: int,
    audit_reference: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any] | None:
    """MANDATORY: stock audit found system != physical (batch context)."""
    if not context:
        return None
    variance = int(physical_stock) - int(system_stock)
    properties: dict[str, Any] = {
        **context,
        "quantity": int(system_stock),
        "physical_stock": int(physical_stock),
        "variance": variance,
    }
    if audit_reference:
        properties["audit_reference"] = str(audit_reference)
    if system_stock:
        properties["variance_ratio"] = round(abs(variance) / float(system_stock), 4)
    return emit(
        "inventory_discrepancy_detected",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties=properties,
    )


def emit_outbound_order_rejected(
    *,
    context: dict[str, Any],
    quantity: int,
    available_stock: int,
    reason: str,
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    exit_type: str | None = None,
) -> dict[str, Any] | None:
    """OPPORTUNITY (stream): an outbound order was rejected (insufficient stock,
    warehouse mismatch, sku not found, etc.) with the reason and baseline stock."""
    if not context and reason in {"sku_not_found", "warehouse_mismatch"}:
        # SKU not found / warehouse mismatch: we still emit with the (partial)
        # context we could build; inventory_context already produced {} if even
        # client_id was unavailable, in which case we cannot emit a valid event.
        pass
    if not context:
        return None
    properties: dict[str, Any] = {
        **context,
        "quantity": int(quantity),
        "available_stock": int(available_stock),
        "reason": reason,
    }
    if exit_type:
        properties["exit_type"] = exit_type
    return emit(
        "outbound_order_rejected",
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        properties=properties,
    )