import ContactForm from "./ContactForm";
import WebsiteHeader from "./WebsiteHeader";
import NetworkIllustration from "./NetworkIllustration";
import WebsiteIcon, { WebsiteBrand } from "./WebsiteIcon";

const services = [
  { icon: "warehouse" as const, number: "01", title: "Warehouse Management", description: "A reliable home for your stock. A smoother start for every order.", items: ["Storage, picking and packing", "Real-time inventory", "Warehouses in Los Angeles and Zaragoza"] },
  { icon: "truck" as const, number: "02", title: "Last-Mile Deliveries", description: "Connect your products to your customers, with visibility along the way.", items: ["Certified carrier network in both countries", "Unified shipment tracking", "Incident and returns management"] },
  { icon: "returns" as const, number: "03", title: "Reverse Logistics", description: "Make the journey back as considered as the delivery itself.", items: ["Complete returns management", "Inspection and reconditioning", "Integration with your sales platform"] },
];
const backofficeBase = process.env.NEXT_PUBLIC_BACKOFFICE_URL?.replace(/\/+$/, "") ?? "";
const staffHref = `${backofficeBase}/uis/backoffice`;

export default function WebsiteHome() {
  return <div className="tf-site">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
      "@context": "https://schema.org", "@type": "Organization", name: "TrackFlow",
      description: "Warehouse management and last-mile deliveries for e-commerce", url: "https://trackflow.com", foundingDate: "2009",
      address: [{ "@type": "PostalAddress", addressCountry: "US", addressLocality: "Los Angeles", addressRegion: "California" }, { "@type": "PostalAddress", addressCountry: "ES", addressLocality: "Zaragoza", addressRegion: "Aragón" }],
      contactPoint: { "@type": "ContactPoint", telephone: "+1-213-555-0147", contactType: "sales", availableLanguage: ["Spanish", "English"] },
      sameAs: ["https://linkedin.com/company/trackflow"], areaServed: [{ "@type": "Country", name: "United States" }, { "@type": "Country", name: "Spain" }],
    }) }} />
    <a className="tf-skip-link" href="#home">Skip to content</a>
    <WebsiteHeader staffHref={staffHref} />
    <section id="home" className="tf-hero" aria-labelledby="tf-hero-title" tabIndex={-1}>
      <div className="tf-container tf-hero-grid">
        <div className="tf-hero-copy"><span className="tf-eyebrow"><span className="tf-small-dot" />Built for e-commerce. Connected across markets.</span>
          <h1 id="tf-hero-title">Logistics that scales with <span>your <span className="tf-nowrap">e-commerce</span></span></h1>
          <p>Warehouse management, last-mile deliveries, and reverse logistics in the United States and Spain. Over 15 years helping fashion, electronics, and cosmetics brands grow without worrying about operations.</p>
          <div className="tf-hero-actions"><a className="button accent" href="#contact-form">Request information<WebsiteIcon name="arrow" /></a><a className="tf-text-link" href="#services">Explore our services<WebsiteIcon name="arrow" /></a></div>
          <div className="tf-hero-note"><WebsiteIcon name="check" />Warehousing. Delivery. Returns. All connected.</div>
        </div><NetworkIllustration />
      </div>
      <div className="tf-container tf-proof-strip"><span>Supporting brands in</span><div>Fashion</div><span className="tf-proof-dot">·</span><div>Electronics</div><span className="tf-proof-dot">·</span><div>Cosmetics</div><span className="tf-proof-location">Los Angeles ↔ Zaragoza</span></div>
    </section>
    <section id="services" className="tf-section tf-services" aria-labelledby="services-heading" tabIndex={-1}>
      <div className="tf-container"><div className="tf-section-heading"><div><span className="tf-eyebrow">What we do</span><h2 id="services-heading">Three services.<br />One connected operation.</h2></div><p>From the first item on the shelf to the last mile—and the return journey. Find the support your business needs.</p></div>
        <div className="tf-service-grid">{services.map(service => <article className="tf-service-card" key={service.title}>
          <div className="tf-service-top"><span className="tf-icon-tile"><WebsiteIcon name={service.icon} /></span><span>{service.number}</span></div>
          <h3>{service.title}</h3><p>{service.description}</p><ul>{service.items.map(item => <li key={item}><WebsiteIcon name="check" />{item}</li>)}</ul>
          <a className="tf-text-link" href="#contact-form" aria-label={`Let’s talk about ${service.title.toLowerCase()}`}>Let’s talk<WebsiteIcon name="arrow" /></a>
        </article>)}</div>
      </div>
    </section>
    <section id="coverage" className="tf-section tf-coverage" aria-labelledby="coverage-heading" tabIndex={-1}>
      <div className="tf-container tf-coverage-grid"><div className="tf-coverage-intro"><span className="tf-eyebrow">Where we operate</span><h2 id="coverage-heading">Local knowledge.<br />A wider perspective.</h2><p>Our own infrastructure in the United States and Spain brings your logistics closer to the markets you serve.</p><a className="tf-text-link" href="#contact">Discuss your coverage<WebsiteIcon name="arrow" /></a></div>
        <div className="tf-location-list"><article className="tf-location"><div className="tf-location-marker">US</div><div><span className="tf-location-country">United States</span><h3>Los Angeles</h3><p>Our US warehouse, connected to national delivery coverage.</p><div className="tf-carriers"><span>UPS</span><span>FedEx</span><span>DHL</span></div></div><WebsiteIcon name="pin" /></article>
          <article className="tf-location"><div className="tf-location-marker">ES</div><div><span className="tf-location-country">Spain</span><h3>Zaragoza</h3><p>Our Spanish warehouse, with peninsular and island delivery coverage.</p><div className="tf-carriers"><span>MRW</span><span>SEUR</span><span>DHL</span></div></div><WebsiteIcon name="pin" /></article></div>
      </div>
    </section>
    <section id="why-trackflow" className="tf-section tf-why" aria-labelledby="why-heading" tabIndex={-1}><div className="tf-container"><div className="tf-why-top"><div><span className="tf-eyebrow">Why TrackFlow</span><h2 id="why-heading">Your growth deserves<br />a dependable partner.</h2></div><p>We combine people, infrastructure, and our own technology to help e-commerce brands keep moving.</p></div>
      <div className="tf-stat-grid"><div><strong>15<span>+</span></strong><h3>Years of experience</h3><p>Supporting e-commerce logistics since 2009.</p></div><div><strong>130<span>+</span></strong><h3>People behind your operations</h3><p>A team dedicated to your logistics.</p></div><div><strong>2</strong><h3>Markets. Our own infrastructure.</h3><p>United States and Spain, with local expertise.</p></div></div>
      <div className="tf-why-bottom"><span><WebsiteIcon name="check" />Our own technology for inventory visibility</span><span><WebsiteIcon name="check" />Specialists in fashion, electronics, and cosmetics</span></div>
    </div></section>
    <section id="contact" className="tf-section tf-contact" aria-labelledby="contact-heading" tabIndex={-1}><div className="tf-container tf-contact-grid"><div className="tf-contact-copy"><span className="tf-eyebrow">Let’s get started</span><h2 id="contact-heading">Tell us where<br />you want to grow.</h2><p>Share your monthly volume, product category, countries, and services of interest. Miguel Torres and our commercial team will review your request.</p><div className="tf-contact-methods"><a href="mailto:comercial@trackflow.com"><WebsiteIcon name="mail" /><span><small>Email our team</small>comercial@trackflow.com</span></a><a href="tel:+12135550147"><WebsiteIcon name="phone" /><span><small>Los Angeles</small>+1 213 555 0147</span></a><a href="tel:+34976123456"><WebsiteIcon name="phone" /><span><small>Zaragoza</small>+34 976 123 456</span></a></div><div className="tf-contact-note"><WebsiteIcon name="check" /><p>A conversation about your needs.<br />A clear next step for your logistics.</p></div></div><ContactForm /></div></section>
    <footer className="tf-footer"><div className="tf-container"><div className="tf-footer-top"><div><a href="#home" className="tf-brand-link" aria-label="TrackFlow home"><WebsiteBrand /></a><p>Logistics that grows with you.<br />Los Angeles & Zaragoza.</p></div><nav aria-label="Footer navigation"><a href="#services">Services</a><a href="#coverage">Coverage</a><a href="#why-trackflow">Why TrackFlow</a><a href="#contact">Contact</a></nav><div className="tf-footer-contact"><a href="mailto:comercial@trackflow.com">comercial@trackflow.com</a><a href="https://linkedin.com/company/trackflow">LinkedIn ↗</a></div></div><div className="tf-footer-bottom"><span>© 2025 TrackFlow. All rights reserved.</span><a href={staffHref}>Staff login ↗</a></div></div></footer>
  </div>;
}
