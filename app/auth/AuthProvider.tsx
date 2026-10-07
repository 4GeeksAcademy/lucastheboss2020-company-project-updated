"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ApiRequestError, fetchJson } from "../../src/utils/api-errors";

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

type SessionCheck =
  | { kind: "valid"; user: AuthState["user"] }
  | { kind: "invalid" }
  | { kind: "unavailable" };

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_ROUTES.has(pathname)) return true;
  if (pathname.startsWith("/uis/website")) return true;
  return false;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ token: null, user: null });
  const [isLoading, setIsLoading] = useState(true);
  const [sessionUnavailable, setSessionUnavailable] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  const fetchUser = useCallback(async (token: string) => {
    try {
      const user = await fetchJson<NonNullable<AuthState["user"]>>("http://localhost:8000/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      return { kind: "valid", user } satisfies SessionCheck;
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 401) {
        return { kind: "invalid" } satisfies SessionCheck;
      }
      return { kind: "unavailable" } satisfies SessionCheck;
    }
  }, []);

  const checkStoredSession = useCallback(async () => {
    setIsLoading(true);
    setSessionUnavailable(false);
    const token = localStorage.getItem(STORAGE_KEY);
    if (!token) {
      setState({ token: null, user: null });
      setIsLoading(false);
      return;
    }

    const result = await fetchUser(token);
    if (result.kind === "valid") {
      setState({ token, user: result.user });
    } else if (result.kind === "invalid") {
      localStorage.removeItem(STORAGE_KEY);
      setState({ token: null, user: null });
    } else {
      setState({ token: null, user: null });
      setSessionUnavailable(true);
    }
    setIsLoading(false);
  }, [fetchUser]);

  useEffect(() => {
    void checkStoredSession();
  }, [checkStoredSession]);

  useEffect(() => {
    if (isLoading || sessionUnavailable) return;

    const isPublic = isPublicPath(pathname);

    if (!state.token && !isPublic) {
      router.replace("/login");
      return;
    }

    if (state.token && (pathname === "/login" || pathname === "/register")) {
      router.replace("/uis/backoffice");
    }
  }, [isLoading, pathname, router, sessionUnavailable, state.token]);

  const login = useCallback(
    async (token: string) => {
      localStorage.setItem(STORAGE_KEY, token);
      const result = await fetchUser(token);
      if (result.kind === "valid") {
        setSessionUnavailable(false);
        setState({ token, user: result.user });
        router.push("/uis/backoffice");
      } else if (result.kind === "unavailable") {
        setSessionUnavailable(true);
        setState({ token: null, user: null });
        throw new ApiRequestError("Could not verify your session. Check your connection and retry.");
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
    setSessionUnavailable(false);
    router.push("/login");
  }, [router]);

  if (sessionUnavailable && !isPublicPath(pathname)) {
    return (
      <main className="shell">
        <div className="message error" role="alert">
          <p>TrackFlow could not verify your session because the service is unavailable. Your saved session was kept.</p>
          <div className="actions">
            <button type="button" onClick={() => void checkStoredSession()}>Retry</button>
            <button type="button" className="secondary" onClick={logout}>Return to sign in</button>
          </div>
        </div>
      </main>
    );
  }

  if (isLoading && !isPublicPath(pathname)) {
    return <main className="shell"><p className="message loading" role="status">Verifying TrackFlow session...</p></main>;
  }

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