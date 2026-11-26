"use client";

import { useState } from "react";

const palette = [
  { name: "Deep navy", color: "#163c52", use: "Brand & primary actions" },
  { name: "TrackFlow teal", color: "#087f74", use: "Accent & key details" },
  { name: "Soft canvas", color: "#f5f7f9", use: "Page backgrounds" },
  { name: "Warm neutral", color: "#f3f0e8", use: "Supporting highlights" },
];

export default function DesignFoundations() {
  const [company, setCompany] = useState("");
  const [country, setCountry] = useState("United States");
  const [selected, setSelected] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const invalid = attempted && company.trim().length < 2;

  return <div className="foundation-review">
    <header className="foundation-review__top">
      <div className="foundation-review__brand"><span className="foundation-review__mark" aria-hidden="true"><i /><i /><i /></span>TrackFlow</div>
      <span className="foundation-review__edition">Design review · Part 1 of 7</span>
    </header>
    <div className="foundation-review__hero">
      <span className="foundation-review__eyebrow">The shared visual foundation</span>
      <h1>A clearer direction<br />for TrackFlow.</h1>
      <p>A calmer palette, more readable typography, and consistent controls for the public website and backoffice.</p>
      <nav className="foundation-review__links" aria-label="Design review sections"><a href="#palette">Colors</a><a href="#type">Typography & buttons</a><a href="#components">Forms & feedback</a><a href="/uis/website">View current website ↗</a></nav>
    </div>

    <section id="palette" className="foundation-review__section" aria-labelledby="palette-title">
      <div className="foundation-review__section-header"><span>01</span><h2 id="palette-title">A familiar brand, refined.</h2></div>
      <div className="foundation-review__swatches">{palette.map(color => <div className="foundation-review__swatch" key={color.name}>
        <div className="foundation-review__swatch-color" style={{ background: color.color }} />
        <div className="foundation-review__swatch-label"><strong>{color.name}</strong><small>{color.use}</small></div>
      </div>)}</div>
    </section>

    <section id="type" className="foundation-review__section" aria-labelledby="type-title">
      <div className="foundation-review__section-header"><span>02</span><h2 id="type-title">Clear hierarchy. Less visual noise.</h2></div>
      <div className="foundation-review__two">
        <article className="panel foundation-review__type"><span className="foundation-review__overline">Type & reading rhythm</span><h3>Logistics, made clear.</h3><p>Warehouse management, last-mile delivery, and reverse logistics in the United States and Spain.</p><small>Readable supporting text with room to breathe.</small></article>
        <article className="panel"><span className="foundation-review__overline">Actions & interaction states</span><div className="foundation-review__buttons"><a className="button" href="#sample-form">Primary action</a><a className="button secondary" href="/uis/website">Secondary action</a><a className="button accent" href="#components">Accent action</a><button type="button" disabled>Unavailable</button></div><p className="foundation-review__spacer"><small>Try hovering over a button or using Tab to see the keyboard focus indicator.</small></p></article>
      </div>
    </section>

    <section id="components" className="foundation-review__section" aria-labelledby="components-title">
      <div className="foundation-review__section-header"><span>03</span><h2 id="components-title">Helpful controls. Understandable feedback.</h2></div>
      <div className="foundation-review__two">
        <form id="sample-form" className="panel foundation-review__sample" noValidate onSubmit={event => {
          event.preventDefault(); setAttempted(true); setSubmitted(company.trim().length >= 2);
        }}>
          <h3>Try the form styles</h3><p>A local styling example. No information is sent or saved.</p>
          <label className="field"><span id="sample-company-label">Company name</span><input aria-labelledby="sample-company-label" autoComplete="organization" placeholder="Your company name" value={company} onChange={event => { setCompany(event.target.value); setSubmitted(false); }} aria-invalid={invalid} aria-describedby={invalid ? "sample-company-error" : undefined} />{invalid && <small id="sample-company-error" className="foundation-review__field-error" role="alert">Company name must have at least 2 characters</small>}</label>
          <label className="field"><span>Main operating country</span><select value={country} onChange={event => setCountry(event.target.value)}><option>United States</option><option>Spain</option><option>Both</option><option>Other</option></select></label>
          <label className="field"><span>Unavailable field</span><input disabled value="Example of a disabled field" readOnly /></label>
          <label className="foundation-review__check"><input type="checkbox" checked={selected} onChange={event => setSelected(event.target.checked)} />Example selection</label>
          <button type="submit" className="accent">Preview confirmation</button>
          {submitted && <p className="message success" role="status">The sample looks good. This was a preview only; nothing was submitted.</p>}
        </form>
        <article className="panel foundation-review__feedback"><span className="foundation-review__overline">Status labels</span><div className="foundation-review__statuses"><span className="badge info">In progress</span><span className="badge success">Approved</span><span className="badge warning">Needs review</span><span className="badge error">Action required</span></div>
          <span className="foundation-review__overline foundation-review__spacer">Examples of feedback</span>
          <div className="message success"><strong>Request received</strong>Your information is ready for review.</div>
          <div className="message warning"><strong>Needs your attention</strong>Review the highlighted details before continuing.</div>
          <div className="message error"><strong>Something needs correcting</strong>Check the field and try again.</div>
          <div className="message loading"><strong>Work in progress</strong>Your saved information remains available.</div>
          <small>Every state has a written label as well as a color.</small>
        </article>
      </div>
    </section>
    <footer className="foundation-review__footer">Part 1 review: colors, typography, spacing, buttons, fields, and feedback. Public website and backoffice layout changes come in the next stages.</footer>
  </div>;
}
