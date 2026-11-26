"use client";

import { useState } from "react";
import BackofficeNavigation, { backofficePage } from "./BackofficeNavigation";
import BackofficeIcon from "./BackofficeIcon";

const destinations = [
  { title: "Leads", href: "/candidates", icon: "leads" as const, description: "Review companies and their logistics requirements." },
  { title: "Inventory", href: "/uis/backoffice/inventory/products", icon: "inventory" as const, description: "Find products, stock movements, and orders." },
  { title: "RFP proposals", href: "/uis/backoffice/rfp", icon: "rfp" as const, description: "Follow intake, drafts, approvals, and final proposals." },
];

export default function BackofficeNavigationPreview() {
  const [pathname, setPathname] = useState("/uis/backoffice");
  const [notice, setNotice] = useState("");
  const page = backofficePage(pathname);
  return <div className="bo-design-preview">
    <BackofficeNavigation pathname={pathname} user={{ email: "review@example.com", role: "user" }} onNavigate={href => { setPathname(href); setNotice(""); }} onLogout={() => setNotice("This is a preview account. Your actual sign-in session has not changed.")} />
    <section id="bo-preview-content" className="shell bo-content" tabIndex={-1} aria-label="Navigation design preview">
      <div className="bo-preview-notice"><BackofficeIcon name="overview" /><div><strong>Part 3 · Backoffice navigation review</strong>This is a public visual preview with sample content. Try the sidebar, grouped menus, and account options. Actual records and actions remain behind normal sign-in.</div></div>
      {notice && <p role="status" className="message loading">{notice}</p>}
      <header className="bo-preview-content-heading"><span>{page.group}</span><h1>{page.title}</h1><p>{pathname === "/uis/backoffice" ? "A more organized starting point for your team. Every tool has a place in the sidebar, with more room left for the work in front of you." : `You selected ${page.title.toLowerCase()}. The navigation and page heading now reflect that destination. This preview does not load or change operational data.`}</p></header>
      <div className="panel bo-preview-panel"><h2>Find your workspace</h2><p>Use these shortcuts, or explore the grouped navigation on the left.</p><div className="bo-preview-destinations">{destinations.map(item => <button key={item.href} type="button" onClick={() => setPathname(item.href)}><BackofficeIcon name={item.icon} /><strong>{item.title}</strong><small>{item.description}</small></button>)}</div></div>
      <div className="panel bo-preview-panel bo-preview-detail"><h2>What to review in this part</h2><ul><li>Navigation groups and labels: Workspace, Operations, Insights, and Tools.</li><li>Products and order screens grouped under Inventory; management and CSV analysis grouped under Incidents.</li><li>The highlighted current page and the heading in the top bar.</li><li>Profile, password, and sign-out actions in the account menu.</li><li>On smaller screens, the sidebar becomes a menu with keyboard support.</li></ul><p>The existing business screens use this same navigation. Their content layouts will be reviewed in the next parts.</p></div>
      <footer className="bo-preview-footer"><span>Preview content only · No live customer data</span><div><a href="/uis/website">Public website</a><span aria-hidden="true"> · </span><a href="/uis/backoffice">Open actual backoffice</a></div></footer>
    </section>
  </div>;
}
