"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { fetchCandidates } from "../../src/candidates/api";
import type { CandidateListResponse } from "../../src/candidates/types";
import { CANDIDATE_STAGES, CANDIDATE_STATUSES } from "../../src/candidates/types";

function formatServices(services: string[]): string {
  return services.map((service) => service.replace(/-/g, " ")).join(", ");
}

export default function BackofficeHome() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const deferredQuery = useDeferredValue(query);
  const [result, setResult] = useState<CandidateListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function updateParam(key: string, value: string) {
    const nextParams = new URLSearchParams(searchParams.toString());
    if (!value || value === "all") nextParams.delete(key);
    else nextParams.set(key, value);
    if (key !== "page") nextParams.delete("page");
    startTransition(() => router.replace(`${pathname}?${nextParams.toString()}`));
  }

  useEffect(() => {
    updateParam("q", deferredQuery.trim());
  }, [deferredQuery]);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    fetchCandidates(`?${searchParams.toString()}`)
      .then((data) => { if (!ignore) setResult(data); })
      .catch((fetchError: Error) => { if (!ignore) setError(fetchError.message); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [searchParams]);

  return (
    <section>
      <header className="page-header">
        <span className="badge green">TrackFlow commercial operations</span>
        <h1>Lead candidate backoffice</h1>
        <p>Review e-commerce companies requesting warehouse management, last-mile delivery, or reverse logistics support.</p>
        <div className="actions">
          <Link className="button secondary" href="/uis/website#contact-form">View public lead form</Link>
          <Link className="button" href="/candidates/new">Add lead manually</Link>
          <Link className="button secondary" href="/uis/backoffice/incidents">Incident Analysis</Link>
          <Link className="button secondary" href="/uis/backoffice/suppliers">Supplier Directory</Link>
        </div>
      </header>

      <section className="panel" aria-label="Lead candidate filters">
        <div className="filters">
          <label className="field"><span>Search by company or email</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="GlowCart or aisha@glowcart.com" /></label>
          <label className="field"><span>Status</span><select value={searchParams.get("status") ?? "all"} onChange={(event) => updateParam("status", event.target.value)}><option value="all">All statuses</option>{CANDIDATE_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
          <label className="field"><span>Stage</span><select value={searchParams.get("stage") ?? "all"} onChange={(event) => updateParam("stage", event.target.value)}><option value="all">All stages</option>{CANDIDATE_STAGES.map((stage) => <option key={stage} value={stage}>{stage}</option>)}</select></label>
        </div>
      </section>

      {loading && <p className="message loading">Loading TrackFlow lead candidates...</p>}
      {error && <p className="message error" role="alert">{error}</p>}
      {!loading && result?.total === 0 && <p className="message">No lead candidates match the current filters.</p>}
      {result && <p className="message" aria-live="polite"><strong>{result.total}</strong> lead candidates found. Page {result.page} of {result.totalPages}.</p>}

      <section className="candidate-grid" aria-live="polite">
        {result?.data.map((candidate) => (
          <Link className="candidate-card" href={`/candidates/${candidate.id}`} key={candidate.id}>
            <div className="meta-row"><span className="badge blue">{candidate.status}</span><span className="badge green">{candidate.stage}</span><span className="badge">{candidate.operatingCountry}</span></div>
            <div><h2>{candidate.companyName}</h2><p>{candidate.contactPerson} · {candidate.corporateEmail}</p></div>
            <p>{candidate.productType} e-commerce · {candidate.monthlyVolume} shipments/month</p>
            <p>{formatServices(candidate.servicesOfInterest)}</p>
          </Link>
        ))}
      </section>

      {result && result.totalPages > 1 && <nav className="actions" aria-label="Lead candidate pages" style={{ marginTop: "1rem" }}><button className="secondary" disabled={result.page === 1} onClick={() => updateParam("page", String(result.page - 1))}>Previous</button><span className="badge">Page {result.page} of {result.totalPages}</span><button className="secondary" disabled={result.page === result.totalPages} onClick={() => updateParam("page", String(result.page + 1))}>Next</button></nav>}
    </section>
  );
}
