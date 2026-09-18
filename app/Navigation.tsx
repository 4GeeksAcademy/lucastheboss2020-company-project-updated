"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "../src/auth";

export default function Navigation() {
  const pathname = usePathname();
  const router = useRouter();

  if (pathname === "/" || pathname === "/uis/website" || pathname === "/login" || pathname === "/register") {
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
        <Link className="button" href="/candidates/new">
          New candidate
        </Link>
        <Link className="button secondary" href="/account/profile">Profile</Link>
        <button type="button" className="secondary" onClick={() => { clearToken(); router.replace("/login"); }}>Log out</button>
      </nav>
    </header>
  );
}
