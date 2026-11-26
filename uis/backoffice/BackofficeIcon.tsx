import type { ReactNode } from "react";
export type BackofficeIconName = "overview" | "leads" | "rfp" | "inventory" | "suppliers" | "incidents" | "reports" | "telemetry" | "assistant" | "profile" | "arrow" | "chevron" | "menu" | "close" | "logout" | "plus";
const paths: Record<BackofficeIconName, ReactNode> = {
  overview: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  leads: <><circle cx="9" cy="8" r="3" /><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 5v2" /></>,
  rfp: <><path d="M5 3h9l5 5v13H5ZM14 3v6h5M8 13h8M8 17h5" /></>,
  inventory: <><path d="m3 8 9-5 9 5v9l-9 5-9-5ZM3 8l9 5 9-5M12 13v9M7 5l10 5" /></>,
  suppliers: <><path d="M3 21V7l8-4v18M11 9h10v12M7 8v1M7 13v1M7 18v1M15 13v1M18 13v1M15 18v1M18 18v1M2 21h20" /></>,
  incidents: <><path d="m12 3 10 18H2Z" /><path d="M12 9v5M12 17v.2" /></>,
  reports: <><path d="M4 3v18h17M9 17v-5M14 17V7M19 17v-8" /></>,
  telemetry: <><path d="M2 12h5l3-8 4 16 3-8h5" /></>,
  assistant: <><path d="M21 11a9 9 0 0 1-9 9H4l-2 2V11a9 9 0 0 1 18 0ZM7 11h.1M12 11h.1M17 11h.1" /></>,
  profile: <><circle cx="12" cy="8" r="4" /><path d="M4 22v-3a8 8 0 0 1 16 0v3" /></>,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  chevron: <path d="m7 10 5 5 5-5" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  logout: <><path d="M10 4H4v16h6M8 12h13m-4-4 4 4-4 4" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
};
export default function BackofficeIcon({ name }: { name: BackofficeIconName }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
