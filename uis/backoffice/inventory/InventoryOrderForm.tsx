"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  createInboundOrder,
  createOutboundOrder,
  fetchInventoryProduct,
  fetchInventoryProducts,
} from "../../../src/inventory/api";
import type { InventoryExitType, InventoryProduct } from "../../../src/inventory/types";
import { userSafeErrorMessage } from "../../../src/utils/api-errors";

type OrderMode = "inbound" | "outbound";

interface InventoryOrderFormProps {
  mode: OrderMode;
}

function warehouseName(code: InventoryProduct["warehouse"]): string {
  return code === "LA" ? "Los Angeles" : "Zaragoza";
}

export default function InventoryOrderForm({ mode }: InventoryOrderFormProps) {
  const searchParams = useSearchParams();
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [productsLoading, setProductsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(searchParams.get("product") ?? "");
  const [quantity, setQuantity] = useState("");
  const [reference, setReference] = useState("");
  const [exitType, setExitType] = useState<InventoryExitType>("dispatch");
  const [trackingNumber, setTrackingNumber] = useState("");
  const [currentStock, setCurrentStock] = useState<number | null>(null);
  const [stockLoading, setStockLoading] = useState(false);
  const [loadingError, setLoadingError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    let ignore = false;
    setProductsLoading(true);
    setLoadingError("");
    fetchInventoryProducts()
      .then((result) => { if (!ignore) setProducts(result); })
      .catch((error: unknown) => {
        if (!ignore) setLoadingError(userSafeErrorMessage(error, "Products could not be loaded. Please retry."));
      })
      .finally(() => { if (!ignore) setProductsLoading(false); });
    return () => { ignore = true; };
  }, [retryVersion]);

  useEffect(() => {
    const productParam = searchParams.get("product");
    if (productParam && products.some((product) => String(product.id) === productParam)) {
      setSelectedId(productParam);
    }
  }, [products, searchParams]);

  useEffect(() => {
    if (mode !== "outbound" || !selectedId) {
      setCurrentStock(null);
      setStockLoading(false);
      return;
    }

    let ignore = false;
    setStockLoading(true);
    setCurrentStock(null);
    setSubmitError("");
    fetchInventoryProduct(Number(selectedId))
      .then((product) => { if (!ignore) setCurrentStock(product.current_stock); })
      .catch((error: unknown) => {
        if (!ignore) setSubmitError(userSafeErrorMessage(error, "Available stock could not be checked. Please retry."));
      })
      .finally(() => { if (!ignore) setStockLoading(false); });
    return () => { ignore = true; };
  }, [mode, selectedId]);

  const selectedProduct = products.find((product) => String(product.id) === selectedId);
  const parsedQuantity = Number(quantity);
  const exceedsStock = mode === "outbound" && currentStock !== null && parsedQuantity > currentStock;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError("");
    setSuccess("");

    if (!selectedProduct) {
      setSubmitError("Select a product before submitting.");
      return;
    }
    if (!Number.isInteger(parsedQuantity) || parsedQuantity < 1) {
      setSubmitError("Enter a whole-number quantity greater than zero.");
      return;
    }
    if (mode === "outbound" && currentStock === null) {
      setSubmitError("Wait for the available stock check to finish before submitting.");
      return;
    }
    if (mode === "inbound" && !reference.trim()) {
      setSubmitError("Enter the receipt reference.");
      return;
    }
    if (mode === "outbound" && exitType === "dispatch" && !trackingNumber.trim()) {
      setSubmitError("Enter a carrier tracking number for a dispatch.");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "inbound") {
        await createInboundOrder({
          sku_id: selectedProduct.id,
          quantity: parsedQuantity,
          reference: reference.trim(),
          warehouse: selectedProduct.warehouse,
        });
        setSuccess("Receipt recorded. Inventory has been updated.");
      } else {
        await createOutboundOrder({
          sku_id: selectedProduct.id,
          quantity: parsedQuantity,
          exit_type: exitType,
          tracking_number: exitType === "dispatch" ? trackingNumber.trim() : null,
          warehouse: selectedProduct.warehouse,
        });
        setSuccess("Stock exit recorded.");
      }
      setSelectedId("");
      setQuantity("");
      setReference("");
      setTrackingNumber("");
      setCurrentStock(null);
    } catch (error) {
      setSubmitError(userSafeErrorMessage(error, "The order could not be saved. Please retry."));
    } finally {
      setSubmitting(false);
    }
  }

  const isInbound = mode === "inbound";
  const title = isInbound ? "Record a receipt" : "Record a stock exit";

  return (
    <section className="inventory-page inventory-form-page">
      <header className="page-header inventory-page__header">
        <span className="badge green">Warehouse operations</span>
        <h1>{title}</h1>
        <p>{isInbound ? "Log goods received from a client brand." : "Log a customer dispatch or a confirmed stock loss."}</p>
        <div className="actions">
          <Link className="button secondary" href="/uis/backoffice/inventory/products">Back to products</Link>
          <Link className="button secondary" href="/uis/backoffice/inventory/orders">Order history</Link>
        </div>
      </header>

      {loadingError && (
        <div className="message error" role="alert">
          <p>{loadingError}</p>
          <button className="secondary" type="button" onClick={() => setRetryVersion((version) => version + 1)}>Retry</button>
        </div>
      )}
      {!productsLoading && !loadingError && products.length === 0 && (
        <p className="message">No products are available. Register inventory before recording a movement.</p>
      )}

      <form className="inventory-form panel" onSubmit={handleSubmit}>
        <label className="field" htmlFor="inventory-product">
          <span>Product</span>
          <select
            id="inventory-product"
            required
            value={selectedId}
            onChange={(event) => { setSelectedId(event.target.value); setSuccess(""); setSubmitError(""); }}
            disabled={productsLoading || products.length === 0}
          >
            <option value="">{productsLoading ? "Loading products…" : "Select a product"}</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.name} · {product.sku} · {product.warehouse}
              </option>
            ))}
          </select>
        </label>

        {selectedProduct && (
          <div className="inventory-selected-product" aria-live="polite">
            <span>{selectedProduct.client_name}</span>
            <strong>{warehouseName(selectedProduct.warehouse)} ({selectedProduct.warehouse})</strong>
            {!isInbound && (
              <span>
                {stockLoading ? "Checking current stock…" : currentStock === null ? "Stock unavailable" : `Available now: ${currentStock} units`}
              </span>
            )}
          </div>
        )}

        <label className="field" htmlFor="inventory-quantity">
          <span>Quantity</span>
          <input
            id="inventory-quantity"
            type="number"
            inputMode="numeric"
            min="1"
            step="1"
            required
            value={quantity}
            disabled={mode === "outbound" && (!selectedProduct || stockLoading || currentStock === null)}
            onChange={(event) => { setQuantity(event.target.value); setSubmitError(""); setSuccess(""); }}
            aria-describedby={[
              exceedsStock ? "inventory-stock-warning" : "",
              submitError ? "inventory-submit-error" : "",
            ].filter(Boolean).join(" ") || undefined}
          />
          {exceedsStock && (
            <span className="inventory-inline-warning" id="inventory-stock-warning" role="status">
              This exceeds the displayed stock of {currentStock} units. The API will check stock again when submitted.
            </span>
          )}
          {submitError && (
            <span className="inventory-field-error" id="inventory-submit-error" role="alert">{submitError}</span>
          )}
        </label>

        {isInbound ? (
          <label className="field" htmlFor="inventory-reference">
            <span>Receipt reference</span>
            <input
              id="inventory-reference"
              type="text"
              maxLength={120}
              required
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              placeholder="e.g. GR-LA-0234"
            />
          </label>
        ) : (
          <>
            <label className="field" htmlFor="inventory-exit-type">
              <span>Exit type</span>
              <select id="inventory-exit-type" value={exitType} onChange={(event) => { setExitType(event.target.value as InventoryExitType); setSubmitError(""); }}>
                <option value="dispatch">Customer dispatch</option>
                <option value="loss">Confirmed loss</option>
              </select>
            </label>
            {exitType === "dispatch" && (
              <label className="field" htmlFor="inventory-tracking-number">
                <span>Carrier tracking number</span>
                <input
                  id="inventory-tracking-number"
                  type="text"
                  maxLength={120}
                  required
                  value={trackingNumber}
                  onChange={(event) => setTrackingNumber(event.target.value)}
                  placeholder="e.g. 1Z999AA10123456784"
                />
              </label>
            )}
          </>
        )}

        {success && <p className="message success" role="status">{success}</p>}
        <div className="inventory-form__actions">
          <button type="submit" disabled={submitting || productsLoading || !selectedProduct || (isInbound ? !!loadingError : stockLoading || currentStock === null)}>
            {submitting ? "Saving…" : isInbound ? "Record receipt" : "Record stock exit"}
          </button>
          {submitting && <span role="status">Saving movement…</span>}
        </div>
      </form>
    </section>
  );
}