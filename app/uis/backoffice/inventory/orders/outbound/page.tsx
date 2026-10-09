import { Suspense } from "react";
import InventoryOrderForm from "../../../../../../uis/backoffice/inventory/InventoryOrderForm";

export default function OutboundOrderPage() {
  return <Suspense fallback={<p className="message loading">Loading stock exit form…</p>}><InventoryOrderForm mode="outbound" /></Suspense>;
}