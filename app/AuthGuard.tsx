"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getToken } from "../src/auth";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  useEffect(() => { if (!getToken()) router.replace(`/login?next=${encodeURIComponent(pathname)}`); else setReady(true); }, [pathname, router]);
  if (!ready) return <p className="message loading">Checking authentication...</p>;
  return <>{children}</>;
}
