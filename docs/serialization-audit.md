# API Serialization Audit

**Scope:** HTTP API endpoints implemented by the root Next.js App Router (`app/api/**`, including thin backoffice route copies), the Python FastAPI backend (`backend.main:app`), and its composed services (`services.main:app`). This audit distinguishes JSON contracts from downloads and explicitly records the response-model exception for no-content/file responses. `response_model=None` is used for FastAPI routes whose response is intentionally not a JSON DTO.

**Security rule:** registration and unauthenticated password flows do not return or echo email addresses, passwords, access tokens, reset tokens, password hashes, or token digests. Login returns its access token because authentication requires it. Authenticated `GET /auth/me` is the only user response that includes the user's email.

## FastAPI routes

| Endpoint | Original state | Current response schema / change | Result |
|---|---|---|---|
| `GET /health` | Raw status dictionary; no model. | `dict[str, str]`. | Explicit JSON response model. |
| `POST /auth/login` | Already used `TokenResponse`. | Retained `TokenResponse` (`access_token`, `token_type`); no email or password in response. | Explicit; credential input is separate. |
| `GET /auth/me` | Raw public-user dictionary plus profile. | `CurrentUserResponse` containing `UserPublic` fields and optional `ProfilePublic`. | Explicit; authenticated email allowed; password hash excluded. |
| `POST /users` | Returned `public_user`, including email. | `RegistrationResponse`: id, active state, role, timestamp only. | No email/token/hash echo. |
| `PUT /profiles/me` | Raw profile dictionary. | `ProfilePublic`. | Explicit output DTO separate from `ProfileUpdate`. |
| `POST /auth/forgot-password` | Raw message dictionary. | `MessageResponse`. | Generic anti-enumeration message only; no email or reset token. |
| `POST /auth/reset-password` | Raw message dictionary. | `MessageResponse`. | Generic success message only; no email or reset token. |
| `POST /auth/change-password` | Raw message dictionary. | `MessageResponse`. | No password/token in response. |
| `GET /candidates/` | Raw list of full TinyDB records. | `list[CandidateListItem]`; excludes notes and undeclared internal keys. | Explicit slim list DTO. |
| `GET /candidates/{candidate_id}` | Raw TinyDB record. | `CandidateRead`. | Explicit detail DTO, with notes. |
| `POST /candidates/` | Raw created record. | `CandidateRead`; request remains `CandidateWrite`. | Input/output separated. |
| `PATCH /candidates/{candidate_id}` | Raw updated record. | `CandidateRead`; request remains `CandidatePatch`. | Input/output separated. |
| `DELETE /candidates/{candidate_id}` | 204, no response model. | `response_model=None`, 204 No Content. | Explicit non-JSON response. |
| `GET /candidates/{candidate_id}/notes` | Raw notes list. | `list[CandidateNoteRead]`. | Explicit list DTO. |
| `POST /candidates/{candidate_id}/notes` | Raw note dictionary. | `CandidateNoteRead`; request remains `NoteCreate`. | Input/output separated. |
| `DELETE /candidates/{candidate_id}/notes/{note_id}` | 204, no response model. | `response_model=None`, 204 No Content. | Explicit non-JSON response. |
| `GET /inventory/products` | Already had `list[SKURead]`. | Retained `list[SKURead]`. | Existing explicit output schema. |
| `POST /inventory/products` | Already had `SKURead`. | Retained `SKURead`; request `SKUCreate`. | Existing input/output separation. |
| `GET /inventory/products/{product_id}` | Already had `SKURead`. | Retained `SKURead`. | Existing explicit output schema. |
| `POST /inventory/orders/inbound` | Already had `StockEntryRead`. | Retained `StockEntryRead`; request `StockEntryCreate`. | Existing input/output separation. |
| `POST /inventory/orders/outbound` | Already had `StockExitRead`. | Retained `StockExitRead`; request `StockExitCreate`. | Existing input/output separation. |
| `GET /inventory/orders` | Already had `list[InventoryOrderRead]`, including a full nested SKU and user UUID. | `list[InventoryOrderListItem]`; the nested product summary now contains only name/SKU, while movement fields displayed by the history table are retained. | Explicit, consumer-specific list DTO; keeps the user UUID because the table displays it. |
| `GET /suppliers` | Raw list; supplier schema conflicted with legacy seed records. | `list[SupplierListRead]`; includes id/name/country/categories/rate/currency/status/updated_at only. Legacy `services` is normalized to `categories`. | Explicit minimal directory list schema. |
| `GET /suppliers/{supplier_id}` | Raw supplier record. | `SupplierRead`. | Explicit full detail DTO. |
| `POST /suppliers` | Raw created record. | `SupplierRead`; request `SupplierInput`. | Input/output separated. |
| `PATCH /suppliers/{supplier_id}/rate` | Raw updated record. | `SupplierRead`; request `RateUpdate`. | Input/output separated. |
| `PATCH /suppliers/{supplier_id}/status` | Raw updated record. | `SupplierRead`; request `StatusUpdate`. | Input/output separated. |
| `DELETE /suppliers/{supplier_id}` | 204, no response model. | `response_model=None`, 204 No Content. | Explicit non-JSON response. |
| `GET /suppliers/categories/list` | Raw categories dictionary. | `SupplierCategoriesResponse`. | Explicit JSON response model. |
| `GET /incidents/analyses` | Raw list of full analyses. | `list[AnalysisListItem]`; metadata and record counts only. | Explicit compact list DTO. |
| `GET /incidents/analyses/{analysis_id}` | Raw analysis dictionary. | `AnalysisResult`. | Explicit full detail DTO; conflicting duplicate model definitions consolidated. |
| `POST /incidents/analyses` | Unrestricted dict input and raw result output. | `AnalysisCreateRequest` validates analyzer fields and nested metrics; response `AnalysisResult` filters unknown output fields. | Separate input/output DTOs; unknown compatibility fields are ignored. |
| `GET /incidents/analyses/{analysis_id}/export` | CSV `Response`, no model. | `response_model=None`; CSV download preserved. | Explicit non-JSON response. |
| `GET /api/incidents` | Raw manager incident list. | `list[IncidentListItem]` containing id/title/category/status/branch/created_at, matching the register UI. | Explicit minimal list DTO; TypeScript consumer type updated; error envelope stays unchanged. |
| `POST /api/incidents` | Raw manager record. | `IncidentResponse`; body is parsed/validated as `IncidentCreate`. | Separate create and read DTOs. |
| `GET /api/incidents/summary` | Raw summary dictionary with full overdue records. | `IncidentSummaryResponse`; overdue items use lean `IncidentSummaryListItem`. | Explicit summary with minimal nested items. |
| `GET /api/incidents/{incident_id}` | Raw manager record. | `IncidentResponse`. | Explicit output; custom errors retained. |
| `PATCH /api/incidents/{incident_id}/status` | Raw manager record. | `IncidentResponse`; request status is validated as `IncidentStatus`. | Explicit output and constrained input. |

## Next.js App Router routes

The Next.js routes return `NextResponse` JSON or file responses rather than FastAPI `response_model`s. Their serialization boundaries are the shared TypeScript domain types plus explicit response construction and runtime input validators. JSON error envelopes are not success DTOs and remain unchanged.

| Route(s) | Original state | Current response contract / change | Result |
|---|---|---|---|
| `GET /api/candidates` | JSON list result produced by `listCandidates`; no runtime response DTO. | Existing `listCandidates` projection is returned directly; `CandidateListResponse` is a compile-time consumer type, not a runtime filter. | Paginated list projection retained; no separate runtime serializer is applied. |
| `POST /api/candidates` | JSON candidate or error; runtime input validator. | `CandidateWriteInput` validation and `Candidate` response retained. | Input validation separate from stored/output record. |
| `GET /api/candidates/{id}` | Candidate object or error. | Candidate detail object from store; no separate read schema introduced. | Existing Next API contract retained. |
| `PATCH /api/candidates/{id}` | Candidate object or error. | Candidate record returned after status/stage validation. | Existing contract retained. |
| `PUT /api/candidates/{id}` | Candidate object or error. | Candidate record returned after write validation. | Existing contract retained. |
| `POST /api/candidates/{id}/notes` | Candidate with added note or error. | Existing candidate record response and validated note body. | Existing contract retained. |
| `DELETE /api/candidates/{id}/notes/{noteId}` | Candidate result or error. | Existing candidate record response. | Existing contract retained. |
| `POST /api/incidents/analyze` | `{analysis}` or `{errors}` JSON, analyzer payload accepted from Python subprocess. | `AnalyzeResponse` TypeScript contract and explicit store projection retained. | Upload validation/errors retained; Python FastAPI analysis models do not apply to this Next.js route. |
| `GET /api/incidents/results` | `{analyses}` or error. | `ResultsResponse` TypeScript contract. | Existing list/detail envelope retained. |
| `GET /api/incidents/results/export` | CSV download or JSON error. | CSV `NextResponse` retained. | Non-JSON response; no JSON DTO applies to successful download. |
| `GET /api/incidents/results/{id}/export` | CSV download or JSON error. | CSV `NextResponse` retained. | Non-JSON response; no JSON DTO applies to successful download. |
| `GET /api/incidents` | JSON manager list or error, with no route-level runtime response schema. | The Python FastAPI route now applies its compact `IncidentListItem`; the root Next.js route contract depends on the configured rewrite and does not filter responses by TypeScript type. | Runtime filtering occurs in the FastAPI service, not the Next.js type declaration. |
| `POST /api/incidents` | JSON created record or error. | Existing incident record contract and runtime validation retained. | Existing contract retained. |
| `GET /api/incidents/summary` | JSON summary or error, with no route-level runtime response schema. | Python FastAPI response uses `IncidentSummaryResponse`, with overdue incidents serialized as `IncidentSummaryListItem`; Next.js declaration is compile-time only. | Lean overdue data is enforced server-side. |
| `GET /api/incidents/{id}` | JSON record or error. | Existing incident record contract retained. | Existing contract retained. |
| `PATCH /api/incidents/{id}/status` | JSON updated record or error. | Existing status validation and incident record contract retained. | Existing contract retained. |

### Routes not included in runtime application

`uis/backoffice/app/api/**` and `uis/website/app/api/**` contain legacy/duplicate route files under nested app trees. They are not the root Next.js App Router's configured application entry (`app/`) and are not included in the root application endpoint list above. Confirm this remains true if deployment configuration is changed to build from either nested app directory.

## Verification

- Serialization-focused tests verify candidate and supplier unknown-field filtering, auth secret filtering, analysis response filtering, and manager incident filtering.
- Full Python test suite: `uv run pytest -q` (**112 passed** after the serialization changes).
- OpenAPI generation was verified independently for the backend, supplier, and incident FastAPI apps.
- Unified `services.main` OpenAPI generation requires `DATABASE_URL`; without it the app intentionally fails during inventory-service import.
- `npm run typecheck` and `git diff --check` pass after the serialization changes.

## Known contract notes

- Login necessarily returns an access token; all other unauthenticated auth flows return no email/token/password fields.
- Password reset tokens are sent through the configured out-of-band email link and are not returned by the API.
- Supplier detail/create/update outputs include operational contact fields when present; supplier lists intentionally omit them.
- Existing Next.js route handlers are runtime-validated selectively and do not support FastAPI's `response_model` decorator. Their TypeScript response types are not runtime filters unless response construction filters fields explicitly.
