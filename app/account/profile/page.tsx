"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "../../auth/AuthProvider";
import { ApiRequestError, fetchJson, userSafeErrorMessage } from "../../../src/utils/api-errors";

interface ProfileData {
  name: string;
  phone: string;
  address: string;
}

interface MeResponse {
  email: string;
  profile?: {
    name?: string | null;
    phone?: string | null;
    address?: string | null;
  } | null;
}

const STORAGE_KEY = "trackflow_token";

export default function AccountProfilePage() {
  const { isLoading, logout } = useAuth();
  const [email, setEmail] = useState("");
  const [profile, setProfile] = useState<ProfileData>({ name: "", phone: "", address: "" });
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    if (isLoading) return;

    const token = localStorage.getItem(STORAGE_KEY);
    if (!token) {
      setLoadingProfile(false);
      return;
    }

    setLoadingProfile(true);
    setError(null);

    fetchJson<MeResponse>("/api/backend/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((data) => {
        setEmail(data.email);
        setProfile({
          name: data.profile?.name ?? "",
          phone: data.profile?.phone ?? "",
          address: data.profile?.address ?? "",
        });
      })
      .catch((fetchError: unknown) => {
        if (fetchError instanceof ApiRequestError && fetchError.status === 401) logout();
        setError(userSafeErrorMessage(fetchError, "Could not load your profile. Please retry."));
      })
      .finally(() => setLoadingProfile(false));
  }, [isLoading, logout, retryVersion]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();

    const token = localStorage.getItem(STORAGE_KEY);
    if (!token) {
      setError("No active session found.");
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await fetchJson("/api/backend/profiles/me", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: profile.name.trim() || null,
          phone: profile.phone.trim() || null,
          address: profile.address.trim() || null,
        }),
      });

      setSuccess("Profile updated successfully.");
    } catch (saveError) {
      if (saveError instanceof ApiRequestError && saveError.status === 401) {
        logout();
        return;
      }
      setError(userSafeErrorMessage(saveError, "Profile update failed. Please retry."));
    } finally {
      setSaving(false);
    }
  }

  if (isLoading || loadingProfile) {
    return <p className="message loading">Loading account profile...</p>;
  }

  return (
    <section className="space-y-4">
      <header className="page-header">
        <span className="badge green">Account</span>
        <h1>Profile</h1>
        <p>Manage your user details used by TrackFlow backoffice operations.</p>
        <Link href="/account/change-password" className="button secondary">
          Change password
        </Link>
      </header>

      {error && (
        <div className="message error" role="alert">
          <p>{error}</p>
          <button type="button" className="secondary" onClick={() => setRetryVersion((version) => version + 1)}>Retry</button>
        </div>
      )}
      {success && <p className="message" role="status">{success}</p>}

      <form onSubmit={handleSave} className="panel space-y-4 max-w-2xl">
        <label className="field">
          <span>Email</span>
          <input value={email} disabled readOnly className="bg-gray-100" />
        </label>

        <label className="field">
          <span>Name</span>
          <input
            value={profile.name}
            onChange={(event) => setProfile((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="Your full name"
          />
        </label>

        <label className="field">
          <span>Phone</span>
          <input
            value={profile.phone}
            onChange={(event) => setProfile((prev) => ({ ...prev, phone: event.target.value }))}
            placeholder="+1 213 555 0147"
          />
        </label>

        <label className="field">
          <span>Address</span>
          <input
            value={profile.address}
            onChange={(event) => setProfile((prev) => ({ ...prev, address: event.target.value }))}
            placeholder="Los Angeles or Zaragoza office"
          />
        </label>

        <div className="actions">
          <button type="submit" className="button" disabled={saving}>
            {saving ? "Saving..." : "Save profile"}
          </button>
        </div>
      </form>
    </section>
  );
}
