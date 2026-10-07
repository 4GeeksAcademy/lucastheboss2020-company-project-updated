"use client";

import Link from "next/link";
import { useState } from "react";
import { fetchJson, userSafeErrorMessage } from "../../src/utils/api-errors";

const API_BASE = "http://localhost:8000";
const CONFIRMATION = "If that address is registered, you'll receive a reset link shortly.";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (submitting || submitted) return;

    setSubmitting(true);
    setError("");
    try {
      await fetchJson(`${API_BASE}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      setSubmitted(true);
    } catch (requestError) {
      setError(userSafeErrorMessage(requestError, "We could not send the request. Check your connection and retry."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-10">
      <form onSubmit={handleSubmit} className="w-full max-w-md space-y-6 rounded-xl bg-white p-8 shadow-lg">
        <div>
          <h1 className="text-center text-2xl font-bold text-gray-900">Reset your password</h1>
          <p className="mt-2 text-center text-sm text-gray-600">
            Enter your account email and we’ll send a short-lived reset link if it matches an account.
          </p>
        </div>

        {submitted ? (
          <div className="rounded-md bg-blue-50 p-4 text-sm text-blue-800" role="status">
            {CONFIRMATION}
          </div>
        ) : (
          <>
            {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">{error}</div>}
            <label className="block text-sm font-medium text-gray-700" htmlFor="email">
              Email address
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
            </label>
            <button
              type="submit"
              disabled={submitting || submitted}
              className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? "Sending…" : "Send reset link"}
            </button>
          </>
        )}

        <p className="text-center text-sm text-gray-600">
          <Link href="/login" className="font-semibold text-blue-700 hover:text-blue-800">Back to login</Link>
        </p>
      </form>
    </div>
  );
}