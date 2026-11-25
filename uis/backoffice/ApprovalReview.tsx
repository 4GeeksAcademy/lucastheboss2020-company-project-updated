"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { ApprovalSection, RfpApprovalReview } from "../../src/types/rfp-intake";
import { fetchJson, parseJsonResponse, userSafeErrorMessage } from "../../src/utils/api-errors";
import { trackFlowAuthHeaders } from "../../src/utils/auth-headers";

const labels: Record<string, string> = {
  warehouse: "Warehouse Operations — Ana Whitfield",
  lastmile: "Last Mile and Carrier Management — Carlos Vega",
  reverse: "Reverse Logistics — Sofía Ramos",
  arbiter: "Commercial arbitration — Miguel Torres",
};
const readable = (value: string) => value.replace(/_/g, " ");
const base = (id: string) => `/api/backend/rfp/tickets/${encodeURIComponent(id)}/approvals`;

export function ApprovalInbox({ onSelect }: { onSelect: (id: string) => void }) {
  const [items, setItems] = useState<{ ticket_id: string; status: string }[]>([]);
  const [ticketId, setTicketId] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setItems(await fetchJson<{ ticket_id: string; status: string }[]>("/api/backend/rfp/approvals/inbox", {
        headers: trackFlowAuthHeaders(), cache: "no-store",
      }));
      setError("");
    } catch (e) {
      setError(userSafeErrorMessage(e, "Could not load assigned approvals."));
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  function open(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (ticketId.trim()) onSelect(ticketId.trim());
  }
  return <section className="panel" aria-label="Assigned department approvals">
    <h2>Your assigned approvals</h2>
    <p>Review a ticket assigned to your account. Department approval is independent of the person who uploaded the request.</p>
    <button type="button" className="secondary" onClick={() => void load()}>Refresh assignments</button>
    {error && <p role="alert" className="message error">{error}</p>}
    {items.length > 0 ? <ul>{items.map((item) => <li key={item.ticket_id}>
      <button type="button" className="secondary" onClick={() => onSelect(item.ticket_id)}>
        Review {item.ticket_id} · {readable(item.status)}
      </button>
    </li>)}</ul> : <p>No assigned approvals are listed.</p>}
    <form onSubmit={open}>
      <label className="field"><span>Open an assigned ticket by its ID</span>
        <input value={ticketId} onChange={(event) => setTicketId(event.target.value)} required maxLength={100} />
      </label>
      <button type="submit">Open approval review</button>
    </form>
  </section>;
}

function DepartmentDecision({ section, busy, submit }: {
  section: ApprovalSection;
  busy: boolean;
  submit: (department: string, body: Record<string, unknown>) => Promise<void>;
}) {
  const [feedback, setFeedback] = useState("");
  const [confirmation, setConfirmation] = useState(false);
  const changes = (decision: "reject" | "request_changes") =>
    void submit(section.department_id, { decision, version: section.version, feedback: feedback.trim() });
  return <article className="panel" aria-label={`${section.department_id} human approval`}>
    <h4>{labels[section.department_id] || section.owner}</h4>
    <p><strong>{readable(section.approval_status)}</strong> · Version {section.version}</p>
    {section.error && <p role="alert" className="message error">{section.error}</p>}
    <div style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{section.draft.content}</div>
    {!!section.draft.open_questions?.length && <><h5>Open questions</h5><ul>{section.draft.open_questions.map((question, i) => <li key={i}>{question}</li>)}</ul></>}
    {section.evaluation && <details><summary>Automated checks for this version</summary>
      <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(section.evaluation, null, 2)}</pre>
    </details>}
    {section.feedback && <p className="message">Previous feedback: {section.feedback}</p>}
    {section.can_decide ? <fieldset disabled={busy}>
      <legend>Your decision on version {section.version}</legend>
      <label className="field"><span>Feedback (required for rejection or changes)</span>
        <textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} maxLength={4000} rows={4} />
      </label>
      <label><input type="checkbox" checked={confirmation} onChange={(event) => setConfirmation(event.target.checked)} /> I have reviewed this version and authorize its inclusion in the client proposal.</label>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginTop: "0.75rem" }}>
        <button type="button" disabled={!confirmation || !section.can_approve} onClick={() => void submit(section.department_id, { decision: "approve", version: section.version, feedback: feedback.trim() })}>Approve this version</button>
        <button type="button" className="secondary" disabled={!feedback.trim()} onClick={() => changes("request_changes")}>Request changes</button>
        <button type="button" className="secondary" disabled={!feedback.trim()} onClick={() => changes("reject")}>Reject this version</button>
      </div>
      {!section.can_approve && <p className="message error">This version has unresolved checks or conflicts. Request changes before approving.</p>}
    </fieldset> : <p>Decisions are available to this department’s assigned reviewer while its approval is pending.</p>}
  </article>;
}

function ArbitrationDecision({ conflict, busy, submit }: {
  conflict: RfpApprovalReview["conflicts"][number];
  busy: boolean;
  submit: (body: Record<string, unknown>) => Promise<void>;
}) {
  const [feedback, setFeedback] = useState("");
  return <article className="panel">
    <h5>{readable(conflict.trigger_id)}</h5>
    <p><strong>{readable(conflict.status)}</strong> · Assigned arbiter: {conflict.arbiter_name || labels[conflict.arbiter] || conflict.arbiter}</p>
    <p>Departments: {conflict.department_ids.map((id) => labels[id] || id).join(", ")}</p>
    <p>{conflict.resolution}</p>
    {conflict.can_resolve && <fieldset disabled={busy}>
      <legend>Arbitration decision</legend>
      <label className="field"><span>Required resolution feedback</span>
        <textarea rows={3} maxLength={4000} value={feedback} onChange={(event) => setFeedback(event.target.value)} />
      </label>
      <button type="button" disabled={!feedback.trim()} onClick={() => void submit({ trigger_id: conflict.trigger_id, decision: "request_changes", feedback: feedback.trim() })}>Apply resolution and request changes</button>{" "}
      <button type="button" className="secondary" disabled={!feedback.trim()} onClick={() => void submit({ trigger_id: conflict.trigger_id, decision: "reject", feedback: feedback.trim() })}>Reject conflicting proposal</button>
    </fieldset>}
  </article>;
}

export default function ApprovalReview({ ticketId }: { ticketId: string }) {
  const [review, setReview] = useState<RfpApprovalReview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [department, setDepartment] = useState("warehouse");
  const [userId, setUserId] = useState("");
  const loadSequence = useRef(0);
  const saving = useRef(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    const sequence = ++loadSequence.current;
    const result = await fetchJson<RfpApprovalReview>(base(ticketId), { headers: trackFlowAuthHeaders(), cache: "no-store", signal });
    if (!signal?.aborted && sequence === loadSequence.current && result.ticket_id === ticketId) setReview(result);
  }, [ticketId]);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => {
      if (document.visibilityState !== "hidden" && !saving.current) void load(controller.signal).catch((e) => {
        if (!controller.signal.aborted) setError(userSafeErrorMessage(e, "Could not load approval review."));
      });
    };
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => { controller.abort(); ++loadSequence.current; clearInterval(interval); };
  }, [load]);
  async function command(path: string, body?: Record<string, unknown>) {
    saving.current = true;
    ++loadSequence.current;
    setBusy(true); setError("");
    try {
      await fetchJson<unknown>(base(ticketId) + path, {
        method: "POST", headers: { ...trackFlowAuthHeaders(), ...(body ? { "Content-Type": "application/json" } : {}) },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      await load();
    } catch (e) { setError(userSafeErrorMessage(e, "Could not save this approval action. Refresh before trying again.")); }
    finally { saving.current = false; setBusy(false); }
  }
  async function download() {
    setBusy(true); setError("");
    try {
      const response = await fetch(base(ticketId) + "/document", { headers: trackFlowAuthHeaders(), cache: "no-store" });
      if (!response.ok) await parseJsonResponse(response);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url; link.download = `trackflow-proposal-${ticketId}.md`;
      link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(userSafeErrorMessage(e, "Could not download the final proposal.")); }
    finally { setBusy(false); }
  }
  return <section className="panel" aria-label="Human approvals and final proposal">
    <h3>Human approvals and final proposal</h3>
    <p>Ticket {ticketId}</p>
    {error && <p role="alert" className="message error">{error}</p>}
    {!review && !error && <p role="status">Loading approvals…</p>}
    {review && <>
      <p role="status">Ticket status: <strong>{readable(review.status)}</strong></p>
      {(review.error || review.blocked) && <p role="alert" className="message error">{review.error || "This workflow needs review before it can continue. Saved decisions and drafts are retained."}</p>}
      <p>Each active department signs off separately. A pending department does not prevent another reviewer from deciding.</p>
      {review.sections.length > 0 && review.status !== "done" && <button type="button" className="secondary" disabled={busy} onClick={() => void command("/retry")}>Resume saved approval processing</button>}
      {review.can_assign && <details><summary>Assign department reviewers</summary>
        <p>Assign an existing active TrackFlow account to represent the named department owner. Use its account user ID.</p>
        <p>Existing reviewer assignments are locked once approvals have started.</p>
        {review.reviewers.length > 0 && <ul>{review.reviewers.map((person) => <li key={person.department_id}>{labels[person.department_id] || person.department_id}: {person.user_id}</li>)}</ul>}
        <form onSubmit={(event) => { event.preventDefault(); void command("/reviewers", { department_id: department, user_id: userId.trim() }); }}>
          <label className="field"><span>Department or arbiter</span><select value={department} onChange={(event) => setDepartment(event.target.value)}>{Object.entries(labels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
          <label className="field"><span>Existing account user ID</span><input value={userId} onChange={(event) => setUserId(event.target.value)} required maxLength={100} /></label>
          <button type="submit" disabled={busy || !userId.trim()}>Save reviewer assignment</button>
        </form>
      </details>}
      {review.can_start && <button type="button" disabled={busy} onClick={() => void command("")}>Start department approvals</button>}
      {review.sections.map((section) => <DepartmentDecision key={`${section.department_id}-${section.version}-${section.approval_status}`} section={section} busy={busy} submit={(id, body) => command(`/${encodeURIComponent(id)}/resume`, body)} />)}
      {review.conflicts.length > 0 && <section aria-label="Arbitration findings"><h4>Conflicts requiring resolution</h4>
        <p>Conflicting commitments must be resolved before the final proposal can be produced.</p>
        {review.conflicts.map((conflict) => <ArbitrationDecision key={`${conflict.trigger_id}-${conflict.status}`} conflict={conflict} busy={busy} submit={(body) => command("/arbitrate", body)} />)}
      </section>}
      {review.document && <section aria-label="Approved final document"><h4>Final proposal</h4>
        <p>{review.document.currency} · Generated {new Date(review.document.generated_at).toLocaleString()}</p>
        <button type="button" disabled={busy} onClick={() => void download()}>Download approved proposal</button>
        <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{review.document.content}</pre>
      </section>}
      {review.trace.length > 0 && <details><summary>Workflow history</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(review.trace, null, 2)}</pre></details>}
    </>}
  </section>;
}
