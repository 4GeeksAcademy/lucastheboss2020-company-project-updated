export const TRACKFLOW_TOKEN_KEY = "trackflow_token";

export function trackFlowAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem(TRACKFLOW_TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}