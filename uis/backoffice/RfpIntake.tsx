"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { trackFlowAuthHeaders } from "../../src/utils/auth-headers";
import { fetchJson, userSafeErrorMessage } from "../../src/utils/api-errors";
import type { RfpTicket } from "../../src/types/rfp-intake";
import ProposalReview from "./ProposalReview";
const API = "/api/backend/rfp/tickets";
const field = (value: string | null | undefined) =>
  value || "Not stated — needs clarification";
export default function RfpIntake() {
  const [tickets, setTickets] = useState<RfpTicket[]>([]),
    [selected, setSelected] = useState<RfpTicket | null>(null);
  const [selectedId, setSelectedId] = useState(""),
    [offset, setOffset] = useState(0),
    [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true),
    [uploading, setUploading] = useState(false),
    [retrying, setRetrying] = useState(false),
    [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(
    async (signal?: AbortSignal) => {
      const headers = trackFlowAuthHeaders();
      const [list, detail] = await Promise.all([
        fetchJson<{ items: RfpTicket[] }>(
          API + "?offset=" + offset + "&limit=30",
          { headers, cache: "no-store", signal },
        ),
        selectedId
          ? fetchJson<RfpTicket>(API + "/" + selectedId, {
              headers,
              cache: "no-store",
              signal,
            })
          : Promise.resolve(null),
      ]);
      if (!signal?.aborted) {
        setTickets(list.items);
        setSelected(detail);
        setLoading(false);
        setError("");
      }
    },
    [offset, selectedId],
  );
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => {
      if (document.visibilityState !== "hidden")
        void load(controller.signal).catch((e) => {
          if (!controller.signal.aborted) {
            setError(userSafeErrorMessage(e, "Could not load RFP tickets."));
            setLoading(false);
          }
        });
    };
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [load]);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    if (
      !file.name.toLowerCase().endsWith(".pdf") ||
      file.size > 10 * 1024 * 1024
    ) {
      setError("Choose a PDF no larger than 10 MB.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await fetchJson<RfpTicket>(API, {
        method: "POST",
        headers: trackFlowAuthHeaders(),
        body,
      });
      setSelectedId(result.ticket_id);
      setSelected(result);
      setOffset(0);
      setFile(null);
      if (input.current) input.current.value = "";
    } catch (e) {
      setError(
        userSafeErrorMessage(
          e,
          "Upload could not be completed. Check the ticket list before retrying.",
        ),
      );
    } finally {
      setUploading(false);
    }
  }
  async function retry() {
    if (!selected) return;
    setRetrying(true);
    try {
      const result = await fetchJson<RfpTicket>(
        API + "/" + selected.ticket_id + "/retry",
        { method: "POST", headers: trackFlowAuthHeaders() },
      );
      setSelected(result);
      setError("");
    } catch (e) {
      setError(userSafeErrorMessage(e, "Could not retry this ticket."));
    } finally {
      setRetrying(false);
    }
  }
  return (
    <section>
      <header className="page-header">
        <span className="badge green">TrackFlow commercial team</span>
        <h1>RFP intake</h1>
        <p>
          Upload a customer’s logistics request. TrackFlow will identify the
          services, involve the right departments, and prepare a summary for
          Sales.
        </p>
        <Link href="/uis/backoffice">Back to backoffice</Link>
      </header>
      <section className="panel" aria-label="Upload a logistics request">
        <h2>New request</h2>
        <form onSubmit={upload}>
          <label className="field" htmlFor="rfp-pdf">
            <span>Customer request PDF</span>
            <input
              ref={input}
              id="rfp-pdf"
              type="file"
              accept="application/pdf,.pdf"
              required
              disabled={uploading}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <p className="message">
            Text PDFs only · up to 10 MB and 80 pages. Processing continues
            after you leave this screen. One upload creates one ticket.
          </p>
          <button type="submit" disabled={!file || uploading}>
            {uploading ? "Saving upload…" : "Upload and analyze"}
          </button>
        </form>
      </section>
      {error && (
        <div className="message error" role="alert">
          {error}
          <button
            type="button"
            className="secondary"
            onClick={() =>
              void load().catch(() =>
                setError("The service is still unavailable."),
              )
            }
          >
            Refresh tickets
          </button>
        </div>
      )}
      <section className="panel" aria-label="RFP ticket list">
        <h2>Your requests</h2>
        {loading && <p role="status">Loading requests…</p>}
        {!loading && !tickets.length && (
          <p>No requests yet. Upload a PDF to get started.</p>
        )}
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              textAlign: "left",
              borderSpacing: "0 12px",
            }}
          >
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <tr key={t.ticket_id}>
                  <td>
                    <button
                      type="button"
                      className="secondary"
                      aria-pressed={selectedId === t.ticket_id}
                      onClick={() => {
                        setSelectedId(t.ticket_id);
                        setSelected(t);
                      }}
                    >
                      {t.metadata?.client_name || t.original_filename}
                    </button>
                  </td>
                  <td>
                    <span className="badge">{t.status.replace(/_/g, " ")}</span>
                  </td>
                  <td>
                    {t.processing_state === "failed"
                      ? "Needs attention"
                      : t.stage}
                  </td>
                  <td>{new Date(t.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="actions">
          <button
            className="secondary"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 30))}
          >
            Previous
          </button>
          <span>Page {offset / 30 + 1}</span>
          <button
            className="secondary"
            disabled={tickets.length < 30}
            onClick={() => setOffset(offset + 30)}
          >
            Next
          </button>
        </div>
      </section>
      {selected && (
        <section className="panel" aria-label="RFP ticket details">
          <h2>
            {selected.metadata?.client_name || selected.original_filename}
          </h2>
          <p>
            <strong>Ticket:</strong> {selected.ticket_id}
          </p>
          <p role="status">
            <strong>{selected.status.replace(/_/g, " ")}</strong> ·{" "}
            {selected.stage}
          </p>
          {(selected.error_message || selected.stalled) && (
            <div className="message error" role="alert">
              <p>
                {selected.error_message ||
                  "Processing has not reported progress recently. The worker may have stopped."}
              </p>
              {selected.can_retry && (
                <button disabled={retrying} onClick={() => void retry()}>
                  {retrying ? "Scheduling…" : "Retry saved request"}
                </button>
              )}
              {!selected.can_retry &&
                selected.processing_state === "failed" && (
                  <p>
                    Contact the TrackFlow team if the retry limit has been
                    reached.
                  </p>
                )}
            </div>
          )}
          {selected.classification_reason && (
            <p>
              <strong>Document assessment:</strong>{" "}
              {selected.classification_reason}
            </p>
          )}
          {selected.status === "discarded" && (
            <p>
              This document was not a client request for a TrackFlow proposal.
              No department analysis was performed.
            </p>
          )}
          {selected.metadata && (
            <>
              <h3>Customer request</h3>
              <dl>
                <dt>Country / proposal currency</dt>
                <dd>
                  {field(selected.metadata.client_country)} /{" "}
                  {field(selected.metadata.currency)}
                </dd>
                <dt>Monthly volume</dt>
                <dd>{field(selected.metadata.monthly_volume)}</dd>
                <dt>Deadline</dt>
                <dd>{field(selected.metadata.deadline)}</dd>
                <dt>Reference budget</dt>
                <dd>{field(selected.metadata.budget_range)}</dd>
              </dl>
              <details>
                <summary>Document complexity and source evidence</summary>
                <p>
                  Readability formulas estimate English text complexity. Token
                  counts are approximate, not a price quote. Short documents may
                  not support all formulas.
                </p>
                <pre
                  style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
                >
                  {JSON.stringify(
                    {
                      metrics: selected.metadata.readability_metrics,
                      evidence: selected.metadata.evidence,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </>
          )}
          {selected.handoff && (
            <>
              <h3>Sales summary</h3>
              <p style={{ whiteSpace: "pre-wrap" }}>
                {selected.handoff.summary}
              </p>
              {selected.handoff.conflicts.length > 0 && (
                <>
                  <h4>Needs clarification</h4>
                  <ul>
                    {selected.handoff.conflicts.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </>
              )}
              {selected.handoff.open_questions.length > 0 && (
                <>
                  <h4>Open questions</h4>
                  <ul>
                    {selected.handoff.open_questions.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </>
              )}
              <p className="message">
                Intake is complete. Proposal drafts can be prepared below.
                Department approval and the final proposal follow in Part 3;
                no pricing or capacity has been committed.
              </p>
            </>
          )}
          <ProposalReview key={selected.ticket_id} ticket={selected} onChange={setSelected} />
          {selected.sections.map((s) => (
            <article className="panel" key={s.department_id}>
              <h3>
                {s.department_id === "warehouse"
                  ? "Warehouse Operations"
                  : s.department_id === "lastmile"
                    ? "Last Mile and Carrier Management"
                    : "Reverse Logistics"}
              </h3>
              <p>
                <strong>Ask:</strong> {s.owner}
              </p>
              <ul>
                {s.key_aspects.map((a, i) => (
                  <li key={i}>
                    <p>{a.requirement}</p>
                    <details>
                      <summary>Source excerpt</summary>
                      <blockquote>{a.evidence}</blockquote>
                    </details>
                  </li>
                ))}
              </ul>
              {s.open_questions.length > 0 && (
                <>
                  <h4>Information needed</h4>
                  <ul>
                    {s.open_questions.map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </>
              )}
            </article>
          ))}
        </section>
      )}
    </section>
  );
}
