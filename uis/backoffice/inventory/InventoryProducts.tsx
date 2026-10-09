"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchInventoryProducts } from "../../../src/inventory/api";
import type { InventoryProduct } from "../../../src/inventory/types";
import { userSafeErrorMessage } from "../../../src/utils/api-errors";

// Keep this threshold visible so operations can tune it to TrackFlow's stock policy.
const LOW_STOCK_THRESHOLD = 20;

function stockState(quantity: number): { label: string; className: string } {
  if (quantity === 0) return { label: "Out of stock", className: "inventory-stock--empty" };
  if (quantity < LOW_STOCK_THRESHOLD) return { label: "Low stock", className: "inventory-stock--low" };
  return { label: "Healthy", className: "inventory-stock--healthy" };
}

function productLabel(product: InventoryProduct): string {
  return product.warehouse === "LA" ? "Los Angeles" : "Zaragoza";
}

export default function InventoryProducts() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    fetchInventoryProducts()
      .then((result) => { if (!ignore) setProducts(result); })
      .catch((fetchError: unknown) => {
        if (!ignore) setError(userSafeErrorMessage(fetchError, "Products could not be loaded. Please retry."));
      })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [retryVersion]);

  const totalUnits = products.reduce((sum, product) => sum + product.current_stock, 0);
  const lowCount = products.filter((product) => product.current_stock < LOW_STOCK_THRESHOLD).length;

  return (
    <section className="inventory-page">
      <header className="page-header inventory-page__header">
        <span className="badge green">Warehouse operations</span>
        <h1>Inventory</h1>
        <p>Live stock by SKU and warehouse. Stock levels are calculated from recorded receipts and exits.</p>
      </header>

      <div className="inventory-metrics" aria-label="Inventory summary">
        <div><span>Products</span><strong>{loading ? "—" : products.length}</strong></div>
        <div><span>Units on hand</span><strong>{loading ? "—" : totalUnits.toLocaleString()}</strong></div>
        <div><span>Needs attention</span><strong>{loading ? "—" : lowCount}</strong></div>
      </div>

      {loading && <p className="message loading" role="status">Loading live inventory…</p>}
      {error && (
        <div className="message error" role="alert">
          <p>{error}</p>
          <button type="button" className="secondary" onClick={() => setRetryVersion((version) => version + 1)}>Retry</button>
        </div>
      )}
      {!loading && !error && products.length === 0 && (
        <p className="message">No SKUs are registered yet.</p>
      )}

      {!loading && products.length > 0 && (
        <div className="inventory-table-wrap">
          <table className="inventory-table">
            <caption className="visually-hidden">TrackFlow SKU stock by warehouse</caption>
            <thead>
              <tr>
                <th scope="col">Product</th>
                <th scope="col">Client</th>
                <th scope="col">Category</th>
                <th scope="col">Warehouse</th>
                <th scope="col">Current stock</th>
                <th scope="col"><span className="visually-hidden">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => {
                const state = stockState(product.current_stock);
                const productQuery = `?product=${product.id}`;
                return (
                  <tr key={product.id}>
                    <th scope="row">
                      <span className="inventory-table__product-name">{product.name}</span>
                      <span className="inventory-table__sku">{product.sku}</span>
                    </th>
                    <td>{product.client_name}</td>
                    <td className="inventory-capitalize">{product.category}</td>
                    <td>{productLabel(product)} <span className="inventory-muted">({product.warehouse})</span></td>
                    <td>
                      <span className={`inventory-stock ${state.className}`}>
                        <strong>{product.current_stock}</strong>
                        <span>{state.label}</span>
                      </span>
                    </td>
                    <td>
                      <div className="inventory-row-actions">
                        <Link className="button secondary" href={`/uis/backoffice/inventory/orders/inbound${productQuery}`}>Receive</Link>
                        <Link className="button" href={`/uis/backoffice/inventory/orders/outbound${productQuery}`}>Dispatch / loss</Link>
                      </div>
                    </td>
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