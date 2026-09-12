"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navigation() {
  const pathname = usePathname();

  if (pathname === "/uis/website") {
    return null;
  }

  return (
    <header className="topbar">
      <Link className="brand" href="/candidates">
        TrackFlow Candidates
      </Link>
      <nav className="actions" aria-label="Primary navigation">
        <Link className="button secondary" href="/candidates">
          Pipeline
        </Link>
        <Link className="button secondary" href="/uis/backoffice/suppliers">
          Suppliers
        </Link>
        <Link className="button" href="/candidates/new">
          New candidate
        </Link>
      </nav>
    </header>
  );
}
