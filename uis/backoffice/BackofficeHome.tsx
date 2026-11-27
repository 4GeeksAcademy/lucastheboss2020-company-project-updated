"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { fetchCandidates } from "../../src/candidates/api";
import type { CandidateListResponse } from "../../src/candidates/types";
import { CANDIDATE_STAGES, CANDIDATE_STATUSES } from "../../src/candidates/types";
import { userSafeErrorMessage } from "../../src/utils/api-errors";
import BackofficeIcon from "./BackofficeIcon";
import styles from "./Overview.module.css";

const BackofficeReports = dynamic(() => import("./BackofficeReports"), {
  ssr: false,
  loading: () => <p className="message loading">Loading reports and analytics...</p>,
});

function formatServices(services: string[]): string {
  return services.map((service) => service.replace(/-/g, " ")).join(", ");
}

const websiteUrl = (process.env.NEXT_PUBLIC_WEBSITE_URL ?? "").replace(/\/+$/, "");
const metrics = [
  { label: "All leads", query: "", hint: "Across your pipeline" },
  { label: "New enquiries", query: "status=new", hint: "Ready to qualify" },
  { label: "Qualified leads", query: "status=qualified", hint: "A fit for TrackFlow" },
  { label: "At proposal stage", query: "stage=proposal", hint: "Moving towards a decision" },
];

export default function BackofficeHome() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const deferredQuery = useDeferredValue(query);
  const [result, setResult] = useState<CandidateListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryVersion, setRetryVersion] = useState(0);
  const [counts, setCounts] = useState<number[] | null>(null);
  const [summaryError, setSummaryError] = useState(false);
  const [showExamples, setShowExamples] = useState(false);

  function updateParam(key: string, value: string) {
    if ((searchParams.get(key) ?? "") === (value === "all" ? "" : value)) return;
    const nextParams = new URLSearchParams(searchParams.toString());
    if (!value || value === "all") nextParams.delete(key);
    else nextParams.set(key, value);
    if (key !== "page") nextParams.delete("page");
    startTransition(() => router.replace(`${pathname}?${nextParams.toString()}`, { scroll: false }));
  }

  useEffect(() => {
    updateParam("q", deferredQuery.trim());
  }, [deferredQuery]);

  useEffect(() => {
    let ignore = false;
    setCounts(null);
    setSummaryError(false);
    Promise.all(metrics.map((metric) => fetchCandidates(`?${metric.query}`)))
      .then((responses) => { if (!ignore) setCounts(responses.map((response) => response.total)); })
      .catch(() => { if (!ignore) setSummaryError(true); });
    return () => { ignore = true; };
  }, [retryVersion]);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");
    fetchCandidates(`?${searchParams.toString()}`)
      .then((data) => { if (!ignore) setResult(data); })
      .catch((fetchError: unknown) => {
        if (!ignore) setError(userSafeErrorMessage(fetchError, "Could not load the lead dashboard. Please retry."));
      })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [searchParams, retryVersion]);

  return (
    <section className={styles.overview}>
      <header className={styles.heading}>
        <div><span className={styles.eyebrow}>YOUR TRACKFLOW WORKSPACE</span><h1>Operations, in view.</h1><p>A clear starting point for your commercial pipeline and daily operations.</p></div>
        <button className="secondary" onClick={() => setRetryVersion((version) => version + 1)}>Refresh overview</button>
      </header>

      <section className={styles.metrics} aria-label="Pipeline overview">
        {metrics.map((metric, index) => <Link href={`/candidates${metric.query ? `?${metric.query}` : ""}`} key={metric.label} className={styles.metric}><span>{metric.label}</span><strong>{counts ? counts[index] : "—"}</strong><small>{metric.hint}<BackofficeIcon name="arrow" /></small></Link>)}
      </section>
      {summaryError && <p role="status" className={styles.notice}>Pipeline totals could not be loaded. Use Refresh overview to try again.</p>}

      <div className={styles.workspace}><section className={styles.pipeline} aria-labelledby="overview-pipeline-title">
      <header className={styles.panelHeader}><div><h2 id="overview-pipeline-title">Your lead pipeline</h2><p>Find a company and pick up the conversation.</p></div><Link href="/candidates">View all leads <BackofficeIcon name="arrow" /></Link></header>

      <section className={styles.filterPanel} aria-label="Lead candidate filters">
        <div className={styles.filters}>
          <label className="field"><span>Search by company or email</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="GlowCart or aisha@glowcart.com" /></label>
          <label className="field"><span>Status</span><select value={searchParams.get("status") ?? "all"} onChange={(event) => updateParam("status", event.target.value)}><option value="all">All statuses</option>{CANDIDATE_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}</select></label>
          <label className="field"><span>Stage</span><select value={searchParams.get("stage") ?? "all"} onChange={(event) => updateParam("stage", event.target.value)}><option value="all">All stages</option>{CANDIDATE_STAGES.map((stage) => <option key={stage} value={stage}>{stage}</option>)}</select></label>
        </div>
      </section>

      {loading && <p className="message loading">Loading TrackFlow lead candidates...</p>}
      {error && (
        <div className="message error" role="alert">
          <p>{error}</p>
          <button className="secondary" type="button" onClick={() => setRetryVersion((version) => version + 1)}>Retry</button>
        </div>
      )}
      {!loading && result?.total === 0 && <p className="message">No lead candidates match the current filters.</p>}
      {!loading && !error && result && <p className={styles.resultStatus} role="status"><strong>{result.total}</strong> leads match your filters.</p>}

      <section className={styles.leadList} aria-label="Matching leads" aria-busy={loading}>
        {!loading && !error && result?.data.map((candidate) => (
          <Link className={styles.lead} href={`/candidates/${candidate.id}`} key={candidate.id}>
            <span className={styles.companyAvatar} aria-hidden="true">{candidate.companyName.slice(0, 1).toUpperCase()}</span>
            <span className={styles.company}><strong>{candidate.companyName}</strong><small>{candidate.contactPerson} · {candidate.corporateEmail}</small><span>{candidate.operatingCountry} · {candidate.productType} · {candidate.monthlyVolume} shipments/month</span><span>{formatServices(candidate.servicesOfInterest)}</span></span>
            <span className={styles.progress}><span className={`badge ${candidate.status === "new" ? "blue" : candidate.status === "qualified" ? "green" : ""}`}>{candidate.status}</span><small>{candidate.stage}</small></span><BackofficeIcon name="arrow" />
          </Link>
        ))}
      </section>

      {!loading && !error && result && result.totalPages > 1 && <nav className={styles.pagination} aria-label="Lead candidate pages"><button className="secondary" disabled={result.page === 1} onClick={() => updateParam("page", String(result.page - 1))}>Previous</button><span>Page {result.page} of {result.totalPages}</span><button className="secondary" disabled={result.page === result.totalPages} onClick={() => updateParam("page", String(result.page + 1))}>Next</button></nav>}
      </section>

      <aside className={styles.aside} aria-label="Workspace shortcuts">
        <section className={styles.shortcuts}><span className={styles.eyebrow}>PICK UP WHERE YOU NEED TO</span><h2>Continue your work</h2>
          <Link className={styles.shortcut} href="/uis/backoffice/rfp"><BackofficeIcon name="rfp" /><span><strong>RFP proposals</strong><small>Review requests and department approvals.</small></span><BackofficeIcon name="arrow" /></Link>
          <Link className={styles.shortcut} href="/uis/backoffice/inventory/products"><BackofficeIcon name="inventory" /><span><strong>Inventory</strong><small>Check stock across both warehouses.</small></span><BackofficeIcon name="arrow" /></Link>
          <Link className={styles.shortcut} href="/uis/backoffice/incidents/manager"><BackofficeIcon name="incidents" /><span><strong>Incident manager</strong><small>Follow operational issues through resolution.</small></span><BackofficeIcon name="arrow" /></Link>
        </section>
        <section className={styles.insight}><BackofficeIcon name="reports" /><h2>A wider view of performance</h2><p>Explore warehouse and client KPIs in your weekly reporting workspace.</p><Link href="/uis/backoffice/reporting">Open weekly reporting <BackofficeIcon name="arrow" /></Link></section>
        <Link className={styles.publicLink} href={`${websiteUrl}/uis/website#contact-form`}>Open the public enquiry form <BackofficeIcon name="arrow" /></Link>
      </aside></div>
      <details className={styles.examples} onToggle={(event) => { if (event.currentTarget.open) setShowExamples(true); }}><summary>Lead analysis examples</summary><p>Training examples from earlier milestones. These figures use demonstration leads.</p>{showExamples && <BackofficeReports />}</details>
    </section>
  );
}
