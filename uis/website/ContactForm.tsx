"use client";

import { useState } from "react";
import { createCandidate } from "../../src/candidates/api";
import type { CandidateWriteInput } from "../../src/candidates/types";
import { LOW_VOLUME_WARNING } from "../../src/utils/validations";
import { userSafeErrorMessage } from "../../src/utils/api-errors";

const serviceOptions = [
  { label: "Warehousing", value: "warehouse-management" },
  { label: "Last mile", value: "last-mile-delivery" },
  { label: "Reverse logistics", value: "reverse-logistics" },
] as const;

type ContactFormState = Omit<CandidateWriteInput, "status" | "stage" | "assignedTo" | "companyWebsite" | "comments"> & {
  companyWebsite: string;
  comments: string;
};

const initialForm: ContactFormState = {
  companyName: "",
  contactPerson: "",
  corporateEmail: "",
  phone: "",
  companyWebsite: "",
  operatingCountry: "United States",
  productType: "Fashion",
  monthlyVolume: "Not sure",
  servicesOfInterest: [],
  current3pl: "No",
  comments: "",
  privacyAccepted: false,
};

const successMessage = "Thank you for your interest in TrackFlow!";

export default function ContactForm() {
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState<string[]>([]);
  const [errorFields, setErrorFields] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "submitting" | "success">("idle");
  const [apiError, setApiError] = useState("");

  const lowVolumeWarning = form.monthlyVolume === "0-100";

  function updateField<K extends keyof typeof form>(field: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [field]: value }));
    setStatus("idle");
    setApiError("");
  }

  function toggleService(service: CandidateWriteInput["servicesOfInterest"][number]) {
    const selected = form.servicesOfInterest.includes(service)
      ? form.servicesOfInterest.filter((item) => item !== service)
      : [...form.servicesOfInterest, service];
    updateField("servicesOfInterest", selected);
  }

  function validate(): { messages: string[]; fields: string[] } {
    const messages: string[] = [];
    const fields: string[] = [];
    if (form.companyName.trim().length < 2) { messages.push("Company name must have at least 2 characters"); fields.push("companyName"); }
    if (form.contactPerson.trim().split(/\s+/).filter(Boolean).length < 2) { messages.push("Enter first and last name of contact"); fields.push("contactPerson"); }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.corporateEmail.trim())) { messages.push("Enter a valid corporate email (example: name@company.com)"); fields.push("corporateEmail"); }
    if (!/^\+\d{1,3}[\d\s().-]{7,20}$/.test(form.phone.trim())) { messages.push("Phone must include country code (example: +1 213 555 0147)"); fields.push("phone"); }
    if (form.companyWebsite && (!/^https?:\/\//i.test(form.companyWebsite) || !/^https?:\/\/[^\s]+$/i.test(form.companyWebsite))) { messages.push("If you include website, it must be a valid URL"); fields.push("companyWebsite"); }
    if (!form.operatingCountry) { messages.push("Select main operating country"); fields.push("operatingCountry"); }
    if (!form.productType) { messages.push("Select the type of product you handle"); fields.push("productType"); }
    if (!form.monthlyVolume) { messages.push("Select estimated monthly volume"); fields.push("monthlyVolume"); }
    if (form.servicesOfInterest.length === 0) { messages.push("Select at least one service of interest"); fields.push("servicesOfInterest"); }
    if (!form.current3pl) { messages.push("Indicate if you currently work with another logistics provider"); fields.push("current3pl"); }
    if (form.comments.length > 500) { messages.push(`Comments cannot exceed 500 characters (${500 - form.comments.length} remaining)`); fields.push("comments"); }
    if (!form.privacyAccepted) { messages.push("You must accept the privacy policy to continue"); fields.push("privacyAccepted"); }
    return { messages, fields };
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validation = validate();
    setErrors(validation.messages);
    setErrorFields(validation.fields);
    setApiError("");
    if (validation.messages.length > 0) return;

    setStatus("submitting");
    try {
      await createCandidate({ ...form, status: "new", stage: "intake", assignedTo: "Commercial Desk" });
      setStatus("success");
      setForm(initialForm);
      setErrors([]);
      setErrorFields([]);
    } catch (error) {
      setStatus("idle");
      setApiError(userSafeErrorMessage(error, "Your request could not be submitted. Check your connection and retry."));
    }
  }

  if (status === "success") {
    return (
      <div className="panel message success" role="status">
        <h2>{successMessage}</h2>
        <p>We have received your request. Our commercial team will review your information and contact you within the next 24-48 hours to schedule a call and learn about your logistics needs in detail.</p>
        <p>If you have any urgent inquiry, write to us directly at <a href="mailto:comercial@trackflow.com">comercial@trackflow.com</a></p>
      </div>
    );
  }

  return (
    <form id="contact-form" className="panel" aria-label="TrackFlow information request form" onSubmit={handleSubmit} noValidate>
      <h2>Request information</h2>
      {errors.length > 0 && <div className="message error" role="alert"><p>Please review the following:</p><ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul></div>}
      {apiError && <p className="message error" role="alert">{apiError}</p>}
      <div className="form-grid">
        <label className="field"><span>Company name</span><input name="companyName" value={form.companyName} onChange={(event) => updateField("companyName", event.target.value)} aria-invalid={errorFields.includes("companyName")} /></label>
        <label className="field"><span>Contact person</span><input name="contactPerson" value={form.contactPerson} onChange={(event) => updateField("contactPerson", event.target.value)} aria-invalid={errorFields.includes("contactPerson")} /></label>
        <label className="field"><span>Corporate email</span><input name="corporateEmail" type="email" value={form.corporateEmail} onChange={(event) => updateField("corporateEmail", event.target.value)} aria-invalid={errorFields.includes("corporateEmail")} /></label>
        <label className="field"><span>Phone</span><input name="phone" placeholder="+1 213 555 0147" value={form.phone} onChange={(event) => updateField("phone", event.target.value)} aria-invalid={errorFields.includes("phone")} /></label>
        <label className="field"><span>Company website</span><input name="companyWebsite" type="url" placeholder="https://example.com" value={form.companyWebsite} onChange={(event) => updateField("companyWebsite", event.target.value)} aria-invalid={errorFields.includes("companyWebsite")} /></label>
        <label className="field"><span>Main operating country</span><select name="operatingCountry" value={form.operatingCountry} onChange={(event) => updateField("operatingCountry", event.target.value as typeof form.operatingCountry)}><option value="">Select a country</option><option>United States</option><option>Spain</option><option>Both</option><option>Other</option></select></label>
        <label className="field"><span>Product type</span><select name="productType" value={form.productType} onChange={(event) => updateField("productType", event.target.value as typeof form.productType)}><option value="">Select a product type</option><option>Fashion</option><option>Electronics</option><option>Cosmetics</option><option>Food</option><option>Other</option></select></label>
        <label className="field"><span>Estimated monthly shipping volume</span><select name="monthlyVolume" value={form.monthlyVolume} onChange={(event) => updateField("monthlyVolume", event.target.value as typeof form.monthlyVolume)}><option value="">Select a volume</option><option>0-100</option><option>101-500</option><option>501-2000</option><option>2000+</option><option>Not sure</option></select></label>
      </div>
      <fieldset className="field" style={{ marginTop: "1rem" }}><legend>Services of interest</legend><div className="checkboxes">{serviceOptions.map((service) => <label key={service.value}><input type="checkbox" checked={form.servicesOfInterest.includes(service.value)} onChange={() => toggleService(service.value)} />{service.label}</label>)}</div></fieldset>
      <fieldset className="field" style={{ marginTop: "1rem" }}><legend>Do you currently work with another 3PL?</legend><div className="checkboxes">{(["Yes", "No", "Evaluating options"] as const).map((option) => <label key={option}><input type="radio" name="current3pl" checked={form.current3pl === option} onChange={() => updateField("current3pl", option)} />{option}</label>)}</div></fieldset>
      {lowVolumeWarning && <p className="message warning" role="note">{LOW_VOLUME_WARNING}</p>}
      <label className="field" style={{ marginTop: "1rem" }}><span>Comments or specific needs</span><textarea name="comments" maxLength={500} value={form.comments} onChange={(event) => updateField("comments", event.target.value)} aria-invalid={errorFields.includes("comments")} /><small>{form.comments.length}/500 characters</small></label>
      <label className="field" style={{ marginTop: "1rem" }}><span><input name="privacyPolicy" type="checkbox" checked={form.privacyAccepted} onChange={(event) => updateField("privacyAccepted", event.target.checked)} style={{ minHeight: "auto", width: "auto" }} /> I accept the privacy policy</span></label>
      <button type="submit" style={{ marginTop: "1rem" }} disabled={status === "submitting"}>{status === "submitting" ? "Submitting..." : "Submit request"}</button>
    </form>
  );
}
