"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navigation() {
  const pathname = usePathname();

  if (pathname === "/uis/website") {
    return null;
  }

  // Backoffice navigation
  if (pathname.startsWith("/uis/backoffice")) {
    return (
      <header className="topbar">
        <Link className="brand" href="/uis/backoffice">
          TrackFlow Backoffice
        </Link>
        <nav className="actions" aria-label="Primary navigation">
          <Link 
            className={`button ${pathname === "/uis/backoffice" ? "" : "secondary"}`}
            href="/uis/backoffice"
          >
            Candidates
          </Link>
          <Link 
            className={`button ${pathname.startsWith("/uis/backoffice/incidents") ? "" : "secondary"}`}
            href="/uis/backoffice/incidents"
          >
            Incident Analysis
          </Link>
          <Link className="button" href="/candidates/new">
            New candidate
          </Link>
        </nav>
      </header>
    );
  }

  // Default candidates navigation
  return (
    <header className="topbar">
      <Link className="brand" href="/candidates">
        TrackFlow Candidates
      </Link>
      <nav className="actions" aria-label="Primary navigation">
        <Link className="button secondary" href="/candidates">
          Pipeline
        </Link>
        <Link className="button" href="/candidates/new">
          New candidate
        </Link>
      </nav>
    </header>
  );
}
