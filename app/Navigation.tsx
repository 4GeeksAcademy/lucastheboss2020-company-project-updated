"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "./auth/AuthProvider";
import BackofficeNavigation from "../uis/backoffice/BackofficeNavigation";

export default function Navigation() {
  const pathname = usePathname();
  const { isAuthenticated, user, logout } = useAuth();
  const isWorkspace = pathname.startsWith("/uis/backoffice") || pathname.startsWith("/candidates") || pathname.startsWith("/account");
  if (!isWorkspace || !isAuthenticated) return null;
  return <BackofficeNavigation pathname={pathname} user={user} onLogout={logout} />;
}
