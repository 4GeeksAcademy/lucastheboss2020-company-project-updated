import { ApiRequestError, fetchJson } from "../utils/api-errors";
import { TRACKFLOW_TOKEN_KEY, trackFlowAuthHeaders } from "../utils/auth-headers";
import type { InboundOrderInput, InventoryOrder, InventoryProduct, OutboundOrderInput } from "./types";

const API_BASE_URL = "/api/backend";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  for (const [key, value] of Object.entries(trackFlowAuthHeaders())) headers.set(key, value);

  try {
    return await fetchJson<T>(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      cache: init.cache ?? "no-store",
    });
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem(TRACKFLOW_TOKEN_KEY);
      window.location.assign("/login");
    }
    throw error;
  }
}

export function fetchInventoryProducts(): Promise<InventoryProduct[]> {
  return request("/inventory/products");
}

export function fetchInventoryProduct(id: number): Promise<InventoryProduct> {
  return request(`/inventory/products/${encodeURIComponent(id)}`);
}

export function createInboundOrder(input: InboundOrderInput): Promise<InventoryOrder> {
  return request("/inventory/orders/inbound", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function createOutboundOrder(input: OutboundOrderInput): Promise<InventoryOrder> {
  return request("/inventory/orders/outbound", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function fetchInventoryOrders(): Promise<InventoryOrder[]> {
  return request("/inventory/orders");
}