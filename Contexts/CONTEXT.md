# CONTEXT.md - TrackFlow

## Milestone 1: Your Company's Public Website

This project is a public corporate website and lead-capture experience for TrackFlow. Everything in the website, form, validation logic, and supporting TypeScript model must reflect the TrackFlow logistics domain.

## Your company

TrackFlow is a last-mile delivery and warehouse management company founded in 2009 in Los Angeles, United States. It operates in two markets: United States (Los Angeles) and Spain (Zaragoza). TrackFlow offers three services: warehouse management for e-commerce brands, last-mile delivery, and reverse logistics.

TrackFlow has approximately 130 employees and generates around 9 million euros in annual revenue. Its clients are mid-sized fashion, electronics, and cosmetics e-commerce brands that sell online.

## Your department and the problem you must solve

You work in the TrackFlow Tech unit, reporting directly to CTO Andres Kim. TrackFlow's current corporate website was built years ago by an external agency and is outdated. It does not reflect that the company operates in two countries, does not clearly explain the services, and gives interested companies no structured way to request information.

Miguel Torres, Commercial Director, needs a professional website that presents TrackFlow's services and captures leads from potential companies that want to outsource their logistics.

## Stakeholder

Miguel Torres, Commercial Director, needs a modern corporate website with:

- Clear explanation of services
- Coverage in both countries
- Lead-capture form with structured fields
- Responsive, accessible, SEO-optimized implementation
- TailwindCSS styling
- Complete validation

## Language scope

English is the base language for the website and form experience. Spanish support is optional as an enhancement because TrackFlow operates in the United States and Spain.

## Landing page content

The landing page must include these sections, in this order:

1. Header
2. Hero
3. Services
4. Coverage
5. Why TrackFlow
6. Contact
7. Footer

### Header

- Logo or name: TrackFlow
- Navigation: Home | Services | Coverage | Contact

### Hero

- Headline: "Logistics that scales with your e-commerce"
- Subheadline: "Warehouse management, last-mile deliveries, and reverse logistics in the United States and Spain. Over 15 years helping fashion, electronics, and cosmetics brands grow without worrying about operations."
- Call to action: Button "Request information" linking to the form

### Services

#### Warehouse Management

- Storage, picking and packing
- Real-time inventory
- We operate warehouses in Los Angeles and Zaragoza

#### Last-Mile Deliveries

- Certified carrier network in both countries
- Unified shipment tracking
- Incident and returns management

#### Reverse Logistics

- Complete returns management
- Inspection and reconditioning
- Integration with your sales platform

### Coverage

#### United States

- Warehouse in Los Angeles
- National coverage
- Carriers: UPS, FedEx, DHL

#### Spain

- Warehouse in Zaragoza
- Peninsular and island coverage
- Carriers: MRW, SEUR, DHL

### Why TrackFlow

- Binational operation: The only operator with own infrastructure in the United States and Spain
- +130 professionals dedicated to your logistics
- Own technology for total visibility of your inventory
- E-commerce specialization in fashion, electronics, and cosmetics

### Contact

- Email: comercial@trackflow.com
- Los Angeles: +1 213 555 0147
- Zaragoza: +34 976 123 456

### Footer

- © 2025 TrackFlow. All rights reserved.
- LinkedIn

## Information request form fields

The form must capture the following information:

| Field | Type | Validation | Required |
| --- | --- | --- | --- |
| Company name | text | Minimum 2 characters | Yes |
| Contact person | text | Minimum 2 words (first and last name) | Yes |
| Corporate email | email | Valid email format | Yes |
| Phone | tel | Format: +[country code] [number] | Yes |
| Company website | url | Valid URL format | No |
| Main operating country | select | United States / Spain / Both / Other | Yes |
| Product type | select | Fashion / Electronics / Cosmetics / Food / Other | Yes |
| Estimated monthly shipping volume | select | 0-100 / 101-500 / 501-2000 / 2000+ / Not sure | Yes |
| Services of interest | checkbox | Warehousing / Last mile / Reverse logistics (multiple) | Yes |
| Do you currently work with another 3PL? | radio | Yes / No / Evaluating options | Yes |
| Comments or specific needs | textarea | Maximum 500 characters | No |
| I accept the privacy policy | checkbox | Must be checked to submit | Yes |

## Specific validations

1. Company name: Minimum 2 characters
2. Contact person: Must contain at least first and last name
3. Email: Must be valid format, containing @ and domain
4. Phone: Must start with + followed by country code
5. Website: If provided, must be valid URL, starting with http:// or https://
6. Services of interest: At least one must be selected
7. Comments: Limit to 500 characters with visible counter
8. Privacy policy: Checkbox must be checked to submit

## Expected error messages

When a field does not meet validation, display these specific messages:

- Company name: "Company name must have at least 2 characters"
- Contact person: "Enter first and last name of contact"
- Email: "Enter a valid corporate email (example: name@company.com)"
- Phone: "Phone must include country code (example: +1 213 555 0147)"
- Website: "If you include website, it must be a valid URL"
- Country: "Select main operating country"
- Product type: "Select the type of product you handle"
- Monthly volume: "Select estimated monthly volume"
- Services of interest: "Select at least one service of interest"
- Current 3PL: "Indicate if you currently work with another logistics provider"
- Comments: "Comments cannot exceed 500 characters (X remaining)"
- Privacy policy: "You must accept the privacy policy to continue"

## Success message

When the form validates correctly and simulated submission completes, display:

Thank you for your interest in TrackFlow!

We have received your request. Our commercial team will review your information and contact you within the next 24-48 hours to schedule a call and learn about your logistics needs in detail.

If you have any urgent inquiry, write to us directly at comercial@trackflow.com

## Specific restriction

The form is designed for e-commerce companies looking to outsource their logistics, not for end consumers who want to track a package or make a return.

If the selected monthly volume is "0-100 shipments/month" and the Product type field is relevant, include this warning message:

"For volumes under 100 monthly shipments, our services might not be the most efficient solution. Are you sure you want to continue?"

## Required Schema.org markup

Implement this Schema.org markup on the landing page:

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "TrackFlow",
  "description": "Warehouse management and last-mile deliveries for e-commerce",
  "url": "https://trackflow.com",
  "foundingDate": "2009",
  "address": [
    {
      "@type": "PostalAddress",
      "addressCountry": "US",
      "addressLocality": "Los Angeles",
      "addressRegion": "California"
    },
    {
      "@type": "PostalAddress",
      "addressCountry": "ES",
      "addressLocality": "Zaragoza",
      "addressRegion": "Aragón"
    }
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "telephone": "+1-213-555-0147",
    "contactType": "sales",
    "availableLanguage": ["Spanish", "English"]
  },
  "sameAs": ["https://linkedin.com/company/trackflow"],
  "areaServed": [
    {
      "@type": "Country",
      "name": "United States"
    },
    {
      "@type": "Country",
      "name": "Spain"
    }
  ]
}
```

## Data model

The supporting TypeScript model represents TrackFlow logistics operations and lead qualification.

### LogisticsService

Represents one of TrackFlow's services.

Fields:

- id: string
- name: "warehouse-management" | "last-mile-delivery" | "reverse-logistics"
- baseMonthlyFee: number

### LeadRequest

Represents a company requesting information.

Fields:

- id: string
- companyName: string
- contactPerson: string
- corporateEmail: string
- phone: string
- companyWebsite?: string
- operatingCountry: "United States" | "Spain" | "Both" | "Other"
- productType: "Fashion" | "Electronics" | "Cosmetics" | "Food" | "Other"
- monthlyVolume: "0-100" | "101-500" | "501-2000" | "2000+" | "Not sure"
- servicesOfInterest: LogisticsServiceName[]
- current3pl: "Yes" | "No" | "Evaluating options"
- comments?: string
- privacyAccepted: boolean
- status: "new" | "qualified" | "contacted" | "not-fit"

### Facility

Represents an owned TrackFlow warehouse.

Fields:

- id: string
- city: "Los Angeles" | "Zaragoza"
- country: "United States" | "Spain"
- services: LogisticsServiceName[]
- carriers: string[]

### TeamMember

Represents a TrackFlow employee.

Fields:

- id: string
- name: string
- role: "warehouse-operator" | "route-coordinator" | "account-manager" | "support-specialist"
- country: "United States" | "Spain"

### Supplier

Represents a third-party logistics supplier that TrackFlow partners with.

Fields:

- id: integer
- name: string
- country: "United States" | "Spain"
- services: string[]  (TrackFlow service categories: "warehouse-management", "last-mile-delivery", "reverse-logistics")
- rate_per_shipment: number  (positive only, represents cost per shipment)
- currency: "USD" | "EUR"  (United States suppliers use USD, Spain suppliers use EUR)
- status: "active" | "suspended"
- updated_at: string  (ISO 8601 timestamp, system-generated)

## Reports to generate

1. Count leads by service of interest
2. Count leads by operating country
3. Count leads by product type
4. Count leads by monthly volume
5. Identify low-volume leads that should receive the warning
6. Count leads by current 3PL status

## Incident Analysis — Expected Results

When running the analysis script against the test CSV files, the output must match these values.

### TRF (Tracking Record Format) Column Specification

The incident analysis script uses the **TrackFlow TRF (Tracking Record Format)** for tracking/logistics records. Columns:

| Column | Type | Required | Validation |
|---|---|---|---|
| `tracking_id` | string | Yes | Non-empty identifier (e.g. `TF-00001`) |
| `carrier` | string | Yes | Must be one of: `UPS`, `FedEx`, `DHL`, `MRW`, `SEUR` |
| `category` | string | Yes | Must be one of: `LOST_PARCEL`, `DELAYED`, `DAMAGED`, `RETURNED`, `WRONG_ITEM`, `ADDRESS_ISSUE`, `MISSING_LABEL`, `CUSTOMER_CANCELLATION` |
| `status` | string | Yes | Must be one of: `open`, `closed`, `exception` |
| `origin` | string | Yes | Non-empty origin city/location |
| `destination` | string | Yes | Non-empty destination city/location |
| `shipment_date` | date | Yes | Format: `YYYY-MM-DD` |
| `delivery_date` | date | No | Format: `YYYY-MM-DD` if provided |
| `weight_kg` | number | Yes | Must be a positive number (> 0) |
| `declared_value` | number | Yes | Must be a positive number (> 0) |
| `customer_name` | string | Yes | Non-empty customer name |
| `customer_email` | string | Yes | Valid email format (`@` and domain with `.`) |
| `notes` | string | No | Free text |

### File: `data/incidents-trf-official.csv` (100 records, 95 valid / 5 invalid)

| Metric | Expected Value |
|---|---|
| Total records processed | 100 |
| Valid records | 95 |
| Invalid records | 5 |
| Carrier — DHL | 19 |
| Carrier — FEDEX | 22 |
| Carrier — MRW | 15 |
| Carrier — SEUR | 15 |
| Carrier — UPS | 24 |
| Category — ADDRESS_ISSUE | 10 |
| Category — CUSTOMER_CANCELLATION | 6 |
| Category — DAMAGED | 14 |
| Category — DELAYED | 19 |
| Category — LOST_PARCEL | 17 |
| Category — MISSING_LABEL | 7 |
| Category — RETURNED | 11 |
| Category — WRONG_ITEM | 11 |
| Status — Closed | 46 |
| Status — Exception | 17 |
| Status — Open | 32 |
| Average Declared Value (€) | 219.78 |

### Error types expected in `incidents-trf-official.csv` (5 invalid records):

1. Invalid carrier (`INVALID_CARRIER`)
2. Invalid category (`INVALID_CATEGORY`)
3. Missing required field (status)
4. Missing required fields (origin, customer_name) — multi-error
5. Invalid weight_kg (zero)

### Legacy files (backward compatibility — `data/incidents-test-100.csv` and `data/incidents-test-invalid.csv`)

These legacy test files use the old format with generic complaint fields. They are preserved for reference but the official analysis uses the TRF format above.

#### File: `data/incidents-test-100.csv`

| Metric | Expected Value |
|---|---|
| Total records processed | 25 |
| Valid records | 25 |
| Invalid records | 0 |
| Category — Complaints | 10 |
| Category — Requests | 8 |
| Category — Operational Failures | 7 |
| Status — Open | 8 |
| Status — Closed | 16 |
| Status — Discarded | 1 |
| Average Satisfaction Index | 6.81 |

#### File: `data/incidents-test-invalid.csv`

| Metric | Expected Value |
|---|---|
| Total records processed | 10 |
| Valid records | 0 |
| Invalid records | 10 |
| Category — Complaints | 0 |
| Category — Requests | 0 |
| Category — Operational Failures | 0 |
| Status — Open | 0 |
| Status — Closed | 0 |
| Status — Discarded | 0 |
| Average Satisfaction Index | N/A |

#### Error types expected in `incidents-test-invalid.csv`:

1. Invalid category value (`invalid_category`)
2. Invalid status value (`bad_status`)
3. Missing required field (category)
4. Missing required field (description)
5. Missing required fields (email, date)
6. Invalid email format
7. Invalid phone format
8. Invalid date format
9. Invalid satisfaction score (out of range)
10. Multiple validation failures in one record
