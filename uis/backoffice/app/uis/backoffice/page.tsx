import { Suspense } from "react";
import BackofficeHome from "../../../BackofficeHome";

export default function BackofficePage() {
  return <Suspense fallback={<p className="message loading">Loading TrackFlow operations…</p>}><BackofficeHome /></Suspense>;
}