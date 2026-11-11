import { DEMO_SERVICES, DEMO_LEADS, DEMO_FACILITIES, DEMO_TEAM_MEMBERS } from "./data/fixtures";
import { filterBy, groupBy, sortBy } from "./utils/collections";
import { binarySearch, linearSearch } from "./utils/search";
import {
  validateFacility,
  validateLeadRequest,
  validateLogisticsService,
  validateTeamMember,
} from "./utils/validations";
import {
  countLeadsByMonthlyVolume,
  countLeadsByOperatingCountry,
  countLeadsByProductType,
  countLeadsByServiceInterest,
  countLeadsByThreePLStatus,
  lowVolumeWarningLeads,
} from "./utils/transformations";

const services = DEMO_SERVICES;
const leads = DEMO_LEADS;
const facilities = DEMO_FACILITIES;
const teamMembers = DEMO_TEAM_MEMBERS;

function runSearchExamples(): void {
  const newLead = linearSearch(leads, (lead) => lead.status === "new");
  console.log("linearSearch new lead:", newLead);

  const leadsSortedById = sortBy(leads, (lead) => lead.id);
  const targetLead = binarySearch(leadsSortedById, "lead-3", (lead) => lead.id);
  console.log("binarySearch by id lead-3:", targetLead);
}

function runCollectionExamples(): void {
  const binationalLeads = filterBy(leads, (lead) => lead.operatingCountry === "Both");
  console.log("filterBy binational leads:", binationalLeads);

  const leadsByHighestVolume = sortBy(leads, (lead) => lead.monthlyVolume, "desc");
  console.log("sortBy monthly volume desc:", leadsByHighestVolume);

  const leadsGroupedByStatus = groupBy(leads, (lead) => lead.status);
  console.log("groupBy status:", leadsGroupedByStatus);
}

function runValidationExamples(): void {
  console.log("validateLogisticsService:", services.map(validateLogisticsService));
  console.log("validateLeadRequest:", leads.map((lead) => validateLeadRequest(lead, services)));
  console.log("validateFacility:", facilities.map(validateFacility));
  console.log("validateTeamMember:", teamMembers.map(validateTeamMember));
}

function runTransformationExamples(): void {
  console.log("countLeadsByServiceInterest:", countLeadsByServiceInterest(leads, services));
  console.log("countLeadsByOperatingCountry:", countLeadsByOperatingCountry(leads));
  console.log("countLeadsByProductType:", countLeadsByProductType(leads));
  console.log("countLeadsByMonthlyVolume:", countLeadsByMonthlyVolume(leads));
  console.log("countLeadsByThreePLStatus:", countLeadsByThreePLStatus(leads));
  console.log("lowVolumeWarningLeads:", lowVolumeWarningLeads(leads));
}

function runDemo(): void {
  runSearchExamples();
  runCollectionExamples();
  runValidationExamples();
  runTransformationExamples();
}

runDemo();
