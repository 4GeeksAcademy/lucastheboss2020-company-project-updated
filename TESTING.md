# Testing

## Setup

Install the project and its development test tools with uv:

```bash
uv sync
```

The `dev` dependency group includes pytest and pytest-cov. Tests use in-memory TinyDB tables and mock email delivery; they do not send email or write authentication test users to the application database.

## Authentication Test Plan

Each authentication endpoint is covered with success, edge, and failure cases. Tests invoke endpoint functions and auth/service logic directly; they do not assert FastAPI serialization internals.

| Endpoint or logic | Success | Edge case | Failure |
|---|---|---|---|
| `POST /auth/login` | Correct password returns a token for the expected user | Inactive account | Unknown email or wrong password returns 401 |
| `GET /auth/me` | Returns public user fields and profile | Missing profile | Invalid/expired token rejected by current-user guard |
| `POST /users` | Creates user, password hash, and profile | Optional profile values omitted | Duplicate email returns 409; invalid email/short password rejected |
| `PUT /profiles/me` | Updates supplied fields | Missing profile is created; omitted fields preserved | Invalid profile fields rejected |
| `POST /auth/forgot-password` | Registered active account queues a reset link | Unknown/inactive addresses get the same response | Email or token-setup failure remains enumeration-neutral |
| `POST /auth/reset-password` | Valid token changes password and is consumed | Expired or tampered token | Reused/wrong-purpose token and short password rejected |
| `POST /auth/change-password` | Current password verified and new hash stored | Outstanding reset tokens invalidated | Wrong current password or short replacement rejected |

The current plan is reflected in `backend/tests/test_auth_endpoints.py`; existing `backend/tests/test_password_resets.py` supplements it with reset replay, expiry, delivery-failure, and status-code checks.

## Run Tests

Run the complete Python suite from the repository root:

```bash
uv run pytest
```

Run the authentication coverage report:

```bash
uv run pytest backend/tests/test_auth_endpoints.py --cov=backend.auth --cov-report=term-missing
```

The authentication module coverage target is at least 70%. Verified result: `backend.auth` reached **100% statement and branch coverage** (29 statements, 6 branches). The complete `uv run pytest` suite last passed with **86 tests**.

Run the TypeScript utility unit tests with Jest:

```bash
npm test
npm run test:coverage
```

`src/utils/validations.test.ts` covers the existing TrackFlow service, lead, facility, team-member, and low-volume validation utilities. The current Jest coverage run reported **83.87% statements** and **51.61% branches** for `validations.ts`.

## Authentication Coverage

`backend/tests/test_auth_endpoints.py` exercises endpoint business logic directly rather than FastAPI/HTTP serialization. It covers access-token claims and expiry, current-user and admin guards, login, user registration, `/auth/me`, profile updates, forgot-password privacy behavior, reset-token expiry/reuse, and authenticated password changes.

The suite checks happy paths, edge cases, and failures such as duplicate users, invalid credentials, inactive accounts, malformed/expired tokens, missing profiles, email delivery failures, and invalid current passwords. Resend is mocked, and test users/tokens live only in TinyDB `MemoryStorage` fixtures.

## Inventory API (Milestone 5)

The inventory service composes the existing TinyDB-authenticated backend with SQLModel inventory tables in Supabase. The inventory tests use an isolated in-memory SQLite database and never connect to the configured Supabase database.

Start the combined API from the repository root:

```bash
uv run --env-file backend/.env uvicorn services.main:app --reload
```

Seed the local development inventory after registering a TinyDB user:

```bash
uv run --env-file backend/.env seed-inventory
```

The inventory test suite is part of `uv run pytest`. It covers all six protected routes, foreign keys, computed stock per warehouse, inbound/outbound records, tracking-number rules, insufficient-stock rejection without a write, and safe seed behavior. `DATABASE_URL` is loaded from the local env file and is never logged by tests or scripts.

## Test-Plan Notes

During the test-first setup, the initial `uv run pytest` attempt exposed that the root uv environment lacked auth test dependencies (`python-jose`, passlib/bcrypt, email validation, and the FastAPI test client). These were added to the development-only dependency group; production dependencies remain unchanged, and the root command now passes.
