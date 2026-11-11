import type { Facility, LeadRequest, LogisticsService, TeamMember } from "../types/models";
import {
  LOW_VOLUME_WARNING,
  shouldWarnForLowVolume,
  validateFacility,
  validateLeadRequest,
  validateLogisticsService,
  validateTeamMember,
} from "./validations";

const services: LogisticsService[] = [
  { id: "warehouse", name: "warehouse-management", baseMonthlyFee: 2500 },
  { id: "delivery", name: "last-mile-delivery", baseMonthlyFee: 1800 },
];

const validLead: LeadRequest = {
  id: "lead-test",
  companyName: "Northstar Commerce",
  contactPerson: "Ava Morgan",
  corporateEmail: "ava@northstar.example",
  phone: "+1 213 555 0147",
  companyWebsite: "https://northstar.example",
  operatingCountry: "United States",
  productType: "Fashion",
  monthlyVolume: "501-2000",
  servicesOfInterest: ["warehouse-management"],
  current3pl: "No",
  comments: "",
  privacyAccepted: true,
  status: "new",
};

const validFacility: Facility = {
  id: "facility-test",
  city: "Los Angeles",
  country: "United States",
  services: ["warehouse-management"],
  carriers: ["UPS"],
};

const validMember: TeamMember = {
  id: "member-test",
  name: "Ava Morgan",
  role: "warehouse-operator",
  country: "United States",
};

describe("TrackFlow utility validations", () => {
  it("accepts a valid logistics service and rejects invalid rates", () => {
    expect(validateLogisticsService(services[0]).valid).toBe(true);
    expect(validateLogisticsService({ ...services[0], baseMonthlyFee: 0 }).errors).toContain(
      "LogisticsService warehouse: baseMonthlyFee must be > 0.",
    );
  });

  it("accepts valid leads and reports required-field failures", () => {
    expect(validateLeadRequest(validLead, services)).toEqual({ valid: true, errors: [], warnings: [] });

    const invalid = validateLeadRequest(
      {
        ...validLead,
        companyName: "A",
        contactPerson: "Ava",
        corporateEmail: "not-an-email",
        phone: "2135550147",
        servicesOfInterest: [],
        privacyAccepted: false,
      },
      services,
    );

    expect(invalid.valid).toBe(false);
    expect(invalid.errors).toEqual(expect.arrayContaining([
      "Company name must have at least 2 characters",
      "Enter first and last name of contact",
      "Enter a valid corporate email (example: name@company.com)",
      "Phone must include country code (example: +1 213 555 0147)",
      "Select at least one service of interest",
      "You must accept the privacy policy to continue",
    ]));
  });

  it("accepts empty optional lead fields and emits the low-volume warning", () => {
    const lead: LeadRequest = { ...validLead, companyWebsite: "", comments: "", monthlyVolume: "0-100" };

    expect(validateLeadRequest(lead, services).warnings).toContain(LOW_VOLUME_WARNING);
    expect(shouldWarnForLowVolume(lead)).toBe(true);
    expect(shouldWarnForLowVolume({ ...lead, monthlyVolume: "101-500" })).toBe(false);
  });

  it("validates facilities including required carrier and supported service", () => {
    expect(validateFacility(validFacility).valid).toBe(true);
    const invalid = validateFacility({ ...validFacility, services: [], carriers: [] });
    expect(invalid.errors).toEqual(expect.arrayContaining([
      "Facility facility-test: at least one service must be supported.",
      "Facility facility-test: at least one carrier must be listed.",
    ]));
  });

  it("validates team member names, roles, and countries", () => {
    expect(validateTeamMember(validMember).valid).toBe(true);
    const invalid = validateTeamMember({ ...validMember, name: "A", role: "driver" as TeamMember["role"] });
    expect(invalid.valid).toBe(false);
    expect(invalid.errors).toHaveLength(2);
  });
});
