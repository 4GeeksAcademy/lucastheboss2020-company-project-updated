import { Suspense } from "react";
import InventoryOrderForm from "../../../../../../uis/backoffice/inventory/InventoryOrderForm";

export default function InboundOrderPage() {
  return <Suspense fallback={<p className="message loading">Loading receipt form…</p>}><InventoryOrderForm mode="inbound" /></Suspense>;
}