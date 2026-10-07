"use client";

import { useEffect, useState } from "react";
import {
  changeIncidentStatus,
  createIncident,
  getIncident,
  getIncidentSummary,
  IncidentApiError,
  listIncidents,
} from "../../src/incidents/manager-api";
import {
  INCIDENT_BRANCHES,
  INCIDENT_CATEGORIES,
  INCIDENT_ORIGINS,
  INCIDENT_STATUSES,
  type IncidentBranch,
  type IncidentCategory,
  type IncidentCreateInput,
  type IncidentFilters,
  type IncidentOrigin,
  type IncidentRecord,
  type IncidentStatus,
  type IncidentSummary,
} from "../../src/incidents/manager-types";

type Language = "en" | "es";

const STATUS_TRANSITIONS: Record<IncidentStatus, IncidentStatus[]> = {
  open: ["in_progress", "discarded"],
  in_progress: ["resolved", "discarded"],
  resolved: [],
  discarded: [],
};

const COPY = {
  en: {
    title: "Centralized Incident Manager",
    subtitle: "Log and track operational issues across TrackFlow facilities and customer channels.",
    language: "Language",
    summary: "Operations overview",
    total: "Total incidents",
    open: "Open",
    inProgress: "In progress",
    criticalOpen: "Open critical",
    overdue: "Unresolved over 24h",
    byStatus: "Incidents by status",
    byOrigin: "Incidents by origin",
    byBranch: "Incidents by branch",
    criticalByBranch: "Open critical by branch",
    byCategory: "Incidents by category",
    formTitle: "Register an incident",
    titleField: "Incident title",
    titlePlaceholder: "Short summary of the incident",
    description: "Description",
    descriptionPlaceholder: "What happened? Include the operational details needed to act.",
    category: "Category",
    origin: "Origin",
    branch: "Branch / facility",
    branchPrompt: "Select the reporting facility",
    branchHint: "Choose the facility where staff detected the incident.",
    submit: "Register incident",
    submitting: "Saving incident…",
    filters: "Filter incidents",
    allStatuses: "All statuses",
    allOrigins: "All origins",
    allBranches: "All branches",
    allCategories: "All categories",
    results: "Incident register",
    loading: "Loading incidents…",
    loadingDetails: "Loading incident details…",
    retry: "Retry",
    empty: "No incidents match these filters.",
    select: "Select an incident to review its details and lifecycle.",
    detail: "Incident details",
    created: "Created",
    updated: "Last updated",
    updateStatus: "Move incident to",
    finalStatus: "This incident is in a final state.",
    createSuccess: "Incident registered successfully.",
    statusSuccess: "Incident status updated.",
    titleRequired: "Enter an incident title (up to 120 characters).",
    descriptionRequired: "Enter an incident description.",
    categoryRequired: "Select an incident category.",
    originRequired: "Select where the incident was reported.",
    branchRequired: "Select a TrackFlow branch.",
    statusInvalid: "That status transition is not allowed.",
    notFound: "Incident not found.",
    serviceError: "The incident service is unavailable. Try again.",
    requestError: "The incident request could not be completed. Try again.",
    unauthorized: "Your session expired. Please sign in again.",
    retryHint: "We couldn’t load the incident data.",
    noOverdue: "No unresolved incidents are older than 24 hours.",
    overdueList: "Overdue incidents",
  },
  es: {
    title: "Gestor centralizado de incidencias",
    subtitle: "Registra y sigue problemas operativos en las instalaciones y canales de clientes de TrackFlow.",
    language: "Idioma",
    summary: "Resumen operativo",
    total: "Incidencias totales",
    open: "Abiertas",
    inProgress: "En curso",
    criticalOpen: "Críticas abiertas",
    overdue: "Sin resolver >24 h",
    byStatus: "Incidencias por estado",
    byOrigin: "Incidencias por origen",
    byBranch: "Incidencias por sede",
    criticalByBranch: "Incidencias críticas abiertas por sede",
    byCategory: "Incidencias por categoría",
    formTitle: "Registrar incidencia",
    titleField: "Título de la incidencia",
    titlePlaceholder: "Resumen breve de la incidencia",
    description: "Descripción",
    descriptionPlaceholder: "¿Qué ha ocurrido? Incluye los detalles operativos necesarios para actuar.",
    category: "Categoría",
    origin: "Origen",
    branch: "Sede / instalación",
    branchPrompt: "Selecciona la instalación que informa",
    branchHint: "Elige la instalación donde el equipo detectó la incidencia.",
    submit: "Registrar incidencia",
    submitting: "Guardando incidencia…",
    filters: "Filtrar incidencias",
    allStatuses: "Todos los estados",
    allOrigins: "Todos los orígenes",
    allBranches: "Todas las sedes",
    allCategories: "Todas las categorías",
    results: "Registro de incidencias",
    loading: "Cargando incidencias…",
    loadingDetails: "Cargando detalles…",
    retry: "Reintentar",
    empty: "No hay incidencias con estos filtros.",
    select: "Selecciona una incidencia para consultar sus detalles y ciclo de vida.",
    detail: "Detalles de la incidencia",
    created: "Creada",
    updated: "Última actualización",
    updateStatus: "Cambiar incidencia a",
    finalStatus: "La incidencia está en un estado final.",
    createSuccess: "Incidencia registrada correctamente.",
    statusSuccess: "Estado de la incidencia actualizado.",
    titleRequired: "Escribe un título (máximo 120 caracteres).",
    descriptionRequired: "Escribe una descripción.",
    categoryRequired: "Selecciona una categoría.",
    originRequired: "Selecciona el origen de la incidencia.",
    branchRequired: "Selecciona una sede de TrackFlow.",
    statusInvalid: "Ese cambio de estado no está permitido.",
    notFound: "No se encontró la incidencia.",
    serviceError: "El servicio de incidencias no está disponible. Inténtalo de nuevo.",
    requestError: "No se pudo completar la solicitud. Inténtalo de nuevo.",
    unauthorized: "La sesión ha caducado. Inicia sesión de nuevo.",
    retryHint: "No se pudieron cargar las incidencias.",
    noOverdue: "No hay incidencias sin resolver desde hace más de 24 horas.",
    overdueList: "Incidencias vencidas",
  },
} as const;

const BRANCH_LABELS: Record<Language, Record<IncidentBranch, string>> = {
  en: {
    central: "Central",
    la_warehouse: "Los Angeles — Warehouse",
    la_office: "Los Angeles — Office",
    zaragoza_warehouse: "Zaragoza — Warehouse",
    zaragoza_office: "Zaragoza — Office",
  },
  es: {
    central: "Central",
    la_warehouse: "Los Ángeles — Almacén",
    la_office: "Los Ángeles — Oficina",
    zaragoza_warehouse: "Zaragoza — Almacén",
    zaragoza_office: "Zaragoza — Oficina",
  },
};

const CATEGORY_LABELS: Record<Language, Record<IncidentCategory, string>> = {
  en: {
    lost_parcel: "Lost parcel",
    delivery_failure: "Delivery failure",
    inventory_discrepancy: "Inventory discrepancy",
    carrier_issue: "Carrier issue",
    returns_issue: "Returns issue",
    warehouse_incident: "Warehouse incident",
    system_failure: "System failure",
    client_complaint: "Client complaint",
    other: "Other",
  },
  es: {
    lost_parcel: "Paquete perdido",
    delivery_failure: "Fallo de entrega",
    inventory_discrepancy: "Diferencia de inventario",
    carrier_issue: "Problema de transportista",
    returns_issue: "Problema de devoluciones",
    warehouse_incident: "Incidente de almacén",
    system_failure: "Fallo del sistema",
    client_complaint: "Queja de cliente",
    other: "Otro",
  },
};

const STATUS_LABELS: Record<Language, Record<IncidentStatus, string>> = {
  en: { open: "Open", in_progress: "In progress", resolved: "Resolved", discarded: "Discarded" },
  es: { open: "Abierta", in_progress: "En curso", resolved: "Resuelta", discarded: "Descartada" },
};

const ORIGIN_LABELS: Record<Language, Record<IncidentOrigin, string>> = {
  en: { customer: "Customer", branch: "Branch", internal: "Internal" },
  es: { customer: "Cliente", branch: "Sede", internal: "Interno" },
};

function localizedError(error: unknown, language: Language): string {
  const copy = COPY[language];
  if (error instanceof IncidentApiError) {
    if (error.status === 401) return copy.unauthorized;
    if (error.status === 404) return copy.notFound;
    if (error.status === 503 || error.status === 500) return copy.serviceError;
    if (error.field === "status") return copy.statusInvalid;
    if (error.field === "title") return copy.titleRequired;
    if (error.field === "description") return copy.descriptionRequired;
    if (error.field === "category") return copy.categoryRequired;
    if (error.field === "origin") return copy.originRequired;
    if (error.field === "branch") return copy.branchRequired;
    return copy.requestError;
  }
  return copy.requestError;
}

function formatDate(value: string, language: Language): string {
  return new Intl.DateTimeFormat(language === "es" ? "es-ES" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function IncidentManager() {
  const [language, setLanguage] = useState<Language>("en");
  const [records, setRecords] = useState<IncidentRecord[]>([]);
  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<IncidentRecord | null>(null);
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "">("");
  const [originFilter, setOriginFilter] = useState<IncidentOrigin | "">("");
  const [branchFilter, setBranchFilter] = useState<IncidentBranch | "">("");
  const [categoryFilter, setCategoryFilter] = useState<IncidentCategory | "">("");
  const [loading, setLoading] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [updatingStatusId, setUpdatingStatusId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [summaryError, setSummaryError] = useState("");
  const [success, setSuccess] = useState("");
  const [reloadVersion, setReloadVersion] = useState(0);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<IncidentCategory | "">("");
  const [origin, setOrigin] = useState<IncidentOrigin>("customer");
  const [branch, setBranch] = useState<IncidentBranch>("central");
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const copy = COPY[language];

  useEffect(() => {
    const saved = localStorage.getItem("siteLanguage");
    if (saved === "es" || saved === "en") {
      setLanguage(saved);
      document.documentElement.lang = saved;
    }
  }, []);

  function changeLanguage(nextLanguage: Language) {
    setLanguage(nextLanguage);
    localStorage.setItem("siteLanguage", nextLanguage);
    document.documentElement.lang = nextLanguage;
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setSummaryError("");
    const filters: IncidentFilters = {
      status: statusFilter,
      origin: originFilter,
      branch: branchFilter,
      category: categoryFilter,
    };

    Promise.allSettled([listIncidents(filters), getIncidentSummary()]).then(([incidentResult, summaryResult]) => {
      if (!active) return;
      if (incidentResult.status === "fulfilled") {
        setRecords(incidentResult.value);
      } else {
        setError(localizedError(incidentResult.reason, language));
      }
      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        setSummaryError(localizedError(summaryResult.reason, language));
      }
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [statusFilter, originFilter, branchFilter, categoryFilter, reloadVersion, language]);

  useEffect(() => {
    if (!selectedId) {
      setSelectedRecord(null);
      return;
    }

    let active = true;
    setLoadingDetails(true);
    getIncident(selectedId)
      .then((record) => {
        if (active) setSelectedRecord(record);
      })
      .catch((requestError: unknown) => {
        if (active) setError(localizedError(requestError, language));
      })
      .finally(() => {
        if (active) setLoadingDetails(false);
      });

    return () => {
      active = false;
    };
  }, [selectedId, reloadVersion, language]);

  function handleOriginChange(nextOrigin: IncidentOrigin) {
    setOrigin(nextOrigin);
    if (nextOrigin === "customer" || nextOrigin === "internal") setBranch("central");
  }

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSuccess("");
    setError("");
    const nextErrors: Record<string, string> = {};
    if (!title.trim() || title.trim().length > 120) nextErrors.title = copy.titleRequired;
    if (!description.trim()) nextErrors.description = copy.descriptionRequired;
    if (!category) nextErrors.category = copy.categoryRequired;
    if (!origin) nextErrors.origin = copy.originRequired;
    if (!branch) nextErrors.branch = copy.branchRequired;
    setFormErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    const payload: IncidentCreateInput = {
      title: title.trim(),
      description,
      category: category as IncidentCategory,
      origin,
      branch,
    };
    setSubmitting(true);
    try {
      const created = await createIncident(payload);
      setTitle("");
      setDescription("");
      setCategory("");
      setOrigin("customer");
      setBranch("central");
      setFormErrors({});
      setSelectedId(created.id);
      setSuccess(copy.createSuccess);
      setReloadVersion((version) => version + 1);
    } catch (requestError) {
      setError(localizedError(requestError, language));
      if (requestError instanceof IncidentApiError && requestError.field) {
        setFormErrors({ [requestError.field]: localizedError(requestError, language) });
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStatusChange(incidentId: string, nextStatus: IncidentStatus) {
    setError("");
    setSuccess("");
    setUpdatingStatusId(incidentId);
    try {
      await changeIncidentStatus(incidentId, nextStatus);
      setSuccess(copy.statusSuccess);
      setReloadVersion((version) => version + 1);
    } catch (requestError) {
      setError(localizedError(requestError, language));
    } finally {
      setUpdatingStatusId(null);
    }
  }

  const criticalOpenCount = summary
    ? Object.values(summary.critical_open_by_branch).reduce((total, count) => total + count, 0)
    : 0;
  const openCount = summary?.by_status.open ?? 0;
  const inProgressCount = summary?.by_status.in_progress ?? 0;
  const allowedNextStatuses = selectedRecord ? STATUS_TRANSITIONS[selectedRecord.status] : [];

  return (
    <section className="incident-manager">
      <header className="page-header incident-manager__header">
        <div>
          <span className="badge green">TrackFlow · Operations</span>
          <h1>{copy.title}</h1>
          <p>{copy.subtitle}</p>
        </div>
        <div className="incident-manager__language" role="group" aria-label={copy.language}>
          <span>{copy.language}</span>
          <button
            className={language === "en" ? "" : "secondary"}
            aria-pressed={language === "en"}
            onClick={() => changeLanguage("en")}
            type="button"
          >
            EN
          </button>
          <button
            className={language === "es" ? "" : "secondary"}
            aria-pressed={language === "es"}
            onClick={() => changeLanguage("es")}
            type="button"
          >
            ES
          </button>
        </div>
      </header>

      {error && <p className="message error" role="alert">{error}</p>}
      {success && <p className="message success" role="status">{success}</p>}

      <section className="incident-manager__overview" aria-label={copy.summary}>
        <div className="incident-manager__metrics">
          <article><span>{copy.total}</span><strong>{summary?.total ?? "—"}</strong></article>
          <article><span>{copy.open}</span><strong>{openCount}</strong></article>
          <article><span>{copy.inProgress}</span><strong>{inProgressCount}</strong></article>
          <article className="incident-manager__metric-critical"><span>{copy.criticalOpen}</span><strong>{criticalOpenCount}</strong></article>
          <article className="incident-manager__metric-overdue"><span>{copy.overdue}</span><strong>{summary?.unresolved_over_24_hours.count ?? "—"}</strong></article>
        </div>

        {summary && (
          <div className="incident-manager__breakdowns">
            <section aria-label={copy.byStatus}>
              <h2>{copy.byStatus}</h2>
              <dl>
                {INCIDENT_STATUSES.map((value) => (
                  <div key={value}>
                    <dt>{STATUS_LABELS[language][value]}</dt>
                    <dd>{summary.by_status[value]}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section aria-label={copy.byOrigin}>
              <h2>{copy.byOrigin}</h2>
              <dl>
                {INCIDENT_ORIGINS.map((value) => (
                  <div key={value}>
                    <dt>{ORIGIN_LABELS[language][value]}</dt>
                    <dd>{summary.by_origin[value]}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section aria-label={copy.byBranch}>
              <h2>{copy.byBranch}</h2>
              <dl>
                {INCIDENT_BRANCHES.map((value) => (
                  <div key={value}>
                    <dt>{BRANCH_LABELS[language][value]}</dt>
                    <dd>
                      <strong>{summary.by_branch[value]}</strong>
                      <span>{copy.criticalOpen}: {summary.critical_open_by_branch[value]}</span>
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
            <section aria-label={copy.criticalByBranch}>
              <h2>{copy.criticalByBranch}</h2>
              <dl>
                {INCIDENT_BRANCHES.map((value) => (
                  <div key={value}>
                    <dt>{BRANCH_LABELS[language][value]}</dt>
                    <dd>{summary.critical_open_by_branch[value]}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <section aria-label={copy.byCategory}>
              <h2>{copy.byCategory}</h2>
              <dl>
                {INCIDENT_CATEGORIES.map((value) => (
                  <div key={value}>
                    <dt>{CATEGORY_LABELS[language][value]}</dt>
                    <dd>{summary.by_category[value]}</dd>
                  </div>
                ))}
              </dl>
            </section>
          </div>
        )}
        {summaryError && (
          <p className="message error" role="alert">
            {summaryError}{" "}
            <button type="button" className="secondary" onClick={() => setReloadVersion((version) => version + 1)}>
              {copy.retry}
            </button>
          </p>
        )}
      </section>

      {summary && summary.unresolved_over_24_hours.count > 0 ? (
        <section className="message warning" aria-labelledby="overdue-heading">
          <h2 id="overdue-heading">{copy.overdueList} ({summary.unresolved_over_24_hours.count})</h2>
          <ul className="incident-manager__overdue-list">
            {summary.unresolved_over_24_hours.incidents.map((incident) => (
              <li key={incident.id}>
                <button className="incident-manager__text-button" type="button" onClick={() => setSelectedId(incident.id)}>
                  {incident.title} · {BRANCH_LABELS[language][incident.branch]}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : summary ? (
        <p className="message success">{copy.noOverdue}</p>
      ) : null}

      <div className="incident-manager__workspace">
        <form className="panel incident-manager__form" onSubmit={handleCreate} noValidate>
          <h2>{copy.formTitle}</h2>

          <label className="field" htmlFor="incident-title">
            <span>{copy.titleField}</span>
            <input
              id="incident-title"
              value={title}
              maxLength={120}
              onChange={(event) => setTitle(event.target.value)}
              placeholder={copy.titlePlaceholder}
              aria-invalid={Boolean(formErrors.title)}
              aria-describedby={formErrors.title ? "incident-title-error" : undefined}
            />
            {formErrors.title && <span className="incident-manager__field-error" id="incident-title-error">{formErrors.title}</span>}
          </label>

          <label className="field" htmlFor="incident-description">
            <span>{copy.description}</span>
            <textarea
              id="incident-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={copy.descriptionPlaceholder}
              aria-invalid={Boolean(formErrors.description)}
              aria-describedby={formErrors.description ? "incident-description-error" : undefined}
            />
            {formErrors.description && <span className="incident-manager__field-error" id="incident-description-error">{formErrors.description}</span>}
          </label>

          <label className="field" htmlFor="incident-category">
            <span>{copy.category}</span>
            <select
              id="incident-category"
              value={category}
              onChange={(event) => setCategory(event.target.value as IncidentCategory | "")}
              aria-invalid={Boolean(formErrors.category)}
              aria-describedby={formErrors.category ? "incident-category-error" : undefined}
            >
              <option value="">{copy.categoryRequired}</option>
              {INCIDENT_CATEGORIES.map((value) => <option key={value} value={value}>{CATEGORY_LABELS[language][value]}</option>)}
            </select>
            {formErrors.category && <span className="incident-manager__field-error" id="incident-category-error">{formErrors.category}</span>}
          </label>

          <label className="field" htmlFor="incident-origin">
            <span>{copy.origin}</span>
            <select
              id="incident-origin"
              value={origin}
              onChange={(event) => handleOriginChange(event.target.value as IncidentOrigin)}
            >
              {INCIDENT_ORIGINS.map((value) => <option key={value} value={value}>{ORIGIN_LABELS[language][value]}</option>)}
            </select>
          </label>

          <label className={`field incident-manager__branch ${origin === "branch" ? "incident-manager__branch--highlight" : ""}`} htmlFor="incident-branch">
            <span>{copy.branch}</span>
            <select
              id="incident-branch"
              value={branch}
              onChange={(event) => setBranch(event.target.value as IncidentBranch)}
              aria-invalid={Boolean(formErrors.branch)}
              aria-describedby={origin === "branch" ? "incident-branch-hint" : undefined}
            >
              {INCIDENT_BRANCHES.map((value) => <option key={value} value={value}>{BRANCH_LABELS[language][value]}</option>)}
            </select>
            {origin === "branch" && <span id="incident-branch-hint" className="incident-manager__branch-hint">{copy.branchHint}</span>}
            {formErrors.branch && <span className="incident-manager__field-error">{formErrors.branch}</span>}
          </label>

          <button type="submit" disabled={submitting}>
            {submitting ? copy.submitting : copy.submit}
          </button>
        </form>

        <section className="incident-manager__registry" aria-labelledby="incident-registry-title">
          <h2 id="incident-registry-title">{copy.results}</h2>
          <div className="filters incident-manager__filters">
            <label className="field" htmlFor="filter-status">
              <span>{copy.filters}: {copy.open}</span>
              <select id="filter-status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as IncidentStatus | "")}>
                <option value="">{copy.allStatuses}</option>
                {INCIDENT_STATUSES.map((value) => <option key={value} value={value}>{STATUS_LABELS[language][value]}</option>)}
              </select>
            </label>
            <label className="field" htmlFor="filter-origin">
              <span>{copy.origin}</span>
              <select id="filter-origin" value={originFilter} onChange={(event) => setOriginFilter(event.target.value as IncidentOrigin | "")}>
                <option value="">{copy.allOrigins}</option>
                {INCIDENT_ORIGINS.map((value) => <option key={value} value={value}>{ORIGIN_LABELS[language][value]}</option>)}
              </select>
            </label>
            <label className="field" htmlFor="filter-branch">
              <span>{copy.branch}</span>
              <select id="filter-branch" value={branchFilter} onChange={(event) => setBranchFilter(event.target.value as IncidentBranch | "")}>
                <option value="">{copy.allBranches}</option>
                {INCIDENT_BRANCHES.map((value) => <option key={value} value={value}>{BRANCH_LABELS[language][value]}</option>)}
              </select>
            </label>
            <label className="field" htmlFor="filter-category">
              <span>{copy.category}</span>
              <select id="filter-category" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value as IncidentCategory | "")}>
                <option value="">{copy.allCategories}</option>
                {INCIDENT_CATEGORIES.map((value) => <option key={value} value={value}>{CATEGORY_LABELS[language][value]}</option>)}
              </select>
            </label>
          </div>

          {loading && <p className="message loading" role="status">{copy.loading}</p>}
          {!loading && error && (
            <div className="message error" role="alert">
              <p>{copy.retryHint}</p>
              <button type="button" className="secondary" onClick={() => setReloadVersion((version) => version + 1)}>{copy.retry}</button>
            </div>
          )}
          {!loading && !error && records.length === 0 && <p className="message">{copy.empty}</p>}

          <ul className="incident-manager__list" aria-live="polite">
            {records.map((record) => (
              <li key={record.id}>
                <div className="incident-manager__record-row">
                  <button
                    className={`incident-manager__record ${selectedId === record.id ? "incident-manager__record--selected" : ""}`}
                    type="button"
                    aria-pressed={selectedId === record.id}
                    onClick={() => setSelectedId(record.id)}
                  >
                    <span className="incident-manager__record-title">{record.title}</span>
                    <span className="meta-row">
                      <span className={`badge ${record.category === "lost_parcel" || record.category === "carrier_issue" ? "blue" : ""}`}>{CATEGORY_LABELS[language][record.category]}</span>
                      <span className="badge">{STATUS_LABELS[language][record.status]}</span>
                      <span className="badge">{BRANCH_LABELS[language][record.branch]}</span>
                    </span>
                    <span className="incident-manager__record-date">{formatDate(record.created_at, language)}</span>
                  </button>
                  {STATUS_TRANSITIONS[record.status].length > 0 && (
                    <label className="field incident-manager__row-status">
                      <span>{copy.updateStatus}</span>
                      <select
                        aria-label={`${copy.updateStatus}: ${record.title}`}
                        value={record.status}
                        disabled={updatingStatusId === record.id}
                        onChange={(event) => handleStatusChange(record.id, event.target.value as IncidentStatus)}
                      >
                        <option value={record.status}>{STATUS_LABELS[language][record.status]}</option>
                        {STATUS_TRANSITIONS[record.status].map((nextStatus) => (
                          <option key={nextStatus} value={nextStatus}>{STATUS_LABELS[language][nextStatus]}</option>
                        ))}
                      </select>
                    </label>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="panel incident-manager__details" aria-labelledby="incident-detail-heading">
        <h2 id="incident-detail-heading">{copy.detail}</h2>
        {loadingDetails ? <p className="message loading" role="status">{copy.loadingDetails}</p> : null}
        {!loadingDetails && !selectedRecord ? <p>{copy.select}</p> : null}
        {!loadingDetails && selectedRecord && (
          <>
            <div className="incident-manager__detail-heading">
              <h3>{selectedRecord.title}</h3>
              <div className="meta-row">
                <span className="badge blue">{CATEGORY_LABELS[language][selectedRecord.category]}</span>
                <span className="badge green">{STATUS_LABELS[language][selectedRecord.status]}</span>
                <span className="badge">{ORIGIN_LABELS[language][selectedRecord.origin]}</span>
                <span className="badge">{BRANCH_LABELS[language][selectedRecord.branch]}</span>
              </div>
            </div>
            <p className="incident-manager__detail-description">{selectedRecord.description}</p>
            <dl className="incident-manager__timestamps">
              <div><dt>{copy.created}</dt><dd>{formatDate(selectedRecord.created_at, language)}</dd></div>
              <div><dt>{copy.updated}</dt><dd>{formatDate(selectedRecord.updated_at, language)}</dd></div>
            </dl>
            {allowedNextStatuses.length > 0 ? (
              <div className="incident-manager__status-actions">
                <span>{copy.updateStatus}</span>
                {allowedNextStatuses.map((nextStatus) => (
                  <button
                    key={nextStatus}
                    type="button"
                    className={nextStatus === "discarded" ? "danger" : "secondary"}
                    disabled={updatingStatusId === selectedRecord.id}
                    onClick={() => handleStatusChange(selectedRecord.id, nextStatus)}
                  >
                    {updatingStatusId === selectedRecord.id ? copy.submitting : STATUS_LABELS[language][nextStatus]}
                  </button>
                ))}
              </div>
            ) : <p className="message">{copy.finalStatus}</p>}
          </>
        )}
      </section>
    </section>
  );
}
