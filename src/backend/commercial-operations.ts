import type { Candidate, CandidateStage } from "../candidates/types";
import type { LeadStatus } from "../types/models";

export interface LeadQualificationSummary {
  status: LeadStatus;
  stage: CandidateStage;
  warning?: string;
  isPriority: boolean;
}

export function getLeadQualificationSummary(
  candidate: Pick<Candidate, "monthlyVolume" | "productType" | "servicesOfInterest" | "current3pl" | "status" | "stage">,
): LeadQualificationSummary {
  const lowVolumeWarning =
    candidate.monthlyVolume === "0-100"
      ? "For volumes under 100 monthly shipments, our services might not be the most efficient solution. Are you sure you want to continue?"
      : undefined;

  const status: LeadStatus =
    candidate.status === "new" || candidate.status === "qualified" || candidate.status === "contacted" || candidate.status === "not-fit"
      ? candidate.status
      : "new";

  const isPriority =
    candidate.monthlyVolume === "2000+" || candidate.servicesOfInterest.length >= 2 || candidate.productType === "Fashion";

  return {
    status,
    stage: candidate.stage,
    warning: lowVolumeWarning,
    isPriority,
  };
}
