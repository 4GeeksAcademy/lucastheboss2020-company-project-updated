"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { fetchCandidates } from "../../src/candidates/api";
import { userSafeErrorMessage } from "../../src/utils/api-errors";
import type { CandidateListResponse } from "../../src/candidates/types";
import { CANDIDATE_STAGES, CANDIDATE_STATUSES } from "../../src/candidates/types";

function formatServices(services: string[]): string {
  return services.map((service) => service.replace(/-/g, " ")).join(", ");
}

export default function CandidateListClient() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const deferredQuery = useDeferredValue(query);
  const [result, setResult] = useState<CandidateListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryVersion, setRetryVersion] = useState(0);

  function updateParam(key: string, value: string) {
    const nextParams = new URLSearchParams(searchParams.toString());

    if (!value || value === "all") {
      nextParams.delete(key);
    } else {
      nextParams.set(key, value);
    }

    if (key !== "page") {
      nextParams.delete("page");
    }

    startTransition(() => {
      router.replace(`${pathname}?${nextParams.toString()}`);
    });
  }

  useEffect(() => {
    updateParam("q", deferredQuery.trim());
  }, [deferredQuery]);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");

    fetchCandidates(`?${searchParams.toString()}`)
      .then((data) => {
        if (!ignore) {
          setResult(data);
        }
      })
      .catch((fetchError: Error) => {
        if (!ignore) {
          setError(userSafeErrorMessage(fetchError, "Could not load candidates. Please retry."));
        }
      })
      .finally(() => {
        if (!ignore) {
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [searchParams, retryVersion]);

  return (
    <section>
      <header className="page-header">
        <h1>TrackFlow lead candidates</h1>
        <p>
          Review e-commerce companies that requested TrackFlow logistics support, qualify their status, and move them through the commercial pipeline.
        </p>
      </header>

      <section className="panel" aria-label="Candidate filters">
        <div className="filters">
          <label className="field">
            <span>Search by company or email</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="GlowCart or aisha@glowcart.com" />
          </label>
          <label className="field">
            <span>Status</span>
            <select value={searchParams.get("status") ?? "all"} onChange={(event) => updateParam("status", event.target.value)}>
              <option value="all">All statuses</option>
              {CANDIDATE_STATUSES.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Stage</span>
            <select value={searchParams.get("stage") ?? "all"} onChange={(event) => updateParam("stage", event.target.value)}>
              <option value="all">All stages</option>
              {CANDIDATE_STAGES.map((stage) => (
                <option key={stage} value={stage}>{stage}</option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {loading && <p className="message loading">Loading TrackFlow candidates...</p>}
      {error && (
        <div className="message error" role="alert">
          <p>{error}</p>
          <button className="secondary" type="button" onClick={() => setRetryVersion((version) => version + 1)}>Retry</button>
        </div>
      )}
      {!loading && result?.total === 0 && <p className="message">No candidates match the current filters.</p>}

      <section className="candidate-grid" aria-live="polite">
        {result?.data.map((candidate) => (
          <Link className="candidate-card" href={`/candidates/${candidate.id}`} key={candidate.id}>
            <div className="meta-row">
              <span className="badge blue">{candidate.status}</span>
              <span className="badge green">{candidate.stage}</span>
              <span className="badge">{candidate.operatingCountry}</span>
            </div>
            <div>
              <h2>{candidate.companyName}</h2>
              <p>{candidate.contactPerson} · {candidate.corporateEmail}</p>
            </div>
            <p>{candidate.productType} e-commerce · {candidate.monthlyVolume} shipments/month</p>
            <p>{formatServices(candidate.servicesOfInterest)}</p>
          </Link>
        ))}
      </section>

      {result && result.totalPages > 1 && (
        <nav className="actions" aria-label="Candidate pages" style={{ marginTop: "1rem" }}>
          <button className="secondary" disabled={result.page === 1} onClick={() => updateParam("page", String(result.page - 1))}>Previous</button>
          <span className="badge">Page {result.page} of {result.totalPages}</span>
          <button className="secondary" disabled={result.page === result.totalPages} onClick={() => updateParam("page", String(result.page + 1))}>Next</button>
        </nav>
      )}
    </section>
  );
}
