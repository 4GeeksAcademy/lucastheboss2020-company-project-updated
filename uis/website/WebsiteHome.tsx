import Link from "next/link";
import ContactForm from "./ContactForm";

const services = [
  {
    title: "Warehouse Management",
    items: ["Storage, picking and packing", "Real-time inventory", "We operate warehouses in Los Angeles and Zaragoza"],
  },
  {
    title: "Last-Mile Deliveries",
    items: ["Certified carrier network in both countries", "Unified shipment tracking", "Incident and returns management"],
  },
  {
    title: "Reverse Logistics",
    items: ["Complete returns management", "Inspection and reconditioning", "Integration with your sales platform"],
  },
];

const backofficeUrl = process.env.NEXT_PUBLIC_BACKOFFICE_URL ?? "http://localhost:3001";

export default function WebsiteHome() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "Organization",
        name: "TrackFlow",
        description: "Warehouse management and last-mile deliveries for e-commerce",
        url: "https://trackflow.com",
        foundingDate: "2009",
        address: [
          { "@type": "PostalAddress", addressCountry: "US", addressLocality: "Los Angeles", addressRegion: "California" },
          { "@type": "PostalAddress", addressCountry: "ES", addressLocality: "Zaragoza", addressRegion: "Aragón" },
        ],
        contactPoint: {
          "@type": "ContactPoint",
          telephone: "+1-213-555-0147",
          contactType: "sales",
          availableLanguage: ["Spanish", "English"],
        },
        sameAs: ["https://linkedin.com/company/trackflow"],
        areaServed: [{ "@type": "Country", name: "United States" }, { "@type": "Country", name: "Spain" }],
      }) }} />
      <header className="panel" style={{ marginBottom: "1rem" }}>
        <nav className="actions" aria-label="TrackFlow website navigation">
          <strong className="brand">TrackFlow</strong>
          <a href="#home">Home</a>
          <a href="#services">Services</a>
          <a href="#coverage">Coverage</a>
          <a href="#contact">Contact</a>
          <Link className="button secondary" href={`${backofficeUrl}/uis/backoffice`}>Backoffice</Link>
        </nav>
      </header>

      <section id="home">
        <header className="page-header">
          <span className="badge blue">Los Angeles + Zaragoza</span>
          <h1>Logistics that scales with your e-commerce</h1>
          <p>
            Warehouse management, last-mile deliveries, and reverse logistics in the United States and Spain. Over 15 years helping fashion, electronics, and cosmetics brands grow without worrying about operations.
          </p>
          <div className="actions">
            <a className="button" href="#contact-form">Request information</a>
            <a className="button secondary" href="#services">View services</a>
          </div>
        </header>
      </section>

      <section id="services" className="candidate-grid" aria-labelledby="services-heading">
        <h2 id="services-heading" style={{ gridColumn: "1 / -1" }}>Services</h2>
        {services.map((service) => (
          <article className="panel" key={service.title}>
            <h3>{service.title}</h3>
            <ul>
              {service.items.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </article>
        ))}
      </section>

      <section id="coverage" className="detail-grid" style={{ marginTop: "1rem" }} aria-labelledby="coverage-heading">
        <article className="panel">
          <h2 id="coverage-heading">United States</h2>
          <p>Warehouse in Los Angeles with national coverage through UPS, FedEx, and DHL.</p>
        </article>
        <article className="panel">
          <h2>Spain</h2>
          <p>Warehouse in Zaragoza with peninsular and island coverage through MRW, SEUR, and DHL.</p>
        </article>
      </section>

      <section id="why-trackflow" className="panel" style={{ marginTop: "1rem" }} aria-labelledby="why-heading">
        <h2 id="why-heading">Why TrackFlow</h2>
        <ul>
          <li>Binational operation with own infrastructure in the United States and Spain.</li>
          <li>More than 130 professionals dedicated to e-commerce logistics.</li>
          <li>Own technology for total inventory visibility.</li>
          <li>Specialization in fashion, electronics, and cosmetics brands.</li>
        </ul>
      </section>

      <section id="contact" className="detail-grid" style={{ marginTop: "1rem" }} aria-labelledby="contact-heading">
        <article className="panel">
        <h2 id="contact-heading">Contact</h2>
          <p>Tell us about your monthly volume, product category, countries, and services of interest. Miguel Torres and the commercial team will review your request.</p>
        <p>Email: <a href="mailto:comercial@trackflow.com">comercial@trackflow.com</a></p>
        <p>Los Angeles: <a href="tel:+12135550147">+1 213 555 0147</a></p>
        <p>Zaragoza: <a href="tel:+34976123456">+34 976 123 456</a></p>
        </article>

        <ContactForm />
      </section>

      <footer className="panel" style={{ marginTop: "1rem" }}>
        <p><strong>TrackFlow</strong> · © 2025 TrackFlow. All rights reserved. · <a href="https://linkedin.com/company/trackflow">LinkedIn</a></p>
      </footer>
    </>
  );
}
