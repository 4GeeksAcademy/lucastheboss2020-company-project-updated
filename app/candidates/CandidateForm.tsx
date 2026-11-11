"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import type { Candidate, CandidateWriteInput } from "../../src/candidates/types";
import { CANDIDATE_STAGES, CANDIDATE_STATUSES, MONTHLY_VOLUMES, OPERATING_COUNTRIES, PRODUCT_TYPES, SERVICES, THREE_PL_STATUSES } from "../../src/candidates/types";
import { userSafeErrorMessage } from "../../src/utils/api-errors";

const emptyInput: CandidateWriteInput = {
  companyName: "",
  contactPerson: "",
  corporateEmail: "",
  phone: "",
  companyWebsite: "",
  operatingCountry: "United States",
  productType: "Fashion",
  monthlyVolume: "101-500",
  servicesOfInterest: ["warehouse-management"],
  current3pl: "Evaluating options",
  comments: "",
  privacyAccepted: true,
  status: "new",
  stage: "intake",
  assignedTo: "Miguel Torres",
};

export function candidateToInput(candidate?: Candidate): CandidateWriteInput {
  if (!candidate) {
    return emptyInput;
  }

  return {
    companyName: candidate.companyName,
    contactPerson: candidate.contactPerson,
    corporateEmail: candidate.corporateEmail,
    phone: candidate.phone,
    companyWebsite: candidate.companyWebsite ?? "",
    operatingCountry: candidate.operatingCountry,
    productType: candidate.productType,
    monthlyVolume: candidate.monthlyVolume,
    servicesOfInterest: candidate.servicesOfInterest,
    current3pl: candidate.current3pl,
    comments: candidate.comments ?? "",
    privacyAccepted: candidate.privacyAccepted,
    status: candidate.status,
    stage: candidate.stage,
    assignedTo: candidate.assignedTo,
  };
}

interface CandidateFormProps {
  candidate?: Candidate;
  submitLabel: string;
  onSubmit: (input: CandidateWriteInput) => Promise<void>;
}

export default function CandidateForm({ candidate, submitLabel, onSubmit }: CandidateFormProps) {
  const [input, setInput] = useState<CandidateWriteInput>(() => candidateToInput(candidate));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function setField<K extends keyof CandidateWriteInput>(key: K, value: CandidateWriteInput[K]) {
    setInput((current) => ({ ...current, [key]: value }));
  }

  function toggleService(service: CandidateWriteInput["servicesOfInterest"][number]) {
    setInput((current) => {
      const selected = current.servicesOfInterest.includes(service)
        ? current.servicesOfInterest.filter((item) => item !== service)
        : [...current.servicesOfInterest, service];
      return { ...current, servicesOfInterest: selected };
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);

    try {
      await onSubmit(input);
    } catch (submitError) {
      setError(userSafeErrorMessage(submitError, "Candidate could not be saved. Please retry."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="panel" onSubmit={handleSubmit}>
      {error && <p className="message error" role="alert">{error}</p>}
      {saving && <p className="message loading">Saving candidate...</p>}

      <div className="form-grid">
        <label className="field">
          <span>Company name</span>
          <input required minLength={2} value={input.companyName} onChange={(event) => setField("companyName", event.target.value)} />
        </label>
        <label className="field">
          <span>Contact person</span>
          <input required value={input.contactPerson} onChange={(event) => setField("contactPerson", event.target.value)} />
        </label>
        <label className="field">
          <span>Corporate email</span>
          <input required type="email" value={input.corporateEmail} onChange={(event) => setField("corporateEmail", event.target.value)} />
        </label>
        <label className="field">
          <span>Phone</span>
          <input required value={input.phone} placeholder="+1 213 555 0147" onChange={(event) => setField("phone", event.target.value)} />
        </label>
        <label className="field">
          <span>Company website</span>
          <input type="url" value={input.companyWebsite} onChange={(event) => setField("companyWebsite", event.target.value)} />
        </label>
        <label className="field">
          <span>Assigned TrackFlow owner</span>
          <input required value={input.assignedTo} onChange={(event) => setField("assignedTo", event.target.value)} />
        </label>
        <label className="field">
          <span>Main operating country</span>
          <select value={input.operatingCountry} onChange={(event) => setField("operatingCountry", event.target.value as CandidateWriteInput["operatingCountry"])}>
            {OPERATING_COUNTRIES.map((country) => <option key={country} value={country}>{country}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Product type</span>
          <select value={input.productType} onChange={(event) => setField("productType", event.target.value as CandidateWriteInput["productType"])}>
            {PRODUCT_TYPES.map((productType) => <option key={productType} value={productType}>{productType}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Monthly shipping volume</span>
          <select value={input.monthlyVolume} onChange={(event) => setField("monthlyVolume", event.target.value as CandidateWriteInput["monthlyVolume"])}>
            {MONTHLY_VOLUMES.map((volume) => <option key={volume} value={volume}>{volume}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Current 3PL</span>
          <select value={input.current3pl} onChange={(event) => setField("current3pl", event.target.value as CandidateWriteInput["current3pl"])}>
            {THREE_PL_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Status</span>
          <select value={input.status} onChange={(event) => setField("status", event.target.value as CandidateWriteInput["status"])}>
            {CANDIDATE_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </label>
        <label className="field">
          <span>Stage</span>
          <select value={input.stage} onChange={(event) => setField("stage", event.target.value as CandidateWriteInput["stage"])}>
            {CANDIDATE_STAGES.map((stage) => <option key={stage} value={stage}>{stage}</option>)}
          </select>
        </label>
      </div>

      <fieldset className="field" style={{ marginTop: "1rem" }}>
        <legend>Services of interest</legend>
        <div className="checkboxes">
          {SERVICES.map((service) => (
            <label key={service}>
              <input type="checkbox" checked={input.servicesOfInterest.includes(service)} onChange={() => toggleService(service)} />
              {service.replace(/-/g, " ")}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="field" style={{ marginTop: "1rem" }}>
        <span>Comments or specific needs</span>
        <textarea maxLength={500} value={input.comments} onChange={(event) => setField("comments", event.target.value)} />
      </label>

      <label className="field" style={{ marginTop: "1rem" }}>
        <span>Privacy acceptance</span>
        <select value={String(input.privacyAccepted)} onChange={(event) => setField("privacyAccepted", event.target.value === "true")}>
          <option value="true">Accepted</option>
          <option value="false">Not accepted</option>
        </select>
      </label>

      <div className="actions" style={{ marginTop: "1rem" }}>
        <button disabled={saving} type="submit">{submitLabel}</button>
      </div>
    </form>
  );
}
