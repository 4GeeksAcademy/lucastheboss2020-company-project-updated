"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiUrl, readJson, setToken } from "../../src/auth";

const fields = ["name", "phone", "address"] as const;
type ProfileField = typeof fields[number];

export default function RegisterPage() {
  const router = useRouter();
  const [values, setValues] = useState<Record<"email" | "password" | ProfileField, string>>({ email: "", password: "", name: "", phone: "", address: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  function update(key: keyof typeof values, value: string) { setValues((current) => ({ ...current, [key]: value })); setErrors((current) => ({ ...current, [key]: "" })); }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};
    if (!values.email.includes("@")) nextErrors.email = "Enter a valid email address.";
    if (values.password.length < 8) nextErrors.password = "Password must be at least 8 characters.";
    if (Object.keys(nextErrors).length) { setErrors(nextErrors); return; }
    setLoading(true); setErrors({});
    try {
      const profile = Object.fromEntries(fields.filter((field) => values[field]).map((field) => [field, values[field]]));
      await readJson(await fetch(apiUrl("/users"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: values.email, password: values.password, ...profile }) }));
      const response = await fetch(apiUrl("/auth/login"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: values.email, password: values.password }) });
      const payload = await readJson<{ token?: string; access_token?: string }>(response);
      const token = payload.token ?? payload.access_token;
      if (!token) throw new Error("Registration succeeded but no access token was returned.");
      setToken(token); router.replace("/candidates");
    } catch (registrationError) {
      const message = registrationError instanceof Error ? registrationError.message : "Unable to register.";
      setErrors({ form: message });
    } finally { setLoading(false); }
  }

  return <section className="auth-card panel">
    <header className="page-header"><h1>Create account</h1><p>Register to manage TrackFlow leads.</p></header>
    {errors.form && <p className="message error" role="alert">{errors.form}</p>}
    <form className="form-grid" onSubmit={handleSubmit}>
      <label className="field"><span>Email</span><input type="email" value={values.email} onChange={(event) => update("email", event.target.value)} required />{errors.email && <small className="error-text">{errors.email}</small>}</label>
      <label className="field"><span>Password</span><input type="password" value={values.password} onChange={(event) => update("password", event.target.value)} required />{errors.password && <small className="error-text">{errors.password}</small>}</label>
      {fields.map((field) => <label className="field" key={field}><span>{field[0].toUpperCase() + field.slice(1)} (optional)</span><input value={values[field]} onChange={(event) => update(field, event.target.value)} /></label>)}
      <button disabled={loading} type="submit">{loading ? "Creating account..." : "Create account"}</button>
    </form>
    <p>Already registered? <Link href="/login">Sign in</Link></p>
  </section>;
}
