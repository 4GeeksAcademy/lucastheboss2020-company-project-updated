"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "../auth/AuthProvider";

interface RegisterErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
  name?: string;
  phone?: string;
  address?: string;
  form?: string;
}

interface FastApiValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

function mapValidationErrors(detail: unknown): RegisterErrors {
  if (!Array.isArray(detail)) {
    return {};
  }

  const errors: RegisterErrors = {};
  for (const item of detail as FastApiValidationError[]) {
    const field = String(item.loc[item.loc.length - 1] ?? "");
    if (field in errors) continue;

    if (field === "email") errors.email = item.msg;
    else if (field === "password") errors.password = item.msg;
    else if (field === "name") errors.name = item.msg;
    else if (field === "phone") errors.phone = item.msg;
    else if (field === "address") errors.address = item.msg;
  }

  return errors;
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
      const registerResponse = await fetch("http://localhost:8000/users", {
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

      if (!registerResponse.ok) {
        const body = await registerResponse.json().catch(() => ({}));
        if (registerResponse.status === 422) {
          const fieldErrors = mapValidationErrors((body as { detail?: unknown }).detail);
          setErrors(fieldErrors);
          return;
        }

        const detail = (body as { detail?: string }).detail;
        throw new Error(detail ?? "Registration failed");
      }

      const loginResponse = await fetch("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!loginResponse.ok) {
        const body = await loginResponse.json().catch(() => ({}));
        const detail = (body as { detail?: string }).detail;
        throw new Error(detail ?? "Login after registration failed");
      }

      const { access_token } = (await loginResponse.json()) as { access_token: string };
      await login(access_token);
    } catch (error) {
      setErrors((prev) => ({
        ...prev,
        form: error instanceof Error ? error.message : "Unexpected registration error",
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
