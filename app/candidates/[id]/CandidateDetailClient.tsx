"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import CandidateForm from "../CandidateForm";
import { addCandidateNote, deleteCandidateNote, fetchCandidate, patchCandidateProgress, updateCandidate } from "../../../src/candidates/api";
import type { Candidate, CandidateWriteInput } from "../../../src/candidates/types";
import { CANDIDATE_STAGES, CANDIDATE_STATUSES } from "../../../src/candidates/types";
import { userSafeErrorMessage } from "../../../src/utils/api-errors";

export default function CandidateDetailClient({ id }: { id: string }) {
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    fetchCandidate(id)
      .then((result) => { if (active) setCandidate(result); })
      .catch((fetchError: unknown) => {
        if (active) setError(userSafeErrorMessage(fetchError, "Could not load this candidate. Please retry."));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id, retryVersion]);

  async function handleProgressChange(nextStatus: Candidate["status"], nextStage: Candidate["stage"]) {
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const updated = await patchCandidateProgress(id, nextStatus, nextStage);
      setCandidate(updated);
      setSuccess("Candidate status and stage were updated.");
    } catch (patchError) {
      setError(userSafeErrorMessage(patchError, "Progress could not be updated. Please retry."));
    } finally {
      setSaving(false);
    }
  }

  async function handleEdit(input: CandidateWriteInput) {
    const updated = await updateCandidate(id, input);
    setCandidate(updated);
    setSuccess("Candidate data was saved.");
  }

  async function handleAddNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const updated = await addCandidateNote(id, noteBody);
      setCandidate(updated);
      setNoteBody("");
      setSuccess("Note was added.");
    } catch (noteError) {
      setError(userSafeErrorMessage(noteError, "Note could not be added. Please retry."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteNote(noteId: string) {
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const updated = await deleteCandidateNote(id, noteId);
      setCandidate(updated);
      setSuccess("Note was deleted.");
    } catch (deleteError) {
      setError(userSafeErrorMessage(deleteError, "Note could not be deleted. Please retry."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="message loading">Loading candidate detail...</p>;
  }

  if (error && !candidate) {
    return (
      <div className="message error" role="alert">
        <p>{error}</p>
        <button className="secondary" type="button" onClick={() => setRetryVersion((version) => version + 1)}>Retry</button>
      </div>
    );
  }

  if (!candidate) {
    return <p className="message error" role="alert">Candidate was not found.</p>;
  }

  return (
    <section>
      <header className="page-header">
        <h1>{candidate.companyName}</h1>
        <p>{candidate.contactPerson} at {candidate.corporateEmail} is evaluating TrackFlow logistics support for {candidate.productType.toLowerCase()} e-commerce operations.</p>
      </header>

      {error && <p className="message error" role="alert">{error}</p>}
      {success && <p className="message success">{success}</p>}
      {saving && <p className="message loading">Saving changes...</p>}

      <section className="detail-grid">
        <article className="panel">
          <h2>Candidate details</h2>
          <p><strong>Phone:</strong> {candidate.phone}</p>
          <p><strong>Website:</strong> {candidate.companyWebsite ? <a href={candidate.companyWebsite}>{candidate.companyWebsite}</a> : "Not provided"}</p>
          <p><strong>Operating country:</strong> {candidate.operatingCountry}</p>
          <p><strong>Monthly volume:</strong> {candidate.monthlyVolume}</p>
          <p><strong>Services:</strong> {candidate.servicesOfInterest.map((service) => service.replace(/-/g, " ")).join(", ")}</p>
          <p><strong>Current 3PL:</strong> {candidate.current3pl}</p>
          <p><strong>Assigned to:</strong> {candidate.assignedTo}</p>
          <p><strong>Comments:</strong> {candidate.comments || "No comments yet."}</p>
        </article>

        <aside className="panel">
          <h2>Pipeline progress</h2>
          <label className="field">
            <span>Status</span>
            <select disabled={saving} value={candidate.status} onChange={(event) => handleProgressChange(event.target.value as Candidate["status"], candidate.stage)}>
              {CANDIDATE_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </label>
          <label className="field" style={{ marginTop: "1rem" }}>
            <span>Stage</span>
            <select disabled={saving} value={candidate.stage} onChange={(event) => handleProgressChange(candidate.status, event.target.value as Candidate["stage"])}>
              {CANDIDATE_STAGES.map((stage) => <option key={stage} value={stage}>{stage}</option>)}
            </select>
          </label>
        </aside>
      </section>

      <section className="detail-grid" style={{ marginTop: "1rem" }}>
        <article className="panel">
          <h2>Notes</h2>
          <form onSubmit={handleAddNote}>
            <label className="field">
              <span>Add note</span>
              <textarea value={noteBody} onChange={(event) => setNoteBody(event.target.value)} placeholder="Record next steps with the TrackFlow commercial team." />
            </label>
            <button disabled={saving} type="submit" style={{ marginTop: "0.75rem" }}>Add note</button>
          </form>
          <ul className="note-list">
            {candidate.notes.map((note) => (
              <li key={note.id}>
                <p>{note.body}</p>
                <div className="actions">
                  <span className="badge">{new Date(note.createdAt).toLocaleString()}</span>
                  <button className="danger" disabled={saving} type="button" onClick={() => handleDeleteNote(note.id)}>Delete</button>
                </div>
              </li>
            ))}
          </ul>
        </article>

        <article>
          <CandidateForm candidate={candidate} submitLabel="Save candidate" onSubmit={handleEdit} />
        </article>
      </section>

      <p style={{ marginTop: "1rem" }}><Link href={`/candidates?status=${candidate.status}`}>Back to filtered pipeline</Link></p>
    </section>
  );
}
