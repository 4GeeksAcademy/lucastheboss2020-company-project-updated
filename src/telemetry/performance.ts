/**
 * Frontend performance & web vitals capture for TrackFlow telemetry.
 *
 * Captures:
 *   - frontend_page_load (LCP, INP, TTFB, CLS)
 *   - frontend_error_uncaught (via global error handlers)
 *   - api_error (when fetch returns 5xx)
 *
 * All events are sent through the shared TelemetryService `track()` function.
 */

import { track } from "./TelemetryService";

// ── Web Vitals (frontend_page_load) ────────────────────────
// We capture metrics once, shortly after page load, using
// performance.timing (deprecated but universally available)
// and/or the newer PerformanceObserver API.

let _pageVitalsCaptured = false;

/** Read a single-time performance metric from performance.timing (ms since epoch). */
function timingOrNull(key: string): number | null {
  try {
    const t = performance.timing as unknown as Record<string, number>;
    const val = t[key];
    if (typeof val === "number" && val > 0) return val;
  } catch { /* browser may not expose timing */ }
  return null;
}

/** Compute a duration from performance.timing milestones. */
function durationMs(startKey: string, endKey: string): number | null {
  const start = timingOrNull(startKey);
  const end = timingOrNull(endKey);
  if (start && end && end >= start) return end - start;
  return null;
}

/** Attempt to read PerformanceObserver-based metrics (LCP, INP, CLS). */
function registerPerformanceObserver(route: string): void {
  try {
    if (typeof PerformanceObserver === "undefined") return;

    // We only need one shot — read LCP and CLS once they're available.
    const observer = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      for (const entry of entries) {
        if (entry.type === "largest-contentful-paint" && "latency" in entry) {
          track("frontend_page_load", {
            route,
            metric: "LCP",
            value_ms: Math.round(entry.value as number),
          });
        }
        if (entry.type === "cumulative-layout-shift" && "score" in entry) {
          track("frontend_page_load", {
            route,
            metric: "CLS",
            value_ms: Math.round(entry.score as number),
          });
        }
      }
    });

    observer.observe({ type: "largest-contentful-paint", buffered: true });
    observer.observe({ type: "cumulative-layout-shift", buffered: true });
  } catch { /* PerformanceObserver not available */ }
}

/**
 * Capture page load vitals using the best available method.
 * Call this once per page view, early in the page lifecycle.
 */
export function capturePageVitals(route: string): void {
  if (_pageVitalsCaptured) return;
  _pageVitalsCaptured = true;

  // Use PerformanceObserver for LCP/CLS (Chrome 84+)
  registerPerformanceObserver(route);

  // Fallback: use performance.timing for TTFB and page load time
  const ttfb = durationMs("requestStart", "responseStart");
  if (ttfb !== null) {
    track("frontend_page_load", { route, metric: "TTFB", value_ms: ttfb });
  }

  // FID (First Input Delay) can only be captured via PerformanceObserver
  // (a 'first-input' entry). We attempt it best-effort; if unavailable we
  // skip it rather than fabricating a metric name the schema rejects.
  try {
    if (typeof PerformanceObserver !== "undefined") {
      const fidObserver = new PerformanceObserver((list: PerformanceObserverEntryList) => {
        for (const entry of list.getEntries()) {
          if (entry.name === "first-input" && "processingStart" in entry) {
            const delay = (entry as PerformanceEventTiming).processingStart - entry.startTime;
            track("frontend_page_load", { route, metric: "FID", value_ms: Math.round(delay) });
            break;
          }
        }
      });
      fidObserver.observe({ type: "first-input", buffered: true });
    }
  } catch { /* FID not available — skip */ }

  // Device type detection
  let device = "desktop";
  try {
    const width = window.innerWidth;
    if (width < 768) device = "mobile";
    else if (width < 1024) device = "tablet";
  } catch { /* ignore */ }
}

// ── Global Error & Rejected Promise Handlers ───────────────
// These capture frontend_error_uncaught events.

/** Compute a stable message hash from an error string. */
function simpleHash(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    const char = input.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & 0xffffffff; // keep 32-bit
  }
  return Math.abs(hash).toString(16);
}

/** Install global error handlers. Safe to call multiple times (idempotent). */
let _errorHandlersInstalled = false;

export function installGlobalErrorHandlers(): void {
  if (_errorHandlersInstalled || typeof window === "undefined") return;
  _errorHandlersInstalled = true;

  window.addEventListener("error", (event: Event) => {
    const errEvent = event as ErrorEvent;
    const route = window.location.pathname;
    const message = errEvent.error?.message ?? errEvent.message ?? "unknown";
    track("frontend_error_uncaught", {
      route,
      error_type: "js_error",
      message_hash: simpleHash(message),
    });
  });

  window.addEventListener("uncaughtRejectedPromise", (event: PromiseRejectEvent) => {
    const route = window.location.pathname;
    const message = event.reason?.message ?? "unhandled_promise_rejection";
    track("frontend_error_uncaught", {
      route,
      error_type: "rejected_promise",
      message_hash: simpleHash(message),
    });
  });
}

// ── Navigation tracking (page_view) ────────────────────────

// Map a route to a valid `page_view.section` enum value
// (event-schemas.json: inventory|candidates|suppliers|incidents|profile|dashboard|website).
function sectionForRoute(route: string): string {
  if (route.startsWith("/uis/backoffice/inventory") || route.startsWith("/inventory")) return "inventory";
  if (route.startsWith("/candidates")) return "candidates";
  if (route.startsWith("/uis/backoffice/suppliers") || route.startsWith("/suppliers")) return "suppliers";
  if (route.includes("incident")) return "incidents";
  if (route.startsWith("/account")) return "profile";
  if (route.startsWith("/uis/website")) return "website";
  // login/register/forgot/reset + root + unknown → dashboard bucket
  return "dashboard";
}

/**
 * Capture a page_view event for the current route.
 * Call this once per page render.
 */
export function capturePageView(route: string, referrer?: string): void {
  track("page_view", {
    route,
    section: sectionForRoute(route),
    referrer_section: referrer ? sectionForRoute(referrer) : "direct",
  });
}

// ── Flow abandonment tracking ──────────────────────────────

/**
 * Simple tracker for multi-step flows (e.g., inventory order form).
 *
 * Usage:
 *   const flowTracker = new FlowTracker("inbound_order", "/uis/backoffice/inventory/orders/inbound");
 *   flowTracker.recordStep("form_loaded");
 *   // ... on successful submit:
 *   flowTracker.complete();
 *   // ... if user navigates away:
 *   // FlowTracker automatically captures flow_abandoned in a beforeunload handler.
 */
export class FlowTracker {
  private flow: string;
  private route: string;
  private startTime: number;
  private currentStep: string;
  private completed = false;
  private cleanup: (() => void) | null = null;

  constructor(flow: string, route: string) {
    this.flow = flow;
    this.route = route;
    this.startTime = performance.now();
    this.currentStep = "start";

    if (typeof window !== "undefined") {
      const handler = () => this._onAbandon();
      window.addEventListener("beforeunload", handler);
      this.cleanup = () => window.removeEventListener("beforeunload", handler);
    }
  }

  recordStep(step: string): void {
    this.currentStep = step;
  }

  complete(): void {
    this.completed = true;
    this.cleanup?.();
    this.cleanup = null;
  }

  private _onAbandon(): void {
    if (this.completed) return;
    track("flow_abandoned", {
      flow: this.flow,
      route: this.route,
      last_step: this.currentStep,
      time_in_flow_ms: Math.round(performance.now() - this.startTime),
    });
  }
}