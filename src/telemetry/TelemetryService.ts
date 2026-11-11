/**
 * TrackFlow TelemetryService — single `track()` entry point for all frontend telemetry.
 *
 * - Accumulates events in a local queue.
 * - Flushes in batches every N seconds or when queue hits MAX_BATCH_SIZE.
 * - Uses navigator.sendBeacon for reliable flush on tab close.
 * - Never blocks the caller, never crashes the application.
 *
 * Design: phase2-telemetry-plan.md §2 (TelemetryService)
 * Schema: event-schemas.json (single source of truth)
 */

const STORAGE_SESSION_KEY = "tf_session_id";

const FLUSH_INTERVAL_MS = 10_000; // flush every 10s if queue non-empty
const MAX_BATCH_SIZE = 20;       // also flush immediately at this depth
const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 1_000;

/** Generate RFC 4122 v4 UUID. Falls back to a random hex string. */
function uuidv4(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers / test environments
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/** Get or create a stable session id for this browser session (sessionStorage). */
function resolveSessionId(): string {
  try {
    let sid = sessionStorage.getItem(STORAGE_SESSION_KEY);
    if (!sid) {
      sid = uuidv4();
      sessionStorage.setItem(STORAGE_SESSION_KEY, sid);
    }
    return sid;
  } catch {
    return "anonymous";
  }
}

/** Resolve the current user id from localStorage token, or "anonymous". */
function resolveUserId(): string {
  try {
    const token = localStorage.getItem("trackflow_token");
    // Token is a JWT — we don't decode it client-side.
    // Just signal that a user IS authenticated.
    return token ? "authenticated" : "anonymous";
  } catch {
    return "anonymous";
  }
}

/** Resolve the endpoint URL.
 *
 * Priority:
 *   1. process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT (Next.js build-time substitution)
 *   2. localStorage "tf_telemetry_endpoint" (runtime override for tests)
 *   3. null (telemetry disabled, silently discard)
 */
function resolveEndpoint(): string | null {
  // Next.js inlines process.env.NEXT_PUBLIC_* at build time into string literals.
  // We reference it via a helper so it's accessible as a string at runtime.
  try {
    // @ts-expect-error — process.env may not exist in all runtimes; we catch gracefully
    const envEndpoint = typeof process !== "undefined" && process.env && process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
    if (envEndpoint && typeof envEndpoint === "string" && envEndpoint.trim() !== "") {
      return envEndpoint.trim();
    }
  } catch { /* process.env not available */ }

  // Runtime override (set by platform integration / tests)
  try {
    const configured = localStorage.getItem("tf_telemetry_endpoint");
    if (configured) return configured;
  } catch { /* ignore */ }

  return null;
}

export interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string;
  event_type: string;
  schemaVersion: number;
  requestId: string;
  properties: Record<string, unknown>;
}

/**
 * TelemetryService — singleton.
 *
 * Usage:
 *   import { track } from "@/src/telemetry/TelemetryService";
 *   track("inbound_order_created", { warehouse: "los_angeles", client_id: "fashion-co", ... });
 */
class TelemetryServiceImpl {
  private queue: TelemetryEvent[] = [];
  private flushTimerId: ReturnType<typeof setInterval> | null = null;
  private _flushInProgress = false;
  private _sessionId: string;
  private _endpoint: string | null;

  constructor() {
    this._sessionId = resolveSessionId();
    this._endpoint = resolveEndpoint();

    // Start periodic flush
    if (typeof window !== "undefined") {
      this.flushTimerId = setInterval(() => this._maybeFlush(), FLUSH_INTERVAL_MS);

      // Reliable flush on tab close
      window.addEventListener("beforeunload", () => this._onBeforeUnload());
      window.addEventListener("unload", () => this._onBeforeUnload());
    }
  }

  /**
   * The ONE public entry point.
   *
   * @param event_type  Known event type (entity_action, e.g. "inbound_order_created")
   * @param properties  Allowlisted properties for this event type.
   *                    Envelope fields (eventId, timestamp, ...) are NOT passed —
   *                    they are filled by this function.
   */
  track(event_type: string, properties: Record<string, unknown> = {}): void {
    if (!this._endpoint) {
      // Telemetry not configured — silently discard in production,
      // log a warning in dev.
      if (typeof window !== "undefined" && window.location.hostname === "localhost") {
        console.warn("[TelemetryService] TELEMETRY_ENDPOINT not set — discarding event", event_type);
      }
      return;
    }

    const event: TelemetryEvent = {
      eventId: uuidv4(),
      timestamp: new Date().toISOString(),
      sessionId: this._sessionId,
      userId: resolveUserId(),
      event_type,
      schemaVersion: 1,
      requestId: uuidv4(),
      properties,
    };

    this.queue.push(event);

    if (this.queue.length >= MAX_BATCH_SIZE) {
      this._maybeFlush();
    }
  }

  /** Public for tests: force-flush the queue. */
  async flush(): Promise<void> {
    return this._flush();
  }

  /** Public for tests: inspect queue depth. */
  get queueLength(): number {
    return this.queue.length;
  }

  /** Public for tests: inspect the current queue content. */
  get queuedEvents(): TelemetryEvent[] {
    return [...this.queue];
  }

  /** Public for tests: check if a flush is in progress. */
  get flushInProgress(): boolean {
    return this._flushInProgress;
  }

  // ── private ──────────────────────────────────────────────

  private _maybeFlush(): void {
    if (this.queue.length === 0 || this._flushInProgress) return;
    this._flush();
  }

  private async _flush(): Promise<void> {
    if (this._flushInProgress) return;
    const batch = this.queue.splice(0, this.queue.length); // atomic swap
    if (batch.length === 0) return;

    this._flushInProgress = true;
    try {
      await this._sendWithRetry(batch, 0);
    } finally {
      this._flushInProgress = false;
    }
  }

  private async _sendWithRetry(batch: TelemetryEvent[], attempt: number): Promise<void> {
    try {
      const response = await fetch(this._endpoint!, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch }),
        // Keepalive helps the sendBeacon-like behaviour
        keepalive: 30_000,
      });

      if (!response.ok) {
        // Non-2xx from the stub is a validation failure — no retry, the data is bad.
        if (attempt > 0) {
          // Log only if we're not on the first attempt (stub rejects are expected during dev)
          console.warn(
            `[TelemetryService] Batch rejected (HTTP ${response.status}), discarding ${batch.length} events.`
          );
        }
        return;
      }
    } catch (error) {
      // Network failure — retry with exponential backoff
      if (attempt < MAX_RETRIES - 1) {
        const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
        await new Promise((resolve) => setTimeout(resolve, delay));
        return this._sendWithRetry(batch, attempt + 1);
      }
      // Give up — telemetry is non-critical
      console.warn(
        `[TelemetryService] Failed to send batch after ${MAX_RETRIES} attempts, discarding ${batch.length} events.`
      );
    }
  }

  private _onBeforeUnload(): void {
    const batch = this.queue.splice(0, this.queue.length);
    if (batch.length === 0) return;

    const endpoint = this._endpoint;
    if (!endpoint) return;

    try {
      const blob = new Blob([JSON.stringify({ events: batch })], { type: "application/json" });
      navigator.sendBeacon(endpoint, blob);
    } catch {
      // sendBeacon can fail in some sandboxed environments — discard silently.
    }
  }
}

/** Singleton instance. */
let _instance: TelemetryServiceImpl | null = null;

function getInstance(): TelemetryServiceImpl {
  if (!_instance) {
    _instance = new TelemetryServiceImpl();
  }
  return _instance;
}

/**
 * The sole public entry point for all frontend telemetry.
 *
 * Usage:
 *   import { track } from "@/src/telemetry/TelemetryService";
 *   track("inbound_order_created", { warehouse: "los_angeles", ... });
 *
 * @param event_type  Event type from event-schemas.json (e.g. "inbound_order_created")
 * @param properties  Allowlisted properties for that event type.
 *                    Envelope fields are filled automatically.
 */
export function track(event_type: string, properties: Record<string, unknown> = {}): void {
  getInstance().track(event_type, properties);
}

/**
 * Force-flush the queue (useful in tests and during critical moments).
 */
export async function flushTelemetry(): Promise<void> {
  return getInstance().flush();
}

/**
 * Reset the service state (useful for tests).
 */
export function resetTelemetryService(): void {
  if (_instance) {
    if (_instance["flushTimerId"]) {
      clearInterval(_instance["flushTimerId"]);
    }
  }
  _instance = null;
}