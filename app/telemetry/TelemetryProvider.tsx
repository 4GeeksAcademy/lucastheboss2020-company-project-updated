"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import {
  capturePageView,
  capturePageVitals,
  installGlobalErrorHandlers,
} from "../../src/telemetry/performance";
import { flushTelemetry } from "../../src/telemetry/TelemetryService";

/**
 * Global frontend telemetry wiring.
 *
 * Mounts once in the root layout and:
 *   - installs global error + unhandled promise rejection handlers
 *   - captures page-load web vitals (frontend_page_load) on first paint
 *   - captures a page_view event on every route change (client-side nav included)
 *   - flushes any queued telemetry when the page unloads
 *
 * This component renders nothing; it only wires telemetry.
 */
export default function TelemetryProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const firstRouteRef = useRef<string | null>(null);

  // Install global error handlers + page vitals exactly once.
  useEffect(() => {
    installGlobalErrorHandlers();

    const route = window.location.pathname;
    firstRouteRef.current = route;
    capturePageVitals(route);
  }, []);

  // Capture a page_view on every route change (including the first render).
  useEffect(() => {
    if (firstRouteRef.current === null) {
      firstRouteRef.current = pathname;
      capturePageView(pathname, document.referrer);
      return;
    }
    if (firstRouteRef.current === pathname) {
      // First render already handled above (avoid double view on mount).
      return;
    }
    firstRouteRef.current = pathname;
    capturePageView(pathname);
  }, [pathname]);

  // Best-effort flush on tab close (the TelemetryService already uses
  // sendBeacon on beforeunload internally, this is a safety net).
  useEffect(() => {
    const handler = () => flushTelemetry();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  return <>{children}</>;
}