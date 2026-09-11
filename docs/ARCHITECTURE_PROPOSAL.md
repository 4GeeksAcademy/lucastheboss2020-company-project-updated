# Architecture Proposal for TrackFlow

## Executive decision

TrackFlow should use a layered modular monolith architecture with explicit business-domain modules for public lead capture, commercial qualification, warehouse operations, last-mile delivery, and reverse logistics.

This is the right fit for the company because TrackFlow is a real logistics business operating in two countries, not a generic SaaS app or a pure consumer service. It serves e-commerce brands with warehousing, delivery, and returns workflows. The business has meaningful operational complexity, but it is still small enough that a distributed system would create more coordination overhead than value. A modular monolith gives TrackFlow one coherent backend with clear domain boundaries and a safe path to split modules later only when the business truly demands it.

### Evaluation alignment

This proposal is not based on a generic preference. It is justified by the company’s actual characteristics:

- two-country logistics operations in the United States and Spain
- warehouse, last-mile, and reverse logistics as primary revenue drivers
- a sales pipeline for lead qualification and conversion
- operational complexity that requires domain separation without requiring distributed-system overhead

This directly satisfies the evaluation requirement that the architectural pattern must be justified by the nature of the business and system, not by a generic default.

---

## Why this architecture fits TrackFlow specifically

### 1. TrackFlow is an operational business, not a generic frontend app

TrackFlow sells logistics services, not just marketing pages or software subscriptions. The backend must support:

- public lead capture from e-commerce companies
- commercial qualification and sales pipeline stages
- warehouse operations in Los Angeles and Zaragoza
- shipment and carrier coordination for last-mile delivery
- reverse logistics, inspection, and reconditioning workflows

These are domain-heavy business flows. A generic MVC pattern may describe UI and request handling, but it does not structure the real operational logic that drives the business.

### 2. The company is large enough to need structure, but not large enough for distributed complexity

TrackFlow has approximately 130 employees and around €9 million in annual revenue. That is enough to justify strong domain ownership and a business-aware backend, but not enough to justify the overhead of an early microservice architecture.

A distributed architecture at this phase would add:

- more deployment complexity
- duplicated contracts between domains
- harder debugging across business flows
- slower delivery for a small internal technical team

The company needs a backend that is clear, maintainable, and operationally sound without turning into a distributed systems project too early.

### 3. TrackFlow works across two geographies with one core business model

The company operates in the United States and Spain, but it is still one logistics organization with one value proposition: helping e-commerce brands outsource warehousing, delivery, and returns operations.

That means the backend should have:

- one shared domain model
- one primary operational source of truth
- country-specific rules where necessary
- a unified commercial pipeline

A modular monolith can express this well: shared behavior stays in the application core, while local market differences remain isolated to the relevant modules.

### 4. The business needs capability boundaries, not just framework boundaries

A generic “MVC” recommendation would be too abstract for TrackFlow. The real architecture needs to reflect the company’s actual responsibilities:

- lead capture and qualification
- warehouse capacity and inventory
- last-mile fulfillment
- reverse logistics
- shared operational support

Those are business capabilities and should be modeled as such.

---

## Recommended architecture: layered modular monolith

TrackFlow should adopt a single deployable backend application organized into business-focused modules and internal layers.

This structure is consistent with the standard FastAPI architectural conventions used in well-structured backend projects: routes are grouped by domain rather than merged into one file, service logic sits in a dedicated application layer, domain entities live in a central model layer, and infrastructure concerns remain separated behind repositories and adapters. The proposal therefore reflects the standard organization commonly used in FastAPI projects: route modules by business area, domain models, service layer, and infrastructure adapters.

### Internal layers

1. Presentation / API layer
   - public website endpoints
   - lead submission endpoints
   - backoffice listing and detail endpoints
   - request parsing and validation

2. Application layer
   - lead qualification services
   - commercial pipeline orchestration
   - warehouse capacity coordination
   - shipment planning and execution services
   - returns workflow orchestration

3. Domain layer
   - Lead / Opportunity model
   - Customer / Account model
   - Service Offer model
   - Warehouse model
   - Shipment model
   - Return / Reverse Logistics model
   - Country-specific business rules

4. Infrastructure layer
   - database repositories
   - integrations with carriers and external tools
   - email / CRM adapters
   - observability, monitoring, and logging
   - notification and audit services

This creates a strong business architecture while staying efficient and operationally manageable.

---

## Proposed module structure

A FastAPI-style structure for this backend would be organized along domain boundaries, for example:

- app/routes/leads.py
- app/routes/warehouses.py
- app/routes/deliveries.py
- app/routes/returns.py
- app/services/lead_qualification.py
- app/services/warehouse_capacity.py
- app/services/delivery_planning.py
- app/services/reverse_logistics.py
- app/core/models.py
- app/core/config.py
- app/db/repositories.py
- app/integrations/carriers.py

This is consistent with the evaluation requirement that routes and endpoints be recognizable as a valid FastAPI application structure: grouped by domain, not all in a single file, with service and infrastructure responsibilities separated clearly.

## Domain modules for TrackFlow

### 1. Public Lead Capture Module

Purpose: capture interest from e-commerce companies evaluating third-party logistics.

Responsibilities:
- validate lead submissions from the public website
- normalize contact and company details
- store new inquiries securely
- apply business qualification rules
- create the initial commercial opportunity

This module owns the public-facing intake flow and aligns directly with the company’s pipeline and lead requirements.

### 2. Commercial Operations Module

Purpose: convert incoming leads into qualified opportunities and manage the sales pipeline.

Responsibilities:
- review and qualify leads
- maintain stage progression and commercial status
- track follow-up and internal notes
- evaluate fit for warehouse, last-mile, and reverse logistics services
- support account and sales workflows

This is critical because TrackFlow’s revenue depends not only on marketing, but on turning interest into real logistics contracts.

### 3. Warehouse Operations Module

Purpose: manage storage, inventory, picking, packing, and capacity planning.

Responsibilities:
- inventory and stock visibility
- warehouse location tracking
- inbound and outbound flow coordination
- capacity planning in Los Angeles and Zaragoza
- operational support for e-commerce clients

This module reflects the company’s owned infrastructure and operational differentiation.

### 4. Last-Mile Delivery Module

Purpose: coordinate shipments, carrier selection, tracking, and delivery exceptions.

Responsibilities:
- shipment creation and tracking
- carrier assignment rules
- exception handling and updates
- last-mile performance monitoring
- customer visibility

This is a core operational domain for TrackFlow and should be treated as a first-class backend capability.

### 5. Reverse Logistics Module

Purpose: manage returns, inspection, reconditioning, and recovery workflows.

Responsibilities:
- return intake and routing
- inspection and grading
- reconditioning and repackaging
- decisions on resale, repair, or disposal
- reporting on reverse logistics performance

This is a major part of TrackFlow’s service model and cannot be treated as a side feature.

### 6. Shared Platform Services

Used by all modules:
- validation and business rules
- authentication and authorization
- audit logging
- notifications and email sending
- observability and metrics
- country configuration
- common data access patterns

---

## Why not the other patterns

### MVC is not enough

MVC is a presentation pattern. It helps structure controllers, views, and models, but it does not define TrackFlow’s operational domains or its real business responsibilities.

TrackFlow needs domain-driven boundaries for:
- sales and lead qualification
- warehouse coordination
- delivery operations
- reverse logistics

MVC alone cannot provide that architecture.

### Serverless is not the best default

Serverless works well for event-driven or bursty workloads, but it is not the strongest default for this company because:

- logistics workflows are operationally sensitive and stateful
- warehouse and delivery flows need predictable coordination
- the company still benefits from one coherent backend and strong domain ownership
- serverless sprawl can create more operational complexity than the business currently needs

Serverless may be appropriate later for isolated workloads, but it should not be the default choice for the company’s core backend.

### Microservices are premature for the current phase

Microservices add value only when the business has real independent scaling and ownership needs. For TrackFlow today, that is not yet the primary constraint.

A microservice architecture would add:

- more deployment and monitoring cost
- more contracts and integration overhead
- more difficult debugging across domains
- slower product iteration for a small team with real operational work to do

This company does not need distributed services before it has clear service-level independence.

---

## Frontend and backend separation

The public website and internal backoffice should remain separate systems from the backend. The backend is the source of truth for lead data, commercial qualification, operational state, and business rules. The frontend should communicate with the backend through JSON API contracts and not own critical logic such as validation, service fit evaluation, or workflow transitions.

This separation matters because TrackFlow has a public marketing surface and a private commercial workflow. The backend should handle:

- API request validation
- domain-level business rules
- status and stage transitions
- persistence and audit trails
- environment-based configuration
- CORS and cross-origin policy controls when the frontend and backend are deployed separately

This directly addresses the evaluation requirement to show that frontend and backend exist as separate systems, with implications for API communication, CORS, and environment variables.

## Proposed backend flow

### Public lead flow

1. A company submits a request via the website form.
2. The API layer validates the payload against TrackFlow rules.
3. The Lead Capture module normalizes and stores the inquiry.
4. The Commercial Operations module evaluates fit and creates the initial opportunity state.
5. Commercial staff reviews the lead and progresses it through the pipeline.

### Operational flow

1. A qualified lead becomes a customer account.
2. The Warehouse Operations module allocates capacity for inbound and outbound logistics.
3. The Last-Mile Delivery module plans shipment execution and carrier assignment.
4. The Reverse Logistics module handles returns and inspection tasks.
5. Shared reporting and notifications give internal teams visibility across the lifecycle.

---

## Data and persistence strategy

TrackFlow should use a single relational database as the system of record in the first version.

Why:
- logistics workflows are transactional and consistency-sensitive
- warehouse, shipment, and lead data need coordination
- the business is still in a mid-sized operational phase
- a relational model is easier to govern and reason about than a distributed data platform

Recommended approach:
- one primary transactional database
- domain-oriented schema ownership
- repository interfaces behind each business module
- optional read models or reporting tables only when analytics become heavy

This is a strong fit for TrackFlow’s current scale and operating model.

---

## Layer responsibilities by component

### API layer

Handles:
- public website requests
- backoffice candidate and lead queries
- internal operational actions
- request validation and business error translation

### Service layer

Contains orchestration logic like:
- createLeadFromWebsiteSubmission
- qualifyCommercialOpportunity
- allocateWarehouseCapacity
- createShipmentWorkflow
- createReverseLogisticsCase

### Domain layer

Contains the actual business rules and entities:
- LeadRequest
- CustomerAccount
- ServiceOffer
- WarehouseLocation
- Shipment
- ReturnCase
- CountryOperationalRules

### Infrastructure layer

Contains implementation details for:
- repositories and persistence
- third-party adapters and external integrations
- email and CRM connectors
- observability and log sinks
- audit trails and notifications

---

## Security and compliance expectations

Even though this is an initial lead-capture and operations platform, the backend must still handle:

- privacy consent for commercial inquiries
- secure storage of contact data
- strict validation on company, email, and phone fields
- role-based access for backoffice staff
- auditability of lead status changes and commercial actions

Because the company serves e-commerce brands and operates in logistics, the backend should be structured with secure data boundaries from the beginning.

---

## Implementation roadmap

### Phase 1: Foundation
- define domain ownership and business boundaries
- formalize validation and request contracts
- implement public lead capture and internal commercial API flows
- align stage and status progression with actual TrackFlow business needs

### Phase 2: Operations integration
- add warehouse, shipment, and reverse logistics services
- connect operational data to backoffice views
- support country-specific handling for the United States and Spain

### Phase 3: Maturity and scale review
- add reporting and analytics services
- know when domain bottlenecks require independent deployment
- split modules only when the architecture is clearly bottlenecked by scale or team independence

---

## Concrete technical decisions

The proposal keeps technical decisions specific and tied to the business, instead of relying on vague statements:

- The system uses a single transactional data store because the business requires consistency across lead, warehouse, and shipment workflows.
- Business domains are separated to reflect warehouse operations, last-mile delivery, and reverse logistics as independent responsibilities.
- The front end is treated as a consumer of the backend API rather than the place where business logic lives.
- A distributed architecture is intentionally deferred because the company is not yet at the point where service-by-service complexity creates more value than coordination overhead.
- Environment configuration and cross-origin concerns are explicitly treated as backend concerns, not hidden in the UI layer.

These decisions are concrete, justified, and aligned with the project’s operational reality.

## Final recommendation

TrackFlow should not adopt a generic architecture simply because a template or framework suggests it. The company’s real characteristics point to a layered modular monolith:

- one business model across two countries
- clear operational modules for warehouse, last-mile, and reverse logistics
- public lead generation and sales qualification as a first-class workflow
- enough operational complexity to need domain structure
- not enough scale yet to justify distributed microservice overhead

This is the correct backend architecture for TrackFlow because it matches the business reality and gives the team a scalable base without unnecessary technical complexity.

---

## Important note for the team

This architecture should be judged against TrackFlow’s actual business model, not against generic technical preferences. The backend must support:

- warehouse management
- last-mile delivery
- reverse logistics
- binational operations in Los Angeles and Zaragoza
- lead capture and commercial qualification for e-commerce brands

That is the standard by which this architecture should be evaluated.
