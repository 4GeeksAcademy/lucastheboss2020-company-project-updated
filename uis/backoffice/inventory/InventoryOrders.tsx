"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchInventoryOrders } from "../../../src/inventory/api";
import type { InventoryOrder } from "../../../src/inventory/types";
import { userSafeErrorMessage } from "../../../src/utils/api-errors";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function InventoryOrders() {
  const [orders, setOrders] = useState<InventoryOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    fetchInventoryOrders()
      .then((result) => { if (!ignore) setOrders(result); })
      .catch((fetchError: unknown) => {
        if (!ignore) setError(userSafeErrorMessage(fetchError, "Order history could not be loaded. Please retry."));
      })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [retryVersion]);

  return (
    <section className="inventory-page">
      <header className="page-header inventory-page__header">
        <span className="badge green">Warehouse operations</span>
        <h1>Order history</h1>
        <p>Receipts and stock exits recorded across Los Angeles and Zaragoza.</p>
        <div className="actions">
          <Link className="button secondary" href="/uis/backoffice/inventory/products">Products</Link>
          <Link className="button" href="/uis/backoffice/inventory/orders/inbound">Record receipt</Link>
          <Link className="button secondary" href="/uis/backoffice/inventory/orders/outbound">Record stock exit</Link>
        </div>
      </header>

      {loading && <p className="message loading" role="status">Loading order history…</p>}
      {error && (
        <div className="message error" role="alert">
          <p>{error}</p>
          <button className="secondary" type="button" onClick={() => setRetryVersion((version) => version + 1)}>Retry</button>
        </div>
      )}
      {!loading && !error && orders.length === 0 && <p className="message">No inventory movements have been recorded.</p>}

      {!loading && orders.length > 0 && (
        <div className="inventory-table-wrap">
          <table className="inventory-table inventory-orders-table">
            <caption className="visually-hidden">Read-only inventory movement history</caption>
            <thead>
              <tr>
                <th scope="col">Movement</th>
                <th scope="col">Product</th>
                <th scope="col">Quantity</th>
                <th scope="col">Warehouse</th>
                <th scope="col">Created</th>
                <th scope="col">Created by (user UUID)</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => {
                const isInbound = order.movement_type === "inbound";
                const label = isInbound ? "Receipt" : order.exit_type === "loss" ? "Loss" : "Dispatch";
                return (
                  <tr key={`${order.movement_type}-${order.id}`}>
                    <td><span className={`inventory-movement ${isInbound ? "inventory-movement--inbound" : "inventory-movement--outbound"}`}>{isInbound ? "+" : "−"} {label}</span></td>
                    <th scope="row">
                      <span className="inventory-table__product-name">{order.sku.name}</span>
                      <span className="inventory-table__sku">{order.sku.sku}</span>
                      {order.reference && <span className="inventory-table__sku">Ref: {order.reference}</span>}
                      {order.tracking_number && <span className="inventory-table__sku">Tracking: {order.tracking_number}</span>}
                    </th>
                    <td className="inventory-order-quantity">{isInbound ? "+" : "−"}{order.quantity}</td>
                    <td>{order.warehouse === "LA" ? "Los Angeles (LA)" : "Zaragoza (ZGZ)"}</td>
                    <td>{formatDate(order.created_at)}</td>
                    <td className="inventory-user-uuid">{order.user_uuid}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}