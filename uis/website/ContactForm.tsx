"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import WebsiteIcon from "./WebsiteIcon";
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

function FormField({ name, label, error, optional, children }: { name: string; label: string; error?: string; optional?: boolean; children: ReactNode }) {
  return <div className="tf-form-field"><label htmlFor={`contact-${name}`}>{label}{optional && <span className="tf-optional" aria-hidden="true">Optional</span>}</label>{children}{error && <span id={`contact-${name}-error`} className="tf-field-error">{error}</span>}</div>;
}

export default function ContactForm() {
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState<string[]>([]);
  const [errorFields, setErrorFields] = useState<string[]>([]);
  const [status, setStatus] = useState<"idle" | "submitting" | "success">("idle");
  const [apiError, setApiError] = useState("");
  const errorSummary = useRef<HTMLDivElement>(null);
  const successPanel = useRef<HTMLDivElement>(null);
  useEffect(() => { if (status === "success") successPanel.current?.focus(); }, [status]);

  function fieldError(name: string) { const index = errorFields.indexOf(name); return index >= 0 ? errors[index] : undefined; }
  function control(name: string) {
    return { id: `contact-${name}`, name, "aria-invalid": errorFields.includes(name), "aria-describedby": fieldError(name) ? `contact-${name}-error` : undefined };
  }

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
    if (validation.messages.length > 0) { requestAnimationFrame(() => errorSummary.current?.focus()); return; }

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
      <div id="contact-form" ref={successPanel} tabIndex={-1} className="tf-form-success" role="status">
        <span className="tf-icon-tile"><WebsiteIcon name="check" /></span>
        <h2>{successMessage}</h2>
        <p>We have received your request. Our commercial team will review your information and contact you within the next 24-48 hours to schedule a call and learn about your logistics needs in detail.</p>
        <p>If you have any urgent inquiry, write to us directly at <a href="mailto:comercial@trackflow.com">comercial@trackflow.com</a></p>
      </div>
    );
  }

  return (
    <form id="contact-form" className="tf-contact-form" aria-label="TrackFlow information request form" onSubmit={handleSubmit} noValidate>
      <h2>Request information</h2>
      <p>A few details will help us understand your business.</p>
      {errors.length > 0 && <div ref={errorSummary} tabIndex={-1} className="message error" role="alert"><strong>Please review the following:</strong><ul>{errors.map((error, index) => <li key={error}><a href={`#contact-${errorFields[index]}`}>{error}</a></li>)}</ul></div>}
      {apiError && <p className="message error" role="alert">{apiError}</p>}
      <fieldset disabled={status === "submitting"}><legend className="tf-sr-only">Information request details</legend>
        <fieldset className="tf-form-section"><legend><span>01</span>Your company</legend><div className="tf-form-grid">
          <FormField name="companyName" label="Company name" error={fieldError("companyName")}><input {...control("companyName")} required autoComplete="organization" placeholder="Your company" value={form.companyName} onChange={event => updateField("companyName", event.target.value)} /></FormField>
          <FormField name="contactPerson" label="Contact person" error={fieldError("contactPerson")}><input {...control("contactPerson")} required autoComplete="name" placeholder="First and last name" value={form.contactPerson} onChange={event => updateField("contactPerson", event.target.value)} /></FormField>
          <FormField name="corporateEmail" label="Corporate email" error={fieldError("corporateEmail")}><input {...control("corporateEmail")} required type="email" autoComplete="email" placeholder="name@company.com" value={form.corporateEmail} onChange={event => updateField("corporateEmail", event.target.value)} /></FormField>
          <FormField name="phone" label="Phone" error={fieldError("phone")}><input {...control("phone")} required type="tel" autoComplete="tel" placeholder="+1 213 555 0147" value={form.phone} onChange={event => updateField("phone", event.target.value)} /></FormField>
          <FormField name="companyWebsite" label="Company website" optional error={fieldError("companyWebsite")}><input {...control("companyWebsite")} type="url" autoComplete="url" placeholder="https://example.com" value={form.companyWebsite} onChange={event => updateField("companyWebsite", event.target.value)} /></FormField>
          <FormField name="operatingCountry" label="Main operating country" error={fieldError("operatingCountry")}><select {...control("operatingCountry")} required value={form.operatingCountry} onChange={event => updateField("operatingCountry", event.target.value as typeof form.operatingCountry)}><option value="">Select a country</option><option>United States</option><option>Spain</option><option>Both</option><option>Other</option></select></FormField>
        </div></fieldset>
        <fieldset className="tf-form-section"><legend><span>02</span>Your logistics needs</legend><div className="tf-form-grid">
          <FormField name="productType" label="Product type" error={fieldError("productType")}><select {...control("productType")} required value={form.productType} onChange={event => updateField("productType", event.target.value as typeof form.productType)}><option value="">Select a product type</option><option>Fashion</option><option>Electronics</option><option>Cosmetics</option><option>Food</option><option>Other</option></select></FormField>
          <FormField name="monthlyVolume" label="Estimated monthly shipping volume" error={fieldError("monthlyVolume")}><select {...control("monthlyVolume")} required value={form.monthlyVolume} onChange={event => updateField("monthlyVolume", event.target.value as typeof form.monthlyVolume)}><option value="">Select a volume</option><option>0-100</option><option>101-500</option><option>501-2000</option><option>2000+</option><option>Not sure</option></select></FormField>
        </div>
          <fieldset id="contact-servicesOfInterest" className="tf-choice-group" aria-describedby={fieldError("servicesOfInterest") ? "contact-servicesOfInterest-error" : undefined}><legend>Services of interest</legend><div className="tf-choices">{serviceOptions.map(service => <label key={service.value}><input type="checkbox" checked={form.servicesOfInterest.includes(service.value)} onChange={() => toggleService(service.value)} />{service.label}</label>)}</div>{fieldError("servicesOfInterest") && <span className="tf-field-error" id="contact-servicesOfInterest-error">{fieldError("servicesOfInterest")}</span>}</fieldset>
          <fieldset id="contact-current3pl" className="tf-choice-group"><legend>Do you currently work with another 3PL?</legend><div className="tf-choices">{(["Yes", "No", "Evaluating options"] as const).map(option => <label key={option}><input type="radio" name="current3pl" checked={form.current3pl === option} onChange={() => updateField("current3pl", option)} />{option}</label>)}</div></fieldset>
          {lowVolumeWarning && <p className="message warning" role="note">{LOW_VOLUME_WARNING}</p>}
        </fieldset>
        <fieldset className="tf-form-section"><legend><span>03</span>Anything else we should know?</legend>
          <FormField name="comments" label="Comments or specific needs" optional error={fieldError("comments")}><textarea {...control("comments")} maxLength={500} placeholder="Tell us about your products, plans, or requirements." value={form.comments} onChange={event => updateField("comments", event.target.value)} /><small className="tf-field-help">{form.comments.length}/500 characters</small></FormField>
          <label className="tf-privacy" htmlFor="contact-privacyAccepted"><input {...control("privacyAccepted")} name="privacyPolicy" type="checkbox" required checked={form.privacyAccepted} onChange={event => updateField("privacyAccepted", event.target.checked)} />I accept the privacy policy</label>
          {fieldError("privacyAccepted") && <p className="tf-field-error" id="contact-privacyAccepted-error">{fieldError("privacyAccepted")}</p>}
          <button type="submit" className="accent tf-form-submit" disabled={status === "submitting"}>{status === "submitting" ? "Submitting..." : "Submit request"}<WebsiteIcon name="arrow" /></button>
        </fieldset>
      </fieldset>
    </form>
  );
}
