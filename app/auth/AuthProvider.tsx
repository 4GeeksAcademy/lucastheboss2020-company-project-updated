"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

interface AuthState {
  token: string | null;
  user: { id: string; email: string; role: string; is_active: boolean } | null;
}

interface AuthContextValue extends AuthState {
  login: (token: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const STORAGE_KEY = "trackflow_token";
const PUBLIC_ROUTES = new Set([
  "/",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/uis/website",
]);

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_ROUTES.has(pathname)) return true;
  if (pathname.startsWith("/uis/website")) return true;
  return false;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ token: null, user: null });
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const fetchUser = useCallback(async (token: string) => {
    try {
      const res = await fetch("http://localhost:8000/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      return (await res.json()) as { id: string; email: string; role: string; is_active: boolean };
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem(STORAGE_KEY);
    if (token) {
      fetchUser(token).then((user) => {
        if (user) {
          setState({ token, user });
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
        setIsLoading(false);
      });
      return;
    }
    setIsLoading(false);
  }, [fetchUser]);

  useEffect(() => {
    if (isLoading) return;

    const isPublic = isPublicPath(pathname);

    if (!state.token && !isPublic) {
      router.replace("/login");
      return;
    }

    if (state.token && (pathname === "/login" || pathname === "/register")) {
      router.replace("/uis/backoffice");
    }
  }, [isLoading, pathname, router, state.token]);

  const login = useCallback(
    async (token: string) => {
      localStorage.setItem(STORAGE_KEY, token);
      const user = await fetchUser(token);
      if (user) {
        setState({ token, user });
        router.push("/uis/backoffice");
      } else {
        localStorage.removeItem(STORAGE_KEY);
        throw new Error("Invalid session token");
      }
    },
    [fetchUser, router],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setState({ token: null, user: null });
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAuthenticated: !!state.token, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}