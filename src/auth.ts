export const AUTH_TOKEN_KEY = "trackflow_access_token";

export interface AuthUser {
  email: string;
  name?: string;
  phone?: string;
  address?: string;
  [key: string]: unknown;
}

interface AuthUserPayload {
  email?: string;
  name?: string;
  phone?: string;
  address?: string;
  user?: Partial<AuthUser>;
  profile?: Partial<AuthUser>;
}

export function normalizeAuthUser(payload: AuthUserPayload): AuthUser {
  return {
    ...(payload.user ?? {}),
    ...(payload.profile ?? {}),
    ...(payload.email ? { email: payload.email } : {}),
    ...(payload.name ? { name: payload.name } : {}),
    ...(payload.phone ? { phone: payload.phone } : {}),
    ...(payload.address ? { address: payload.address } : {}),
  } as AuthUser;
}

export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window !== "undefined") window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function apiUrl(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}

export async function authenticatedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(apiUrl(path), { ...init, headers });
  if (response.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    }
  }
  return response;
}

export async function readJson<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T & { error?: string; message?: string };
  if (!response.ok) throw new Error(payload.error ?? payload.message ?? "The request failed.");
  return payload as T;
}
