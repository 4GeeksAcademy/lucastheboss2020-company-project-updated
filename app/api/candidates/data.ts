import type { LogisticsService } from "../../../src/types/models";
import { createTrackFlowCandidate, normalizeAssignedOwner } from "../../../src/backend/lead-capture";
import { getLeadQualificationSummary } from "../../../src/backend/commercial-operations";
import type { Candidate, CandidateStage, CandidateWriteInput } from "../../../src/candidates/types";
import { CANDIDATE_STAGES, CANDIDATE_STATUSES } from "../../../src/candidates/types";

const pageSize = 5;

const services: LogisticsService[] = [
  { id: "svc-1", name: "warehouse-management", baseMonthlyFee: 2500 },
  { id: "svc-2", name: "last-mile-delivery", baseMonthlyFee: 1800 },
  { id: "svc-3", name: "reverse-logistics", baseMonthlyFee: 1500 },
];

let candidates: Candidate[] = [
  {
    id: "lead-1",
    companyName: "Nova Fashion Co",
    contactPerson: "Elena Morris",
    corporateEmail: "elena@novafashion.com",
    phone: "+1 213 555 0198",
    companyWebsite: "https://novafashion.com",
    operatingCountry: "United States",
    productType: "Fashion",
    monthlyVolume: "501-2000",
    servicesOfInterest: ["warehouse-management", "last-mile-delivery"],
    current3pl: "Evaluating options",
    comments: "Launching a West Coast fulfillment operation next quarter.",
    privacyAccepted: true,
    status: "qualified",
    stage: "proposal",
    assignedTo: "Miguel Torres",
    createdAt: "2026-08-15T10:00:00.000Z",
    updatedAt: "2026-09-01T12:00:00.000Z",
    notes: [
      { id: "note-1", body: "Interested in Los Angeles warehouse capacity and national carrier SLAs.", createdAt: "2026-09-01T12:00:00.000Z" },
    ],
  },
  {
    id: "lead-2",
    companyName: "CircuitBox",
    contactPerson: "Miguel Santos",
    corporateEmail: "miguel@circuitbox.es",
    phone: "+34 976 123 777",
    companyWebsite: "https://circuitbox.es",
    operatingCountry: "Spain",
    productType: "Electronics",
    monthlyVolume: "101-500",
    servicesOfInterest: ["reverse-logistics"],
    current3pl: "Yes",
    privacyAccepted: true,
    status: "contacted",
    stage: "discovery",
    assignedTo: "Sofia Ruiz",
    createdAt: "2026-08-20T09:30:00.000Z",
    updatedAt: "2026-08-28T14:20:00.000Z",
    notes: [],
  },
  {
    id: "lead-3",
    companyName: "GlowCart",
    contactPerson: "Aisha Patel",
    corporateEmail: "aisha@glowcart.com",
    phone: "+1 310 555 0142",
    operatingCountry: "Both",
    productType: "Cosmetics",
    monthlyVolume: "2000+",
    servicesOfInterest: ["warehouse-management", "last-mile-delivery", "reverse-logistics"],
    current3pl: "No",
    privacyAccepted: true,
    status: "new",
    stage: "intake",
    assignedTo: "Miguel Torres",
    createdAt: "2026-09-02T08:45:00.000Z",
    updatedAt: "2026-09-02T08:45:00.000Z",
    notes: [{ id: "note-2", body: "Needs binational inventory visibility for campaign peaks.", createdAt: "2026-09-02T08:50:00.000Z" }],
  },
  {
    id: "lead-4",
    companyName: "Small Batch Goods",
    contactPerson: "Laura Chen",
    corporateEmail: "laura@smallbatchgoods.com",
    phone: "+1 323 555 0110",
    operatingCountry: "Other",
    productType: "Other",
    monthlyVolume: "0-100",
    servicesOfInterest: ["last-mile-delivery"],
    current3pl: "No",
    comments: "Testing whether outsourced logistics makes sense yet.",
    privacyAccepted: true,
    status: "not-fit",
    stage: "intake",
    assignedTo: "Commercial Desk",
    createdAt: "2026-09-03T16:00:00.000Z",
    updatedAt: "2026-09-03T16:00:00.000Z",
    notes: [],
  },
  {
    id: "lead-5",
    companyName: "Zeta Apparel",
    contactPerson: "Clara Ibarra",
    corporateEmail: "clara@zetaapparel.es",
    phone: "+34 976 555 211",
    companyWebsite: "https://zetaapparel.es",
    operatingCountry: "Both",
    productType: "Fashion",
    monthlyVolume: "501-2000",
    servicesOfInterest: ["warehouse-management", "reverse-logistics"],
    current3pl: "Evaluating options",
    privacyAccepted: true,
    status: "qualified",
    stage: "implementation",
    assignedTo: "Sofia Ruiz",
    createdAt: "2026-08-10T11:15:00.000Z",
    updatedAt: "2026-09-04T10:10:00.000Z",
    notes: [],
  },
  {
    id: "lead-6",
    companyName: "VoltMarket",
    contactPerson: "James Rivera",
    corporateEmail: "james@voltmarket.com",
    phone: "+1 213 555 0180",
    companyWebsite: "https://voltmarket.com",
    operatingCountry: "United States",
    productType: "Electronics",
    monthlyVolume: "2000+",
    servicesOfInterest: ["last-mile-delivery"],
    current3pl: "Yes",
    privacyAccepted: true,
    status: "contacted",
    stage: "proposal",
    assignedTo: "Miguel Torres",
    createdAt: "2026-08-25T13:40:00.000Z",
    updatedAt: "2026-09-05T13:40:00.000Z",
    notes: [],
  },
];

function now(): string {
  return new Date().toISOString();
}

function nextId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function normalizePage(value: string | null): number {
  const page = Number(value ?? "1");
  return Number.isInteger(page) && page > 0 ? page : 1;
}

export function listCandidates(searchParams: URLSearchParams) {
  const query = (searchParams.get("q") ?? "").trim().toLowerCase();
  const status = searchParams.get("status") ?? "all";
  const stage = searchParams.get("stage") ?? "all";
  const page = normalizePage(searchParams.get("page"));

  const filtered = candidates.filter((candidate) => {
    const matchesQuery = !query || candidate.companyName.toLowerCase().includes(query) || candidate.corporateEmail.toLowerCase().includes(query);
    const matchesStatus = status === "all" || candidate.status === status;
    const matchesStage = stage === "all" || candidate.stage === stage;
    return matchesQuery && matchesStatus && matchesStage;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const boundedPage = Math.min(page, totalPages);
  const start = (boundedPage - 1) * pageSize;

  return {
    data: filtered.slice(start, start + pageSize),
    page: boundedPage,
    pageSize,
    total: filtered.length,
    totalPages,
  };
}

export function getCandidate(id: string): Candidate | undefined {
  return candidates.find((candidate) => candidate.id === id);
}

export function createCandidate(input: CandidateWriteInput): { candidate?: Candidate; errors?: string[]; warnings?: string[] } {
  const id = nextId("lead");
  const createdAt = now();
  const result = createTrackFlowCandidate(id, input, services, createdAt);

  if (!result.candidate) {
    return { errors: result.errors ?? ["Candidate could not be created."], warnings: result.warnings ?? [] };
  }

  const candidate = result.candidate;
  const qualification = getLeadQualificationSummary(candidate);

  const normalizedCandidate: Candidate = {
    ...candidate,
    status: qualification.status,
    stage: qualification.stage,
    assignedTo: normalizeAssignedOwner(candidate.assignedTo),
    updatedAt: createdAt,
  };

  candidates = [normalizedCandidate, ...candidates];
  return { candidate: normalizedCandidate, warnings: result.warnings ?? [] };
}

export function replaceCandidate(id: string, input: CandidateWriteInput): { candidate?: Candidate; errors?: string[]; warnings?: string[] } {
  const existing = getCandidate(id);

  if (!existing) {
    return { errors: ["Candidate was not found."] };
  }

  const result = createTrackFlowCandidate(id, input, services, now());

  if (!result.candidate) {
    return { errors: result.errors ?? ["Candidate could not be saved."], warnings: result.warnings ?? [] };
  }

  const qualification = getLeadQualificationSummary(result.candidate);
  const updated: Candidate = {
    ...existing,
    ...result.candidate,
    status: qualification.status,
    stage: qualification.stage,
    assignedTo: normalizeAssignedOwner(result.candidate.assignedTo),
    updatedAt: now(),
  };

  candidates = candidates.map((candidate) => (candidate.id === id ? updated : candidate));
  return { candidate: updated, warnings: result.warnings ?? [] };
}

export function patchCandidate(id: string, payload: { status?: string; stage?: string }): { candidate?: Candidate; errors?: string[] } {
  const existing = getCandidate(id);

  if (!existing) {
    return { errors: ["Candidate was not found."] };
  }

  if (payload.status && !CANDIDATE_STATUSES.includes(payload.status as Candidate["status"])) {
    return { errors: ["Status must be a valid TrackFlow candidate status."] };
  }

  if (payload.stage && !CANDIDATE_STAGES.includes(payload.stage as CandidateStage)) {
    return { errors: ["Stage must be a valid TrackFlow pipeline stage."] };
  }

  const updated: Candidate = {
    ...existing,
    status: (payload.status as Candidate["status"] | undefined) ?? existing.status,
    stage: (payload.stage as CandidateStage | undefined) ?? existing.stage,
    updatedAt: now(),
  };

  candidates = candidates.map((candidate) => (candidate.id === id ? updated : candidate));
  return { candidate: updated };
}

export function addNote(id: string, body: string): { candidate?: Candidate; errors?: string[] } {
  const existing = getCandidate(id);
  const text = body.trim();

  if (!existing) {
    return { errors: ["Candidate was not found."] };
  }

  if (text.length < 2) {
    return { errors: ["Note must have at least 2 characters."] };
  }

  const updated: Candidate = {
    ...existing,
    notes: [{ id: nextId("note"), body: text, createdAt: now() }, ...existing.notes],
    updatedAt: now(),
  };

  candidates = candidates.map((candidate) => (candidate.id === id ? updated : candidate));
  return { candidate: updated };
}

export function deleteNote(id: string, noteId: string): { candidate?: Candidate; errors?: string[] } {
  const existing = getCandidate(id);

  if (!existing) {
    return { errors: ["Candidate was not found."] };
  }

  if (!existing.notes.some((note) => note.id === noteId)) {
    return { errors: ["Note was not found."] };
  }

  const updated: Candidate = {
    ...existing,
    notes: existing.notes.filter((note) => note.id !== noteId),
    updatedAt: now(),
  };

  candidates = candidates.map((candidate) => (candidate.id === id ? updated : candidate));
  return { candidate: updated };
}
