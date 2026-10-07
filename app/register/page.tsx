"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { ApiRequestError, fetchJson, userSafeErrorMessage } from "../../src/utils/api-errors";

interface RegisterErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
  name?: string;
  phone?: string;
  address?: string;
  form?: string;
}

export default function RegisterPage() {
  const { login, isLoading } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [errors, setErrors] = useState<RegisterErrors>({});
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const nextErrors: RegisterErrors = {};

    if (!email.trim()) nextErrors.email = "Email is required";
    if (!password) nextErrors.password = "Password is required";
    if (password.length > 0 && password.length < 8) {
      nextErrors.password = "Password must be at least 8 characters";
    }
    if (password !== confirmPassword) {
      nextErrors.confirmPassword = "Passwords do not match";
    }

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }

    setSubmitting(true);
    setErrors({});

    try {
      await fetchJson("http://localhost:8000/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password,
          name: name.trim() || null,
          phone: phone.trim() || null,
          address: address.trim() || null,
        }),
      });

      const { access_token } = await fetchJson<{ access_token: string }>("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      await login(access_token);
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 422 && error.field && error.field in errors) {
        setErrors({ [error.field]: error.message });
        return;
      }
      setErrors((prev) => ({
        ...prev,
        form: userSafeErrorMessage(error, "Could not create the account. Check your connection and try again."),
      }));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 py-10">
      <form onSubmit={handleSubmit} className="w-full max-w-lg rounded-xl bg-white p-8 shadow-lg space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 text-center">Create TrackFlow Account</h1>
        <p className="text-center text-sm text-gray-500">Register and continue to protected backoffice views.</p>

        {errors.form && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{errors.form}</div>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label htmlFor="email" className="mb-1 block text-sm font-medium text-gray-700">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              required
            />
            {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email}</p>}
          </div>

          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              required
            />
            {errors.password && <p className="mt-1 text-xs text-red-600">{errors.password}</p>}
          </div>

          <div>
            <label htmlFor="confirmPassword" className="mb-1 block text-sm font-medium text-gray-700">Confirm password</label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              required
            />
            {errors.confirmPassword && <p className="mt-1 text-xs text-red-600">{errors.confirmPassword}</p>}
          </div>

          <div>
            <label htmlFor="name" className="mb-1 block text-sm font-medium text-gray-700">Name (optional)</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
            {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name}</p>}
          </div>

          <div>
            <label htmlFor="phone" className="mb-1 block text-sm font-medium text-gray-700">Phone (optional)</label>
            <input
              id="phone"
              type="text"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
            {errors.phone && <p className="mt-1 text-xs text-red-600">{errors.phone}</p>}
          </div>

          <div className="md:col-span-2">
            <label htmlFor="address" className="mb-1 block text-sm font-medium text-gray-700">Address (optional)</label>
            <input
              id="address"
              type="text"
              value={address}
              onChange={(event) => setAddress(event.target.value)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
            {errors.address && <p className="mt-1 text-xs text-red-600">{errors.address}</p>}
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting || isLoading}
          className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Creating account…" : "Register"}
        </button>

        <p className="text-center text-sm text-gray-600">
          Already have an account? <Link href="/login" className="font-semibold text-blue-700 hover:text-blue-800">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
