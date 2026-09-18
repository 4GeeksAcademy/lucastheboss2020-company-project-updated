"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { apiUrl, readJson, setToken } from "../../src/auth";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const response = await fetch(apiUrl("/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const payload = await readJson<{ token?: string; access_token?: string }>(response);
      const token = payload.token ?? payload.access_token;
      if (!token) throw new Error("Login succeeded but no access token was returned.");
      setToken(token);
      router.replace(searchParams.get("next") || "/candidates");
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Unable to sign in.");
    } finally {
      setLoading(false);
    }
  }

  return <section className="auth-card panel">
    <header className="page-header"><h1>Sign in</h1><p>Access the TrackFlow candidate pipeline.</p></header>
    {error && <p className="message error" role="alert">{error}</p>}
    <form className="form-grid" onSubmit={handleSubmit}>
      <label className="field"><span>Email</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" /></label>
      <label className="field"><span>Password</span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" /></label>
      <button disabled={loading} type="submit">{loading ? "Signing in..." : "Sign in"}</button>
    </form>
    <p>Need an account? <Link href="/register">Register</Link></p>
  </section>;
}

export default function LoginPage() {
  return <Suspense fallback={<p className="message loading">Loading sign in...</p>}><LoginForm /></Suspense>;
}
