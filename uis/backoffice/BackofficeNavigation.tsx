"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import BackofficeIcon from "./BackofficeIcon";
import type { BackofficeIconName } from "./BackofficeIcon";

type Item = { label: string; href: string; icon: BackofficeIconName; exact?: boolean; children?: { label: string; href: string; exact?: boolean }[] };
export const BACKOFFICE_GROUPS: { label: string; items: Item[] }[] = [
  { label: "Workspace", items: [
    { label: "Overview", href: "/uis/backoffice", icon: "overview", exact: true },
    { label: "Leads", href: "/candidates", icon: "leads" },
    { label: "RFP proposals", href: "/uis/backoffice/rfp", icon: "rfp" },
  ] },
  { label: "Operations", items: [
    { label: "Inventory", href: "/uis/backoffice/inventory", icon: "inventory", children: [
      { label: "Products", href: "/uis/backoffice/inventory/products" },
      { label: "Orders", href: "/uis/backoffice/inventory/orders", exact: true },
      { label: "Inbound orders", href: "/uis/backoffice/inventory/orders/inbound" },
      { label: "Outbound orders", href: "/uis/backoffice/inventory/orders/outbound" },
    ] },
    { label: "Suppliers", href: "/uis/backoffice/suppliers", icon: "suppliers" },
    { label: "Incidents", href: "/uis/backoffice/incidents", icon: "incidents", children: [
      { label: "Manage incidents", href: "/uis/backoffice/incidents/manager" },
      { label: "Analyze a CSV", href: "/uis/backoffice/incidents", exact: true },
    ] },
  ] },
  { label: "Insights", items: [
    { label: "Weekly reporting", href: "/uis/backoffice/reporting", icon: "reports" },
    { label: "Telemetry", href: "/uis/backoffice/telemetry", icon: "telemetry" },
  ] },
  { label: "Tools", items: [{ label: "Knowledge Assistant", href: "/uis/backoffice/knowledge", icon: "assistant" }] },
];

function matches(path: string, href: string, exact = false) { return path === href || (!exact && path.startsWith(href + "/")); }
export function backofficePage(pathname: string) {
  if (pathname === "/candidates/new") return { group: "Workspace", title: "New lead" };
  if (pathname.startsWith("/candidates/")) return { group: "Workspace", title: "Lead details" };
  if (pathname.startsWith("/account")) return { group: "Account", title: pathname.includes("change-password") ? "Change password" : "Your profile" };
  for (const group of BACKOFFICE_GROUPS) for (const item of group.items) {
    const child = item.children?.find(child => matches(pathname, child.href, child.exact));
    if (child) return { group: item.label, title: child.label };
    if (matches(pathname, item.href, item.exact)) return { group: group.label, title: item.label };
  }
  return { group: "Workspace", title: "Overview" };
}

export default function BackofficeNavigation({ pathname, user, onLogout, onNavigate }: {
  pathname: string; user: { email: string; role: string } | null; onLogout: () => void; onNavigate?: (href: string) => void;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [expanded, setExpanded] = useState<string[]>([]);
  const sidebar = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const accountButton = useRef<HTMLButtonElement>(null);
  const accountWrapper = useRef<HTMLDivElement>(null);
  const topbar = useRef<HTMLElement>(null);
  const current = backofficePage(pathname);
  const preview = Boolean(onNavigate);
  const websiteHref = `${process.env.NEXT_PUBLIC_WEBSITE_URL?.replace(/\/+$/, "") ?? ""}/uis/website`;
  const showAddLead = pathname === "/uis/backoffice" || pathname === "/candidates";

  useEffect(() => {
    setMobileOpen(false); setAccountOpen(false);
    const activeParents = BACKOFFICE_GROUPS.flatMap(group => group.items).filter(item => item.children && matches(pathname, item.href)).map(item => item.href);
    setExpanded(previous => Array.from(new Set([...previous, ...activeParents])));
  }, [pathname]);

  useEffect(() => {
    const breakpoint = window.matchMedia("(min-width: 901px)");
    const resize = () => { if (breakpoint.matches) setMobileOpen(false); };
    breakpoint.addEventListener("change", resize);
    return () => breakpoint.removeEventListener("change", resize);
  }, []);

  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (mobileOpen) { setMobileOpen(false); requestAnimationFrame(() => menuButton.current?.focus()); }
        if (accountOpen) { setAccountOpen(false); accountButton.current?.focus(); }
      }
    };
    const outside = (event: PointerEvent) => {
      if (event.target instanceof Node && !accountWrapper.current?.contains(event.target)) setAccountOpen(false);
    };
    document.addEventListener("keydown", close);
    document.addEventListener("pointerdown", outside);
    return () => { document.removeEventListener("keydown", close); document.removeEventListener("pointerdown", outside); };
  }, [mobileOpen, accountOpen]);

  useEffect(() => {
    if (!mobileOpen) return;
    const content = document.getElementById(preview ? "bo-preview-content" : "bo-main-content");
    // The main element is supplied by the existing layout, not the navigation.
    const main = content ?? document.querySelector<HTMLElement>(".bo-navigation + main.shell");
    const previousOverflow = document.body.style.overflow;
    const previousMainInert = main?.inert ?? false;
    const previousTopbarInert = topbar.current?.inert ?? false;
    if (main) main.inert = true;
    if (topbar.current) topbar.current.inert = true;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(sidebar.current?.querySelectorAll<HTMLElement>("a[href],button:not([disabled]),summary") ?? []).filter(element => element.getClientRects().length > 0);
    focusable()[0]?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const elements = focusable(); const first = elements[0]; const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", trap);
    const bar = topbar.current;
    return () => {
      document.body.style.overflow = previousOverflow;
      if (main) main.inert = previousMainInert;
      if (bar) bar.inert = previousTopbarInert;
      document.removeEventListener("keydown", trap);
    };
  }, [mobileOpen, preview]);

  function navigate(event: MouseEvent<HTMLAnchorElement>, href: string) {
    if (onNavigate && !event.metaKey && !event.ctrlKey && !event.shiftKey && event.button === 0) { event.preventDefault(); onNavigate(href); }
    setMobileOpen(false); setAccountOpen(false);
  }
  function closeMobile() { setMobileOpen(false); requestAnimationFrame(() => menuButton.current?.focus()); }
  const link = (href: string, label: string, active = false, icon?: BackofficeIconName, extraClass = "") => <Link key={href} href={href} className={`bo-link ${active ? "bo-link-active " : ""}${extraClass}`} aria-current={active ? "page" : undefined} onClick={event => navigate(event, href)}>{icon && <BackofficeIcon name={icon} />}<span>{label}</span>{active && <span className="bo-active-dot" />}</Link>;

  return <div className={`bo-navigation${mobileOpen ? " bo-navigation-open" : ""}`}>
    <a className="bo-skip-link" href={preview ? "#bo-preview-content" : "#bo-main-content"} onClick={() => {
      const main = document.querySelector<HTMLElement>(".bo-navigation + main.shell");
      if (main && !preview) { main.id = "bo-main-content"; main.tabIndex = -1; main.focus(); }
    }}>Skip to workspace</a>
    {mobileOpen && <button type="button" className="bo-overlay" aria-label="Close navigation" onClick={closeMobile} />}
    <aside ref={sidebar} id="bo-sidebar" className="bo-sidebar" role={mobileOpen ? "dialog" : undefined} aria-modal={mobileOpen ? true : undefined} aria-label="TrackFlow workspace navigation">
      <div className="bo-sidebar-brand"><Link href="/uis/backoffice" className="bo-brand" onClick={event => navigate(event, "/uis/backoffice")}><span className="bo-brand-mark" aria-hidden="true"><i /><i /><i /></span><span>TrackFlow<span className="bo-brand-period">.</span><small>Team workspace</small></span></Link><button type="button" className="bo-mobile-close" aria-label="Close menu" onClick={closeMobile}><BackofficeIcon name="close" /></button></div>
      <nav className="bo-sidebar-nav" aria-label="Backoffice navigation">{BACKOFFICE_GROUPS.map(group => <div className="bo-nav-group" key={group.label}><h2>{group.label}</h2>{group.items.map(item => item.children ? <div key={item.href} className="bo-nav-parent"><button type="button" className={`bo-link bo-parent-button${matches(pathname, item.href) ? " bo-parent-active" : ""}`} aria-expanded={expanded.includes(item.href)} aria-controls={`bo-children-${item.icon}`} onClick={() => setExpanded(current => current.includes(item.href) ? current.filter(href => href !== item.href) : [...current, item.href])}><BackofficeIcon name={item.icon} /><span>{item.label}</span><BackofficeIcon name="chevron" /></button><div id={`bo-children-${item.icon}`} className="bo-subnav" hidden={!expanded.includes(item.href)}>{item.children.map(child => link(child.href, child.label, matches(pathname, child.href, child.exact)))}</div></div> : link(item.href, item.label, matches(pathname, item.href, item.exact), item.icon))}</div>)}</nav>
      <div className="bo-sidebar-footer">{link("/account/profile", "Your account", pathname.startsWith("/account"), "profile")}<a className="bo-link bo-website-link" href={websiteHref}><BackofficeIcon name="arrow" /><span>View public website</span></a><div className="bo-sidebar-note"><span />Los Angeles · Zaragoza</div></div>
    </aside>
    <header ref={topbar} className="bo-topbar"><div className="bo-topbar-heading"><button ref={menuButton} type="button" className="bo-menu-button" aria-label="Open navigation" aria-expanded={mobileOpen} aria-controls="bo-sidebar" onClick={() => { setMobileOpen(true); setAccountOpen(false); }}><BackofficeIcon name="menu" /></button><div><div className="bo-breadcrumb">{current.group}<span>/</span>{preview && <span className="bo-preview-pill">Design preview</span>}</div><p>{current.title}</p></div></div>
      <div className="bo-topbar-actions">{showAddLead && <Link className="button accent bo-create-button" href="/candidates/new" onClick={event => navigate(event, "/candidates/new")}><BackofficeIcon name="plus" /><span>Add lead</span></Link>}<div ref={accountWrapper} className="bo-account-wrapper"><button ref={accountButton} type="button" className="bo-account-button" aria-label="Account options" aria-expanded={accountOpen} aria-controls="bo-account-options" onClick={() => setAccountOpen(!accountOpen)}><span className="bo-avatar">{user?.email[0]?.toUpperCase() ?? "T"}</span><span className="bo-account-name">{user?.email.split("@")[0] ?? "Your account"}<small>{preview ? "Preview account" : "Team member"}</small></span><BackofficeIcon name="chevron" /></button>{accountOpen && <div id="bo-account-options" className="bo-account-popover"><p>{user?.email ?? "Your account"}</p><Link href="/account/profile" onClick={event => navigate(event, "/account/profile")}>Your profile</Link><Link href="/account/change-password" onClick={event => navigate(event, "/account/change-password")}>Change password</Link><button type="button" onClick={() => { setAccountOpen(false); onLogout(); }}><BackofficeIcon name="logout" />Sign out</button></div>}</div></div>
    </header>
  </div>;
}
