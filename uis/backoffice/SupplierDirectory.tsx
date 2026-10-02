"use client";

import { useCallback, useEffect, useState } from "react";

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
    .replace(/_/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

export default function SupplierDirectory() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      setSuppliers((await res.json()) as Supplier[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load suppliers");
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

      const res = await fetch(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const responseBody = await res.json().catch(() => null);
        const detail = responseBody?.detail
          ? typeof responseBody.detail === "string"
            ? responseBody.detail
            : JSON.stringify(responseBody.detail)
          : `HTTP ${res.status}`;
        throw new Error(detail);
      }
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
      setFormApiError(e instanceof Error ? e.message : "Failed to create supplier");
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
    try {
      const res = await fetch(`${API_BASE}/${supplierId}/rate`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rate_per_shipment: rateNum }),
      });
      if (!res.ok) {
        const responseBody = await res.json().catch(() => null);
        const detail = responseBody?.detail
          ? typeof responseBody.detail === "string"
            ? responseBody.detail
            : JSON.stringify(responseBody.detail)
          : `HTTP ${res.status}`;
        throw new Error(detail);
      }
      setEditingRate(null);
      setEditRateValue("");
      await fetchSuppliers();
    } catch (e) {
      setRateUpdateError(e instanceof Error ? e.message : "Rate update failed");
    }
  }

  // ---- Toggle status ----
  async function handleToggleStatus(supplier: Supplier) {
    const newStatus = supplier.status === "active" ? "suspended" : "active";
    try {
      const res = await fetch(`${API_BASE}/${supplier.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) {
        const responseBody = await res.json().catch(() => null);
        const detail = responseBody?.detail
          ? typeof responseBody.detail === "string"
            ? responseBody.detail
            : JSON.stringify(responseBody.detail)
          : `HTTP ${res.status}`;
        throw new Error(detail);
      }
      await fetchSuppliers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Status update failed");
    }
  }

  // ---- Category toggle in form ----
  function toggleCategory(cat: string) {
    setFormCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  }

  // ---- Loading / error states ----
  if (loading && suppliers.length === 0)
    return <p className="text-gray-500">Loading suppliers…</p>;
  if (error && suppliers.length === 0)
    return <p className="text-red-500">{error}</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Supplier Directory</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          {showForm ? "Cancel" : "Register Supplier"}
        </button>
      </div>

      {/* ---- Registration Form ---- */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-4"
        >
          {formApiError && (
            <div className="rounded bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              API Error: {formApiError}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Name *
              </label>
              <input
                type="text"
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Country *
              </label>
              <select
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Rate per Shipment *
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Currency *
              </label>
              <select
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Service Zone
              </label>
              <input
                type="text"
                value={formServiceZone}
                onChange={(e) => setFormServiceZone(e.target.value)}
                placeholder="e.g. West Coast, Aragón"
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
            </div>

            {/* Contact Email (optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Contact Email
              </label>
              <input
                type="email"
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
                  className={`rounded-full px-3 py-1 text-xs font-semibold border ${
                    formCategories.includes(cat)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-700 border-gray-300 hover:bg-gray-100"
                  }`}
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
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Notes
            </label>
            <textarea
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
            className="rounded bg-green-600 px-6 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
          >
            {formSubmitting ? "Creating…" : "Create Supplier"}
          </button>
        </form>
      )}

      {/* ---- Filters ---- */}
      <div className="flex flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Country:</label>
          <select
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
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Category:</label>
          <select
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
            className="text-sm text-blue-600 hover:text-blue-800 underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* ---- Error banner ---- */}
      {error && (
        <div className="rounded bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {rateUpdateError && (
        <div className="rounded bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {rateUpdateError}
        </div>
      )}

      {/* ---- Supplier Table ---- */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
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
                <td className="px-4 py-3 font-medium text-gray-900">{s.name}</td>
                <td className="px-4 py-3 text-gray-700">{s.country}</td>
                <td className="px-4 py-3 text-gray-700">
                  {s.categories.map(formatCategory).join(", ")}
                </td>
                <td className="px-4 py-3 text-right text-gray-900">
                  {editingRate === s.id ? (
                    <span className="inline-flex items-center gap-1">
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={editRateValue}
                        onChange={(e) => setEditRateValue(e.target.value)}
                        className="w-20 rounded border border-gray-300 px-2 py-1 text-xs text-right"
                        autoFocus
                      />
                      <button
                        onClick={() => handleRateUpdate(s.id)}
                        className="text-xs text-green-600 hover:text-green-800 font-semibold"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setEditingRate(null);
                          setRateUpdateError(null);
                        }}
                        className="text-xs text-gray-500 hover:text-gray-700"
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1">
                      {s.rate_per_shipment.toFixed(2)}
                      <button
                        onClick={() => {
                          setEditingRate(s.id);
                          setEditRateValue(s.rate_per_shipment.toString());
                          setRateUpdateError(null);
                        }}
                        className="text-xs text-blue-600 hover:text-blue-800 ml-1"
                        title="Edit rate"
                      >
                        ✏️
                      </button>
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-center font-mono text-gray-900">{s.currency}</td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${
                      s.status === "active"
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {s.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => handleToggleStatus(s)}
                    className={`rounded px-3 py-1 text-xs font-semibold border ${
                      s.status === "active"
                        ? "bg-red-50 text-red-700 border-red-200 hover:bg-red-100"
                        : "bg-green-50 text-green-700 border-green-200 hover:bg-green-100"
                    }`}
                  >
                    {s.status === "active" ? "Suspend" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {suppliers.length === 0 && !loading && (
        <p className="text-gray-400 text-center py-8">
          No suppliers registered yet.
        </p>
      )}
    </div>
  );
}