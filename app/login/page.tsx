"use client";

import { useAuth } from "../auth/AuthProvider";
import { useEffect, useState } from "react";
import Link from "next/link";

export default function LoginPage() {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [passwordReset, setPasswordReset] = useState(false);

  useEffect(() => {
    setPasswordReset(new URLSearchParams(window.location.search).get("passwordReset") === "success");
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? "Login failed");
      }

      const { access_token } = (await res.json()) as { access_token: string };
      await login(access_token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "An unexpected error occurred");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-xl bg-white p-8 shadow-lg space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 text-center">TrackFlow Login</h1>
        <p className="text-center text-sm text-gray-500">
          Sign in to access TrackFlow protected backoffice views.
        </p>

        {passwordReset && (
          <div className="rounded-md bg-green-50 p-3 text-sm text-green-700" role="status">
            Your password has been reset. Sign in with your new password.
          </div>
        )}

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="-mt-4 text-right">
          <Link href="/forgot-password" className="text-sm font-medium text-blue-700 hover:text-blue-800">
            Forgot your password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={submitting || isLoading}
          className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>

        <p className="text-center text-sm text-gray-600">
          No account yet?{" "}
          <Link href="/register" className="font-semibold text-blue-700 hover:text-blue-800">
            Create one
          </Link>
        </p>
      </form>
    </div>
  );
}