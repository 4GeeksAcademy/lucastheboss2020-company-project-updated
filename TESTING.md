# Testing

## Setup

Install the project and its development test tools with uv:

```bash
uv sync
```

The `dev` dependency group includes pytest and pytest-cov. Tests use in-memory TinyDB tables and mock email delivery; they do not send email or write authentication test users to the application database.

## Run Tests

Run the complete Python suite from the repository root:

```bash
uv run pytest
```

Run the authentication coverage report:

```bash
uv run pytest backend/tests/test_auth_endpoints.py --cov=backend.auth --cov-report=term-missing
```

The authentication module coverage target is at least 70%. Existing auth service tests, password-reset tests, incident manager tests, and script error-path tests remain in the complete suite.

## Authentication Coverage

`backend/tests/test_auth_endpoints.py` exercises endpoint business logic directly rather than FastAPI/HTTP serialization. It covers access-token claims and expiry, current-user and admin guards, login, user registration, `/auth/me`, profile updates, forgot-password privacy behavior, reset-token expiry/reuse, and authenticated password changes.

The suite checks happy paths, edge cases, and failures such as duplicate users, invalid credentials, inactive accounts, malformed/expired tokens, missing profiles, email delivery failures, and invalid current passwords. Resend is mocked, and test users/tokens live only in TinyDB `MemoryStorage` fixtures.
