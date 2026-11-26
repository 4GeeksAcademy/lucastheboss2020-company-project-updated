type IconName = "warehouse" | "truck" | "returns" | "arrow" | "check" | "pin" | "mail" | "phone" | "menu" | "close";
const paths: Record<IconName, React.ReactNode> = {
  warehouse: <><path d="m3 9 9-5 9 5v11H3Z" /><path d="M8 20v-8h8v8M8 15h8M8 18h8" /></>,
  truck: <><path d="M3 5h11v12H3ZM14 9h4l3 4v4h-7" /><circle cx="7" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>,
  returns: <><path d="M4 10a8 8 0 1 1 0 5M4 4v6h6" /><path d="m9 13 3-2 3 2v4l-3 2-3-2ZM12 15v4M9 13l3 2 3-2" /></>,
  arrow: <path d="M4 12h15m-6-6 6 6-6 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 6 9 7 9-7" /></>,
  phone: <path d="m8 3-4 1c-3 6 10 19 16 16l1-4-5-2-2 2-6-6 2-2Z" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
};
export default function WebsiteIcon({ name }: { name: IconName }) {
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
export function WebsiteBrand() {
  return <span className="tf-brand"><svg width="29" height="30" viewBox="0 0 29 30" fill="none" aria-hidden="true"><path d="m1 10 7-4v19l-7 4ZM11 4l7-4v26l-7 4ZM21 9l7-4v19l-7 4Z" fill="currentColor" /></svg>TrackFlow<span className="tf-brand-dot">.</span></span>;
}
