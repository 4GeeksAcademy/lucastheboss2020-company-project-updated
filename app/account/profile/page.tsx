"use client";

import { FormEvent, useEffect, useState } from "react";
import { authenticatedFetch, normalizeAuthUser, readJson, type AuthUser } from "../../../src/auth";

export default function ProfilePage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [values, setValues] = useState({ name: "", phone: "", address: "" });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => { authenticatedFetch("/auth/me").then((response) => readJson<AuthUser>(response)).then((data) => { const normalized = normalizeAuthUser(data); setUser(normalized); setValues({ name: normalized.name ?? "", phone: normalized.phone ?? "", address: normalized.address ?? "" }); }).catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Unable to load profile.")).finally(() => setLoading(false)); }, []);
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setError(""); setSuccess(""); try { const response = await authenticatedFetch("/profiles/me", { method: "PUT", body: JSON.stringify(values) }); const data = await readJson<AuthUser>(response); const normalized = normalizeAuthUser(data); setUser((current) => ({ ...current, ...normalized } as AuthUser)); setSuccess("Profile updated."); } catch (saveError) { setError(saveError instanceof Error ? saveError.message : "Unable to update profile."); } }
  if (loading) return <p className="message loading">Loading profile...</p>;
  return <section className="auth-card panel"><header className="page-header"><h1>Account profile</h1><p>Signed in as <strong>{user?.email}</strong></p></header>{error && <p className="message error" role="alert">{error}</p>}{success && <p className="message success">{success}</p>}<form className="form-grid" onSubmit={save}>{(["name", "phone", "address"] as const).map((field) => <label className="field" key={field}><span>{field[0].toUpperCase() + field.slice(1)}</span><input value={values[field]} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))} /></label>)}<button type="submit">Save profile</button></form></section>;
}
