"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./auth/AuthProvider";
import type { Route } from "next";

interface NavLink {
  href: Route;
  label: string;
}

const BACKOFFICE_LINKS: NavLink[] = [
  { href: "/uis/backoffice", label: "Dashboard" },
  { href: "/candidates", label: "Candidates" },
  { href: "/uis/backoffice/suppliers", label: "Suppliers" },
  { href: "/uis/backoffice/incidents", label: "Incident Analysis" },
  { href: "/uis/backoffice/incidents/manager", label: "Incident Manager" },
  { href: "/candidates/new", label: "New candidate" },
  { href: "/account/profile", label: "Profile" },
];

export default function Navigation() {
  const pathname = usePathname();
  const { isAuthenticated, logout, user } = useAuth();

  // Hide nav on public website and login page
  if (
    pathname === "/uis/website" ||
    pathname === "/login" ||
    pathname === "/register" ||
    pathname === "/forgot-password" ||
    pathname === "/reset-password"
  ) {
    return null;
  }

  const isBackoffice =
    pathname.startsWith("/candidates") ||
    pathname.startsWith("/uis/backoffice") ||
    pathname.startsWith("/account");

  return (
    <header className="topbar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.75rem 1.5rem", background: "var(--track-blue)", color: "#fff" }}>
      <Link className="brand" href={isBackoffice ? "/candidates" : "/"} style={{ fontWeight: 700, fontSize: "1.125rem", textDecoration: "none", color: "#fff" }}>
        TrackFlow {isBackoffice ? "Backoffice" : "Candidates"}
      </Link>

      <nav className="actions" aria-label="Primary navigation" style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        {isBackoffice && BACKOFFICE_LINKS.map((link) => (
          <Link
            key={link.href}
            className="button secondary"
            href={link.href}
            style={{ background: pathname === link.href ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.08)", color: "#fff", border: "1px solid rgba(255,255,255,0.25)" }}
          >
            {link.label}
          </Link>
        ))}

        {isAuthenticated ? (
          <button onClick={logout} className="button secondary" style={{ background: "rgba(255,255,255,0.08)", color: "#fff", border: "1px solid rgba(255,255,255,0.25)" }}>
            Logout ({user?.email ?? "?"})
          </button>
        ) : (
          <>
            <Link className="button secondary" href="/register" style={{ background: "rgba(255,255,255,0.08)", color: "#fff", border: "1px solid rgba(255,255,255,0.25)" }}>
              Register
            </Link>
            <Link className="button secondary" href="/login" style={{ background: "rgba(255,255,255,0.08)", color: "#fff", border: "1px solid rgba(255,255,255,0.25)" }}>
              Login
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
