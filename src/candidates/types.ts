import type { LeadRequest, LeadStatus, LogisticsServiceName, MonthlyShippingVolume, OperatingCountry, ProductType, ThreePLStatus } from "../types/models";

export type CandidateStage = "intake" | "discovery" | "proposal" | "implementation";

export interface CandidateNote {
  id: string;
  body: string;
  createdAt: string;
}

export interface Candidate extends LeadRequest {
  stage: CandidateStage;
  assignedTo: string;
  createdAt: string;
  updatedAt: string;
  notes: CandidateNote[];
}

export interface CandidateListResponse {
  data: Candidate[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface CandidateQuery {
  q?: string;
  status?: LeadStatus | "all";
  stage?: CandidateStage | "all";
  page?: number;
}

export interface CandidateWriteInput {
  companyName: string;
  contactPerson: string;
  corporateEmail: string;
  phone: string;
  companyWebsite?: string;
  operatingCountry: OperatingCountry;
  productType: ProductType;
  monthlyVolume: MonthlyShippingVolume;
  servicesOfInterest: LogisticsServiceName[];
  current3pl: ThreePLStatus;
  comments?: string;
  privacyAccepted: boolean;
  status: LeadStatus;
  stage: CandidateStage;
  assignedTo: string;
}

export const CANDIDATE_STATUSES: LeadStatus[] = ["new", "qualified", "contacted", "not-fit"];
export const CANDIDATE_STAGES: CandidateStage[] = ["intake", "discovery", "proposal", "implementation"];
export const OPERATING_COUNTRIES: OperatingCountry[] = ["United States", "Spain", "Both", "Other"];
export const PRODUCT_TYPES: ProductType[] = ["Fashion", "Electronics", "Cosmetics", "Food", "Other"];
export const MONTHLY_VOLUMES: MonthlyShippingVolume[] = ["0-100", "101-500", "501-2000", "2000+", "Not sure"];
export const SERVICES: LogisticsServiceName[] = ["warehouse-management", "last-mile-delivery", "reverse-logistics"];
export const THREE_PL_STATUSES: ThreePLStatus[] = ["Yes", "No", "Evaluating options"];
