"use client";
import { useState } from "react";
import type { RfpTicket, ProposalAttempt } from "../../src/types/rfp-intake";
import { fetchJson, userSafeErrorMessage } from "../../src/utils/api-errors";
import { trackFlowAuthHeaders } from "../../src/utils/auth-headers";

const labels: Record<string, string> = {
  warehouse: "Warehouse Operations",
  lastmile: "Last Mile and Carrier Management",
  reverse: "Reverse Logistics",
};
const phases: Record<string, string> = {
  drafting: "Writing draft",
  under_evaluation: "Checking draft",
  revising: "Revising with feedback",
  passed: "Automated checks passed",
  needs_human_review: "Needs human review",
};

function Evaluation({ attempt }: { attempt: ProposalAttempt }) {
  const e = attempt.evaluation;
  if (!e)
    return (
      <p role="status">
        Evaluation has not finished. This draft is retained if processing is
        interrupted.
      </p>
    );
  return (
    <section aria-label={`Evaluation of draft ${attempt.version}`}>
      <h4>
        Draft {attempt.version} evaluation —{" "}
        {e.overall_pass ? "Passed" : "Needs changes"}
      </h4>
      <ul>
        <li>
          <strong>Readability:</strong>{" "}
          {e.readability.pass ? "Passed" : "Needs changes"}.{" "}
          {e.readability.details}
          {e.readability.score !== null && (
            <>
              {" "}
              Score: {e.readability.score} (
              {e.readability.method === "sentence_length_fallback"
                ? "average sentence length"
                : "estimated grade level"}
              ).
            </>
          )}
        </li>
        <li>
          <strong>Relevance:</strong>{" "}
          {e.relevance.pass ? "Passed" : "Needs changes"}
        </li>
        <li>
          <strong>Company rules:</strong>{" "}
          {e.compliance.pass ? "Passed" : "Needs changes"}
        </li>
      </ul>
      {e.relevance.missing_aspects.concat(e.relevance.unsupported_claims)
        .length > 0 && (
        <ul>
          {e.relevance.missing_aspects
            .concat(e.relevance.unsupported_claims)
            .map((v, i) => (
              <li key={i}>{v}</li>
            ))}
        </ul>
      )}
      {e.compliance.violations.length > 0 && (
        <ul>
          {e.compliance.violations.map((v, i) => (
            <li key={i}>{v.violation}</li>
          ))}
        </ul>
      )}
      <details>
        <summary>Feedback given to the generator</summary>
        <p style={{ whiteSpace: "pre-wrap" }}>{e.feedback_for_generator}</p>
      </details>
    </section>
  );
}

export default function ProposalReview({
  ticket,
  onChange,
}: {
  ticket: RfpTicket;
  onChange: (ticket: RfpTicket) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const run = ticket.proposal;
  async function start(retry = false) {
    setBusy(true);
    setError("");
    try {
      onChange(
        await fetchJson<RfpTicket>(
          `/api/backend/rfp/tickets/${ticket.ticket_id}/proposal${retry ? "/retry" : ""}`,
          {
            method: "POST",
            headers: trackFlowAuthHeaders(),
          },
        ),
      );
    } catch (e) {
      setError(
        userSafeErrorMessage(e, "Could not schedule proposal generation."),
      );
    } finally {
      setBusy(false);
    }
  }
  if (!run && ticket.status !== "intake_complete") return null;
  return (
    <section className="panel" aria-label="Proposal drafts and evaluations">
      <h3>Proposal drafts</h3>
      <p>
        Each assigned department drafts its section. Readability, relevance and
        company rules are checked in parallel, with up to three draft attempts
        per department.
      </p>
      {!run && (
        <button disabled={busy} onClick={() => void start()}>
          {busy ? "Scheduling…" : "Generate proposal drafts"}
        </button>
      )}
      {error && (
        <p className="message error" role="alert">
          {error}
        </p>
      )}
      {run && (
        <>
          <p role="status">
            {run.state === "complete"
              ? "Automated drafting finished."
              : run.state === "failed"
                ? "Processing needs attention."
                : "Drafting continues in the background."}
          </p>
          {(run.error_message || run.stalled) && (
            <div className="message error" role="alert">
              <p>
                {run.error_message ||
                  "The worker has not reported progress recently. Saved drafts are retained."}
              </p>
              {run.can_retry && (
                <button disabled={busy} onClick={() => void start(true)}>
                  {busy ? "Scheduling…" : "Resume saved drafts"}
                </button>
              )}
            </div>
          )}
          {ticket.sections.map((section) => {
            const attempts = run.attempts.filter(
              (a) => a.department_id === section.department_id,
            );
            const latest = attempts[attempts.length - 1];
            const progress = run.progress[section.department_id];
            return (
              <article className="panel" key={section.department_id}>
                <h4>
                  {labels[section.department_id]} — {section.owner}
                </h4>
                <p>
                  <strong>
                    {progress
                      ? phases[progress.phase] || progress.phase
                      : "Queued"}
                  </strong>
                  {progress && (
                    <>
                      {" "}
                      · Attempt {progress.attempt} of {progress.max_attempts}
                    </>
                  )}
                </p>
                {progress?.phase === "needs_human_review" && (
                  <p className="message error">
                    The revision limit was reached. This provisional draft and
                    its failed checks are retained for the department owner; the
                    ticket has not been discarded.
                  </p>
                )}
                {latest && (
                  <>
                    <div
                      style={{
                        whiteSpace: "pre-wrap",
                        overflowWrap: "anywhere",
                      }}
                      aria-label={`${labels[section.department_id]} proposal draft`}
                    >
                      {latest.draft.content}
                    </div>
                    {latest.draft.open_questions.length > 0 && (
                      <>
                        <h5>Still needs confirmation</h5>
                        <ul>
                          {latest.draft.open_questions.map((q, i) => (
                            <li key={i}>{q}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    <Evaluation attempt={latest} />
                  </>
                )}
                {attempts.length > 1 && (
                  <details>
                    <summary>Earlier drafts and evaluations</summary>
                    {attempts.slice(0, -1).map((a) => (
                      <article key={a.version}>
                        <h5>Draft {a.version}</h5>
                        <p style={{ whiteSpace: "pre-wrap" }}>
                          {a.draft.content}
                        </p>
                        <Evaluation attempt={a} />
                      </article>
                    ))}
                  </details>
                )}
              </article>
            );
          })}
          {run.handoff?.ready_for_part3 && (
            <p className="message">
              All assigned sections, including any that need human review, are
              saved for Part 3. Automated checks do not approve a proposal or
              authorize a customer commitment.
            </p>
          )}
        </>
      )}
    </section>
  );
}
