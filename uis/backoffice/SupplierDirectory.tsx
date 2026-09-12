"use client";

import { FormEvent, useEffect, useState } from "react";

type Supplier = { id: number; name: string; country: string; product_categories: string[]; rate: number; status: "active" | "suspended"; updated_at: string };
const API = process.env.NEXT_PUBLIC_SUPPLIER_API_URL ?? "http://localhost:8000";

export default function SupplierDirectory() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [country, setCountry] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ name: "", country: "United States", product_categories: "", rate: "", status: "active" });

  async function load() {
    const params = new URLSearchParams();
    if (country) params.set("country", country);
    if (category) params.set("category", category);
    const response = await fetch(`${API}/suppliers?${params}`);
    if (!response.ok) throw new Error("Unable to load suppliers");
    setSuppliers(await response.json());
  }
  useEffect(() => { load().catch((e: Error) => setError(e.message)); }, [country, category]);

  async function create(event: FormEvent) {
    event.preventDefault(); setError("");
    const response = await fetch(`${API}/suppliers`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, rate: Number(form.rate), product_categories: form.product_categories.split(",").map((value) => value.trim()).filter(Boolean) }) });
    if (!response.ok) { const body = await response.json().catch(() => null); setError(body?.detail?.[0]?.msg ?? body?.detail ?? "Supplier could not be created"); return; }
    setForm({ name: "", country: "United States", product_categories: "", rate: "", status: "active" }); load().catch((e: Error) => setError(e.message));
  }

  async function update(id: number, path: string, body: object) {
    const response = await fetch(`${API}/suppliers/${id}/${path}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!response.ok) { setError("Supplier update failed"); return; }
    load().catch((e: Error) => setError(e.message));
  }

  return <section>
    <header className="page-header"><span className="badge green">Procurement operations</span><h1>Supplier directory</h1><p>Manage supplier rates, categories, and operational status in one shared directory.</p></header>
    <section className="panel" aria-label="Supplier filters"><div className="filters"><label className="field"><span>Country</span><select value={country} onChange={(e) => setCountry(e.target.value)}><option value="">All countries</option><option>United States</option><option>Spain</option></select></label><label className="field"><span>Product category</span><input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Packaging" /></label></div></section>
    {error && <p className="message error" role="alert">{error}</p>}
    <form className="panel form-grid" onSubmit={create} aria-label="Register supplier"><h2>Register supplier</h2><label className="field"><span>Name</span><input required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><label className="field"><span>Country</span><select value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })}><option>United States</option><option>Spain</option></select></label><label className="field"><span>Product categories <small>(comma separated)</small></span><input required value={form.product_categories} onChange={(e) => setForm({ ...form, product_categories: e.target.value })} /></label><label className="field"><span>Rate</span><input required min="0.01" step="0.01" type="number" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} /></label><button type="submit">Add supplier</button></form>
    <div className="supplier-table-wrap"><table className="supplier-table"><thead><tr><th>Name</th><th>Country</th><th>Categories</th><th>Rate</th><th>Status</th><th>Actions</th></tr></thead><tbody>{suppliers.map((supplier) => <tr className={supplier.status === "suspended" ? "suspended-row" : ""} key={supplier.id}><td><strong>{supplier.name}</strong></td><td>{supplier.country}</td><td>{supplier.product_categories.join(", ")}</td><td><label className="sr-only" htmlFor={`rate-${supplier.id}`}>Rate for {supplier.name}</label><input id={`rate-${supplier.id}`} className="compact-input" type="number" min="0.01" step="0.01" defaultValue={supplier.rate} onBlur={(e) => update(supplier.id, "rate", { rate: Number(e.target.value) })} /></td><td><span className={`badge ${supplier.status === "active" ? "green" : "suspended"}`}>{supplier.status}</span></td><td><button className="secondary compact-button" onClick={() => update(supplier.id, "status", { status: supplier.status === "active" ? "suspended" : "active" })}>{supplier.status === "active" ? "Suspend" : "Activate"}</button></td></tr>)}</tbody></table></div>
  </section>;
}
