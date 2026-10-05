"use client";

import { useState } from "react";

const API_BASE = "http://localhost:8000";
const STORAGE_KEY = "trackflow_token";

export default function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }

    const token = localStorage.getItem(STORAGE_KEY);
    if (!token) {
      setError("Your session has expired. Please log in again.");
      window.location.href = "/login";
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/auth/change-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (response.status === 401) {
        localStorage.removeItem(STORAGE_KEY);
        window.location.href = "/login";
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = (body as { detail?: string }).detail;
        throw new Error(detail ?? "Password change failed.");
      }

      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess("Password changed successfully.");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Password change failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-4">
      <header className="page-header">
        <span className="badge green">Account security</span>
        <h1>Change password</h1>
      </header>

      {error && <p className="message error" role="alert">{error}</p>}
      {success && <p className="message" role="status">{success}</p>}

      <form onSubmit={handleSubmit} className="panel max-w-2xl space-y-4">
        <label className="field" htmlFor="current-password">
          <span>Current password</span>
          <input
            id="current-password"
            type="password"
            autoComplete="current-password"
            required
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
        </label>

        <label className="field" htmlFor="new-password">
          <span>New password</span>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
          />
        </label>

        <label className="field" htmlFor="confirm-password">
          <span>Confirm new password</span>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
          />
        </label>

        <button type="submit" className="button" disabled={submitting}>
          {submitting ? "Saving…" : "Change password"}
        </button>
      </form>
    </section>
  );
}