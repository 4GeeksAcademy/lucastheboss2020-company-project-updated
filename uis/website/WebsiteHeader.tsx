"use client";
import { useEffect, useRef, useState } from "react";
import WebsiteIcon, { WebsiteBrand } from "./WebsiteIcon";
export default function WebsiteHeader({ staffHref }: { staffHref: string }) {
  const [open, setOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && open) { setOpen(false); menuButton.current?.focus(); }
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [open]);
  return <header className="tf-header"><div className="tf-container tf-header-inner">
    <a className="tf-brand-link" href="#home" aria-label="TrackFlow home" onClick={() => setOpen(false)}><WebsiteBrand /></a>
    <button ref={menuButton} type="button" className="secondary tf-menu-button" aria-expanded={open} aria-controls="tf-site-navigation" onClick={() => setOpen(!open)}><WebsiteIcon name={open ? "close" : "menu"} />Menu</button>
    <nav id="tf-site-navigation" className={`tf-nav${open ? " tf-nav-open" : ""}`} aria-label="TrackFlow website navigation">
      <div className="tf-nav-links">{[["#home", "Home"], ["#services", "Services"], ["#coverage", "Coverage"], ["#contact", "Contact"]].map(([href, label]) => <a key={href} href={href} onClick={() => setOpen(false)}>{label}</a>)}</div>
      <div className="tf-nav-actions"><a className="tf-staff-link" href={staffHref}>Staff login</a><a className="button accent" href="#contact-form" onClick={() => setOpen(false)}>Request information<WebsiteIcon name="arrow" /></a></div>
    </nav>
  </div></header>;
}
