"use client";

import { useMemo } from "react";
import {
  DEMO_SERVICES,
  DEMO_LEADS,
  DEMO_FACILITIES,
  DEMO_TEAM_MEMBERS,
} from "../../src/data/fixtures";
import { filterBy, groupBy, sortBy } from "../../src/utils/collections";
import { binarySearch, linearSearch } from "../../src/utils/search";
import {
  validateFacility,
  validateLeadRequest,
  validateLogisticsService,
  validateTeamMember,
} from "../../src/utils/validations";
import {
  countLeadsByServiceInterest,
  countLeadsByOperatingCountry,
  countLeadsByProductType,
  countLeadsByMonthlyVolume,
  countLeadsByThreePLStatus,
  lowVolumeWarningLeads,
} from "../../src/utils/transformations";

function formatServiceName(name: string): string {
  return name.replace(/-/g, " ");
}

function Bar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="report-bar-row">
      <span className="report-bar-label">{label}</span>
      <div className="report-bar-track">
        <div
          className="report-bar-fill"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="report-bar-value">{value}</span>
    </div>
  );
}

export default function BackofficeReports() {
  const services = DEMO_SERVICES;
  const leads = DEMO_LEADS;
  const facilities = DEMO_FACILITIES;
  const teamMembers = DEMO_TEAM_MEMBERS;

  const reports = useMemo(() => {
    const byService = countLeadsByServiceInterest(leads, services);
    const byCountry = countLeadsByOperatingCountry(leads);
    const byProduct = countLeadsByProductType(leads);
    const byVolume = countLeadsByMonthlyVolume(leads);
    const by3pl = countLeadsByThreePLStatus(leads);
    const lowVolume = lowVolumeWarningLeads(leads);

    const filterResult = filterBy(leads, (l) => l.operatingCountry === "Both");
    const groupResult = groupBy(leads, (l) => l.status);
    const sortResult = sortBy(leads, (l) => l.monthlyVolume, "desc");

    const searchNew = linearSearch(leads, (l) => l.status === "new");
    const sortedLeads = sortBy(leads, (l) => l.id, "asc");
    const binaryFound = binarySearch(sortedLeads, "lead-3", (l) => l.id);

    const serviceValidation = services.map((s) => ({
      name: s.name,
      result: validateLogisticsService(s),
    }));
    const leadValidation = leads.map((l) => ({
      name: l.companyName,
      result: validateLeadRequest(l, services),
    }));
    const facilityValidation = facilities.map((f) => ({
      name: f.city,
      result: validateFacility(f),
    }));
    const teamValidation = teamMembers.map((t) => ({
      name: t.name,
      result: validateTeamMember(t),
    }));

    return {
      byService,
      byCountry,
      byProduct,
      byVolume,
      by3pl,
      lowVolume,
      filterResult,
      groupResult,
      sortResult,
      searchNew,
      binaryFound,
      serviceValidation,
      leadValidation,
      facilityValidation,
      teamValidation,
    };
  }, []);

  const maxService = Math.max(...Object.values(reports.byService), 1);
  const maxCountry = Math.max(...Object.values(reports.byCountry), 1);
  const maxProduct = Math.max(...Object.values(reports.byProduct), 1);
  const maxVolume = Math.max(...Object.values(reports.byVolume), 1);
  const max3pl = Math.max(...Object.values(reports.by3pl), 1);

  return (
    <section className="panel" style={{ marginTop: "2rem" }}>
      <header className="page-header">
        <span className="badge green">Milestone 2 — src/utils reports</span>
        <h2 style={{ fontSize: "1.5rem" }}>Lead Reports &amp; Analysis</h2>
        <p>
          TrackFlow lead pipeline insights generated from{" "}
          <strong>{leads.length} demo leads</strong> using shared utility
          functions from <code>src/utils/</code>.
        </p>
      </header>

      {/* ── Transformation Reports ── */}
      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge blue">Transformation</span> Leads by Service Interest
        </h3>
        <div className="report-bars">
          {Object.entries(reports.byService).map(([key, val]) => (
            <Bar key={key} label={formatServiceName(key)} value={val} max={maxService} color="#2563eb" />
          ))}
        </div>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge blue">Transformation</span> Leads by Operating Country
        </h3>
        <div className="report-bars">
          {Object.entries(reports.byCountry).map(([key, val]) => (
            <Bar key={key} label={key} value={val} max={maxCountry} color="#059669" />
          ))}
        </div>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge blue">Transformation</span> Leads by Product Type
        </h3>
        <div className="report-bars">
          {Object.entries(reports.byProduct).map(([key, val]) => (
            <Bar key={key} label={key} value={val} max={maxProduct} color="#d97706" />
          ))}
        </div>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge blue">Transformation</span> Leads by Monthly Volume
        </h3>
        <div className="report-bars">
          {Object.entries(reports.byVolume).map(([key, val]) => (
            <Bar key={key} label={key} value={val} max={maxVolume} color="#7c3aed" />
          ))}
        </div>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge blue">Transformation</span> Leads by 3PL Status
        </h3>
        <div className="report-bars">
          {Object.entries(reports.by3pl).map(([key, val]) => (
            <Bar key={key} label={key} value={val} max={max3pl} color="#dc2626" />
          ))}
        </div>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge blue">Transformation</span> Low-Volume Warning Leads
        </h3>
        {reports.lowVolume.length === 0 ? (
          <p className="message success">No leads trigger the low-volume warning.</p>
        ) : (
          <div className="candidate-grid">
            {reports.lowVolume.map((lead) => (
              <div key={lead.id} className="candidate-card">
                <div className="meta-row">
                  <span className="badge">{lead.companyName}</span>
                  <span className="badge">{lead.monthlyVolume}</span>
                </div>
                <p className="message warning" style={{ margin: 0 }}>
                  For volumes under 100 monthly shipments, our services might not be
                  the most efficient solution. Are you sure you want to continue?
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Collection Reports ── */}
      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge green">Collections</span> filterBy — Binational Leads
        </h3>
        {reports.filterResult.length === 0 ? (
          <p className="message">No leads match the filter.</p>
        ) : (
          <div className="candidate-grid">
            {reports.filterResult.map((lead) => (
              <div key={lead.id} className="candidate-card">
                <div className="meta-row">
                  <span className="badge">{lead.companyName}</span>
                  <span className="badge">{lead.operatingCountry}</span>
                </div>
                <p>{lead.contactPerson} · {lead.corporateEmail}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge green">Collections</span> groupBy — Leads by Status
        </h3>
        <div className="report-bars">
          {Object.entries(reports.groupResult).map(([key, items]) => (
            <Bar key={key} label={`${key} (${items.length})`} value={items.length} max={leads.length} color="#0891b2" />
          ))}
        </div>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge green">Collections</span> sortBy — Monthly Volume (desc)
        </h3>
        <table className="report-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Volume</th>
              <th>Country</th>
            </tr>
          </thead>
          <tbody>
            {reports.sortResult.map((lead) => (
              <tr key={lead.id}>
                <td>{lead.companyName}</td>
                <td>{lead.monthlyVolume}</td>
                <td>{lead.operatingCountry}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Search Reports ── */}
      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge">Search</span> linearSearch — First "new" Lead
        </h3>
        {reports.searchNew ? (
          <div className="candidate-card">
            <div className="meta-row">
              <span className="badge blue">{reports.searchNew.companyName}</span>
              <span className="badge green">{reports.searchNew.status}</span>
            </div>
            <p>{reports.searchNew.contactPerson} · {reports.searchNew.corporateEmail}</p>
          </div>
        ) : (
          <p className="message">No new-status lead found.</p>
        )}
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge">Search</span> binarySearch — Lookup "lead-3" by id
        </h3>
        {reports.binaryFound ? (
          <div className="candidate-card">
            <div className="meta-row">
              <span className="badge blue">{reports.binaryFound.companyName}</span>
              <span className="badge">{reports.binaryFound.id}</span>
            </div>
            <p>{reports.binaryFound.contactPerson} · {reports.binaryFound.operatingCountry}</p>
          </div>
        ) : (
          <p className="message">Lead not found.</p>
        )}
      </div>

      {/* ── Validation Reports ── */}
      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge green">Validation</span> LogisticsService Validation
        </h3>
        <table className="report-table">
          <thead>
            <tr>
              <th>Service</th>
              <th>Valid</th>
              <th>Errors</th>
            </tr>
          </thead>
          <tbody>
            {reports.serviceValidation.map(({ name, result }) => (
              <tr key={name}>
                <td>{formatServiceName(name)}</td>
                <td>{result.valid ? "✅" : "❌"}</td>
                <td>{result.errors.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge green">Validation</span> LeadRequest Validation
        </h3>
        <table className="report-table">
          <thead>
            <tr>
              <th>Company</th>
              <th>Valid</th>
              <th>Errors</th>
              <th>Warnings</th>
            </tr>
          </thead>
          <tbody>
            {reports.leadValidation.map(({ name, result }) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{result.valid ? "✅" : "❌"}</td>
                <td>{result.errors.join("; ") || "—"}</td>
                <td>{result.warnings?.join("; ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge green">Validation</span> Facility Validation
        </h3>
        <table className="report-table">
          <thead>
            <tr>
              <th>Facility</th>
              <th>Valid</th>
              <th>Errors</th>
            </tr>
          </thead>
          <tbody>
            {reports.facilityValidation.map(({ name, result }) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{result.valid ? "✅" : "❌"}</td>
                <td>{result.errors.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="report-section">
        <h3 className="report-section-title">
          <span className="badge green">Validation</span> TeamMember Validation
        </h3>
        <table className="report-table">
          <thead>
            <tr>
              <th>Member</th>
              <th>Valid</th>
              <th>Errors</th>
            </tr>
          </thead>
          <tbody>
            {reports.teamValidation.map(({ name, result }) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{result.valid ? "✅" : "❌"}</td>
                <td>{result.errors.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}