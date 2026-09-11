import type { Candidate, CandidateWriteInput } from "../candidates/types";
import type { LeadRequest, LogisticsService } from "../types/models";
import { validateLeadRequest } from "../utils/validations";

export function buildLeadRequest(id: string, input: CandidateWriteInput): LeadRequest {
  return {
    id,
    companyName: input.companyName,
    contactPerson: input.contactPerson,
    corporateEmail: input.corporateEmail,
    phone: input.phone,
    companyWebsite: input.companyWebsite,
    operatingCountry: input.operatingCountry,
    productType: input.productType,
    monthlyVolume: input.monthlyVolume,
    servicesOfInterest: input.servicesOfInterest,
    current3pl: input.current3pl,
    comments: input.comments,
    privacyAccepted: input.privacyAccepted,
    status: input.status,
  };
}

export function normalizeAssignedOwner(value: string): string {
  return value.trim() || "Commercial Desk";
}

export function createTrackFlowCandidate(
  id: string,
  input: CandidateWriteInput,
  services: LogisticsService[],
  createdAt: string = new Date().toISOString(),
): { candidate?: Candidate; errors?: string[]; warnings?: string[] } {
  const lead = buildLeadRequest(id, input);
  const validation = validateLeadRequest(lead, services);

  if (!validation.valid) {
    return { errors: validation.errors };
  }

  if (!["intake", "discovery", "proposal", "implementation"].includes(input.stage)) {
    return { errors: ["Stage must be a valid TrackFlow pipeline stage."] };
  }

  const candidate: Candidate = {
    ...lead,
    stage: input.stage,
    assignedTo: normalizeAssignedOwner(input.assignedTo),
    createdAt,
    updatedAt: createdAt,
    notes: [],
  };

  return {
    candidate,
    warnings: validation.warnings ?? [],
  };
}
