"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiRequestError, fetchJson, userSafeErrorMessage } from "../../src/utils/api-errors";
import { TRACKFLOW_TOKEN_KEY, trackFlowAuthHeaders } from "../../src/utils/auth-headers";
import rateStyles from "./SupplierRate.module.css";
import styles from "./SupplierDirectory.module.css";

export interface Supplier {
  id: number;
  name: string;
  country: string;
  categories: string[];
  rate_per_shipment: number;
  currency: string;
  status: "active" | "suspended";
  updated_at: string;
  service_zone?: string;
  contact_email?: string;
  notes?: string;
}

interface FormErrors {
  name?: string;
  country?: string;
  categories?: string;
  rate_per_shipment?: string;
  currency?: string;
}

const API_BASE = "/api/suppliers";

// TrackFlow constants per CONTEXT_3.md
const COUNTRIES = ["USA", "Spain"];

const VALID_CATEGORIES = [
  "carrier_last_mile",
  "carrier_international",
  "warehouse_supplies",
  "packaging_materials",
  "reverse_logistics",
  "fleet_maintenance",
  "it_and_wms_software",
  "cleaning_and_facilities",
];

function formatCategory(cat: string): string {
  return cat
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

function handleUnauthorized(): never {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TRACKFLOW_TOKEN_KEY);
    window.location.href = "/login";
  }
  throw new ApiRequestError("Your session expired. Please sign in again.", 401);
}

async function supplierRequest<T>(url: string, init?: RequestInit): Promise<T> {
  try {
    return await fetchJson<T>(url, init);
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401) handleUnauthorized();
    throw error;
  }
}

export default function SupplierDirectory() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusUpdateError, setStatusUpdateError] = useState<string | null>(null);

  // Filters
  const [countryFilter, setCountryFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  // Registration form
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formCountry, setFormCountry] = useState("");
  const [formCategories, setFormCategories] = useState<string[]>([]);
  const [formRatePerShipment, setFormRatePerShipment] = useState("");
  const [formCurrency, setFormCurrency] = useState("");
  const [formStatus, setFormStatus] = useState<"active" | "suspended">("active");
  const [formServiceZone, setFormServiceZone] = useState("");
  const [formContactEmail, setFormContactEmail] = useState("");
  const [formNotes, setFormNotes] = useState("");
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [formApiError, setFormApiError] = useState<string | null>(null);
  const [formSubmitting, setFormSubmitting] = useState(false);

  // Inline editing
  const [editingRate, setEditingRate] = useState<number | null>(null);
  const [editRateValue, setEditRateValue] = useState("");
  const [rateUpdateError, setRateUpdateError] = useState<string | null>(null);
  const [updatingRateId, setUpdatingRateId] = useState<number | null>(null);
  const [updatingStatusId, setUpdatingStatusId] = useState<number | null>(null);

  // Auto-currency when country changes
  useEffect(() => {
    if (formCountry === "USA") setFormCurrency("USD");
    else if (formCountry === "Spain") setFormCurrency("EUR");
  }, [formCountry]);

  const fetchSuppliers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (countryFilter) params.set("country", countryFilter);
      if (categoryFilter) params.set("category", categoryFilter);
      const url = `${API_BASE}${params.toString() ? "?" + params.toString() : ""}`;
      setSuppliers(await supplierRequest<Supplier[]>(url, { headers: { ...trackFlowAuthHeaders() } }));
    } catch (e) {
      setError(userSafeErrorMessage(e, "Could not load suppliers. Please retry."));
    } finally {
      setLoading(false);
    }
  }, [countryFilter, categoryFilter]);

  useEffect(() => {
    fetchSuppliers();
  }, [fetchSuppliers]);

  // ---- Validation ----
  function validateForm(): FormErrors {
    const errors: FormErrors = {};
    if (!formName || formName.trim().length < 2)
      errors.name = "Name is required (min 2 characters)";
    if (!formCountry) errors.country = "Country is required";
    if (formCategories.length === 0)
      errors.categories = "At least one category is required";
    if (!formCurrency) errors.currency = "Currency is required";
    const rateNum = parseFloat(formRatePerShipment);
    if (!formRatePerShipment || isNaN(rateNum) || rateNum <= 0)
      errors.rate_per_shipment = "Rate per shipment must be a positive number";
    return errors;
  }

  // ---- Create supplier ----
  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormApiError(null);
    const errors = validateForm();
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setFormSubmitting(true);
    try {
      const body: Record<string, unknown> = {
        name: formName.trim(),
        country: formCountry,
        categories: formCategories,
        rate_per_shipment: parseFloat(formRatePerShipment),
        currency: formCurrency,
        status: formStatus,
      };
      if (formServiceZone.trim()) body.service_zone = formServiceZone.trim();
      if (formContactEmail.trim()) body.contact_email = formContactEmail.trim();
      if (formNotes.trim()) body.notes = formNotes.trim();

      await supplierRequest<Supplier>(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...trackFlowAuthHeaders() },
        body: JSON.stringify(body),
      });
      // Reset form
      setShowForm(false);
      setFormName("");
      setFormCountry("");
      setFormCategories([]);
      setFormRatePerShipment("");
      setFormCurrency("");
      setFormStatus("active");
      setFormServiceZone("");
      setFormContactEmail("");
      setFormNotes("");
      setFormErrors({});
      await fetchSuppliers();
    } catch (e) {
      setFormApiError(userSafeErrorMessage(e, "Could not create the supplier. Please review the form and retry."));
    } finally {
      setFormSubmitting(false);
    }
  }

  // ---- Update rate ----
  async function handleRateUpdate(supplierId: number) {
    setRateUpdateError(null);
    const rateNum = parseFloat(editRateValue);
    if (isNaN(rateNum) || rateNum <= 0) {
      setRateUpdateError("Rate must be a positive number");
      return;
    }
    setUpdatingRateId(supplierId);
    try {
      await supplierRequest<Supplier>(`${API_BASE}/${supplierId}/rate`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...trackFlowAuthHeaders() },
        body: JSON.stringify({ rate_per_shipment: rateNum }),
      });
      setEditingRate(null);
      setEditRateValue("");
      await fetchSuppliers();
    } catch (e) {
      setRateUpdateError(userSafeErrorMessage(e, "Could not update the supplier rate. Please retry."));
    } finally {
      setUpdatingRateId(null);
    }
  }

  // ---- Toggle status ----
  async function handleToggleStatus(supplier: Supplier) {
    const newStatus = supplier.status === "active" ? "suspended" : "active";
    setStatusUpdateError(null);
    setUpdatingStatusId(supplier.id);
    try {
      await supplierRequest<Supplier>(`${API_BASE}/${supplier.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...trackFlowAuthHeaders() },
        body: JSON.stringify({ status: newStatus }),
      });
      await fetchSuppliers();
    } catch (e) {
      setStatusUpdateError(userSafeErrorMessage(e, "Could not update the supplier status. Please retry."));
    } finally {
      setUpdatingStatusId(null);
    }
  }

  // ---- Category toggle in form ----
  function toggleCategory(cat: string) {
    setFormCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  }

  // ---- Loading / error states ----
  return (
    <section className={styles.directory}>
      <header className={styles.heading}>
        <div><span className={styles.eyebrow}>TRACKFLOW PARTNER NETWORK</span><h1>Supplier directory</h1><p>Manage the partners supporting your operations in the United States and Spain.</p></div>
        <button
          onClick={() => setShowForm(!showForm)}
          className={showForm ? "secondary" : "accent"}
          aria-expanded={showForm}
          aria-controls="supplier-registration"
        >
          {showForm ? "Cancel" : "Register Supplier"}
        </button>
      </header>

      {/* ---- Registration Form ---- */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className={styles.form}
          id="supplier-registration"
          aria-label="Register a supplier"
        >
          <h2>New supplier</h2><p className={styles.formIntro}>Add a partner to your directory. Fields marked * are required.</p>
          {formApiError && (
            <div className={styles.error} role="alert">
              {formApiError}
            </div>
          )}

          <div className={styles.formGrid}>
            {/* Name */}
            <div>
              <label htmlFor="supplier-name" className="block text-sm font-medium text-gray-700 mb-1">
                Name *
              </label>
              <input
                type="text"
                id="supplier-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className={`w-full rounded border px-3 py-2 text-sm ${
                  formErrors.name ? "border-red-400" : "border-gray-300"
                }`}
              />
              {formErrors.name && (
                <p className="mt-1 text-xs text-red-600">{formErrors.name}</p>
              )}
            </div>

            {/* Country */}
            <div>
              <label htmlFor="supplier-country" className="block text-sm font-medium text-gray-700 mb-1">
                Country *
              </label>
              <select
                id="supplier-country"
                value={formCountry}
                onChange={(e) => setFormCountry(e.target.value)}
                className={`w-full rounded border px-3 py-2 text-sm ${
                  formErrors.country ? "border-red-400" : "border-gray-300"
                }`}
              >
                <option value="">-- Select country --</option>
                {COUNTRIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              {formErrors.country && (
                <p className="mt-1 text-xs text-red-600">{formErrors.country}</p>
              )}
            </div>

            {/* Rate per Shipment */}
            <div>
              <label htmlFor="supplier-rate" className="block text-sm font-medium text-gray-700 mb-1">
                Rate per Shipment *
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                id="supplier-rate"
                value={formRatePerShipment}
                onChange={(e) => setFormRatePerShipment(e.target.value)}
                className={`w-full rounded border px-3 py-2 text-sm ${
                  formErrors.rate_per_shipment ? "border-red-400" : "border-gray-300"
                }`}
              />
              {formErrors.rate_per_shipment && (
                <p className="mt-1 text-xs text-red-600">{formErrors.rate_per_shipment}</p>
              )}
            </div>

            {/* Currency — auto-set from country, but editable */}
            <div>
              <label htmlFor="supplier-currency" className="block text-sm font-medium text-gray-700 mb-1">
                Currency *
              </label>
              <select
                id="supplier-currency"
                value={formCurrency}
                onChange={(e) => setFormCurrency(e.target.value)}
                className={`w-full rounded border px-3 py-2 text-sm ${
                  formErrors.currency ? "border-red-400" : "border-gray-300"
                }`}
              >
                <option value="">-- Select --</option>
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
              </select>
              {formErrors.currency && (
                <p className="mt-1 text-xs text-red-600">{formErrors.currency}</p>
              )}
            </div>

            {/* Status */}
            <div>
              <label htmlFor="supplier-status" className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
                id="supplier-status"
                value={formStatus}
                onChange={(e) =>
                  setFormStatus(e.target.value as "active" | "suspended")
                }
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="active">Active</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>

            {/* Service Zone (optional) */}
            <div>
              <label htmlFor="supplier-zone" className="block text-sm font-medium text-gray-700 mb-1">
                Service Zone
              </label>
              <input
                type="text"
                id="supplier-zone"
                value={formServiceZone}
                onChange={(e) => setFormServiceZone(e.target.value)}
                placeholder="e.g. West Coast, Aragón"
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
            </div>

            {/* Contact Email (optional) */}
            <div>
              <label htmlFor="supplier-email" className="block text-sm font-medium text-gray-700 mb-1">
                Contact Email
              </label>
              <input
                type="email"
                id="supplier-email"
                value={formContactEmail}
                onChange={(e) => setFormContactEmail(e.target.value)}
                placeholder="supplier@example.com"
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
          </div>

          {/* Categories */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Categories *
            </label>
            <div className="flex flex-wrap gap-2">
              {VALID_CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  className={`${styles.categoryChoice} ${formCategories.includes(cat) ? styles.selectedChoice : ""}`}
                  aria-pressed={formCategories.includes(cat)}
                >
                  {formatCategory(cat)}
                </button>
              ))}
            </div>
            {formErrors.categories && (
              <p className="mt-1 text-xs text-red-600">
                {formErrors.categories}
              </p>
            )}
          </div>

          {/* Notes (optional) */}
          <div>
            <label htmlFor="supplier-notes" className="block text-sm font-medium text-gray-700 mb-1">
              Notes
            </label>
            <textarea
              id="supplier-notes"
                value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              placeholder="Operations team notes..."
              rows={2}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={formSubmitting}
            className="accent"
          >
            {formSubmitting ? "Creating…" : "Create Supplier"}
          </button>
        </form>
      )}

      {/* ---- Filters ---- */}
      <section className={styles.panel} aria-labelledby="supplier-results-title">
      <div className={styles.panelHeader}><div><h2 id="supplier-results-title">Your suppliers</h2><p role="status">{loading ? "Loading suppliers…" : error ? "The supplier list could not be refreshed." : `${suppliers.length} ${suppliers.length === 1 ? "supplier" : "suppliers"} shown`}</p></div><button className="secondary" type="button" onClick={fetchSuppliers} disabled={loading}>Refresh list</button></div>
      <div className={styles.filters} role="search" aria-label="Filter suppliers">
        <div>
          <label htmlFor="supplier-country-filter">Country</label>
          <select
            id="supplier-country-filter"
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          >
            <option value="">All</option>
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="supplier-category-filter">Category</label>
          <select
            id="supplier-category-filter"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          >
            <option value="">All</option>
            {VALID_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {formatCategory(c)}
              </option>
            ))}
          </select>
        </div>
        {(countryFilter || categoryFilter) && (
          <button
            onClick={() => {
              setCountryFilter("");
              setCategoryFilter("");
            }}
            className={`secondary ${styles.clearFilters}`}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* ---- Error banner ---- */}
      {error && (
        <div className={styles.error} role="alert">
          {error}
          <button className="secondary compact-button" type="button" onClick={fetchSuppliers} style={{ marginLeft: "0.75rem" }}>Retry list load</button>
        </div>
      )}
      {rateUpdateError && (
        <div className={styles.error} role="alert">
          {rateUpdateError}
        </div>
      )}
      {statusUpdateError && (
        <div className={styles.error} role="alert">
          {statusUpdateError}
        </div>
      )}

      {/* ---- Supplier Table ---- */}
      <div className={styles.tableRegion} role="region" aria-label="Supplier rates and availability" tabIndex={0} aria-busy={loading}>
        <table className={styles.table}>
          <caption className={styles.srOnly}>Supplier directory with shipment rates, currencies, status, and management actions.</caption>
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Name</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Country</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Categories</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Rate/Shipment</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">Currency</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">Status</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {suppliers.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td data-label="Supplier" className={styles.supplierName}>{s.name}</td>
                <td data-label="Country">{s.country === "USA" ? "United States" : s.country}</td>
                <td data-label="Categories" className={styles.categories}>
                  <div>{s.categories.map((category) => <span key={category}>{formatCategory(category)}</span>)}</div>
                </td>
                <td data-label="Rate / shipment" className={styles.rateCell}>
                  {editingRate === s.id ? (
                    <span className={styles.rateEditor}>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={editRateValue}
                        aria-label={`Rate per shipment for ${s.name}`}
                        onChange={(e) => setEditRateValue(e.target.value)}
                        className="w-20 rounded border border-gray-300 px-2 py-1 text-xs text-right"
                        autoFocus
                      />
                      <button
                        onClick={() => handleRateUpdate(s.id)}
                        disabled={updatingRateId === s.id}
                        className={styles.saveRate}
                        type="button"
                      >
                        {updatingRateId === s.id ? "Saving…" : "Save"}
                      </button>
                      <button
                        onClick={() => {
                          setEditingRate(null);
                          setRateUpdateError(null);
                        }}
                        className={styles.cancelRate}
                        type="button"
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <span className={rateStyles.rate}>
                      {s.rate_per_shipment.toFixed(2)}
                      <button
                        onClick={() => {
                          setEditingRate(s.id);
                          setEditRateValue(s.rate_per_shipment.toString());
                          setRateUpdateError(null);
                        }}
                        className={rateStyles.edit}
                        type="button"
                        aria-label={`Edit rate for ${s.name}`}
                        title="Edit rate"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m15 5 4 4M4 20l4-1 12-12a2.8 2.8 0 0 0-4-4L4 15Z" /></svg>
                      </button>
                    </span>
                  )}
                </td>
                <td data-label="Currency" className={styles.currency}>{s.currency}</td>
                <td data-label="Status">
                  <span
                    className={`${styles.status} ${s.status === "active" ? styles.active : styles.suspended}`}
                  >
                    {s.status}
                  </span>
                </td>
                <td data-label="Action" className={styles.actionCell}>
                  <button
                    onClick={() => handleToggleStatus(s)}
                        disabled={updatingStatusId === s.id}
                    className={`${styles.statusAction} ${s.status === "active" ? styles.suspendAction : styles.activateAction}`}
                    type="button"
                    aria-label={`${s.status === "active" ? "Suspend" : "Activate"} ${s.name}`}
                  >
                    {updatingStatusId === s.id ? "Updating…" : s.status === "active" ? "Suspend" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {suppliers.length === 0 && !loading && !error && (
        <p className={styles.empty}>
          {countryFilter || categoryFilter ? "No suppliers match these filters. Try another country or category." : "No suppliers registered yet. Register a supplier to get started."}
        </p>
      )}
      </section>
    </section>
  );
}
