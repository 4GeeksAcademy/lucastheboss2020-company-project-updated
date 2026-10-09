# TrackFlow Backend

FastAPI + TinyDB backend for authentication and candidate CRUD.

## Setup

```bash
cd backend
cp .env.example .env   # set JWT_SECRET_KEY and RESEND_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload --env-file .env
```

Configure `RESEND_API_KEY` with a Resend API key and set
`PASSWORD_RESET_FROM_EMAIL` to a sender verified with Resend before sending
reset emails. Never commit `.env` or place API keys in frontend code. The
sample values in `.env.example` are placeholders. Reset links use
`FRONTEND_BASE_URL` and expire after `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`
(30 minutes by default).

## API

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | — | Health check |
| `/auth/login` | POST | — | Returns JWT Bearer token |
| `/auth/me` | GET | 🔒 | Current user profile |
| `/auth/forgot-password` | POST | — | Sends a reset link when the address is registered; always returns the same confirmation |
| `/auth/reset-password` | POST | — | Sets a password with a signed, expiring, single-use token |
| `/auth/change-password` | POST | 🔒 | Changes password after verifying the current password |
| `/users` | POST | — | Registers a user |
| `/profiles/me` | PUT | 🔒 | Updates the current user's profile |
| `/candidates/` | GET | 🔒 | List candidates |
| `/candidates/` | POST | 🔒 | Create candidate |
| `/candidates/{id}` | GET | 🔒 | Get candidate |
| `/candidates/{id}` | PATCH | 🔒 | Update candidate |
| `/candidates/{id}` | DELETE | 🔒 | Delete candidate |
| `/candidates/{id}/notes` | GET | 🔒 | List notes |
| `/candidates/{id}/notes` | POST | 🔒 | Add note |
| `/candidates/{id}/notes/{noteId}` | DELETE | 🔒 | Delete note |

🔒 = requires `Authorization: Bearer <token>`

## Milestone 5 Inventory API

The inventory API composes this FastAPI app, so auth remains backed by the existing TinyDB users while inventory records use Supabase PostgreSQL through SQLModel. Keep `DATABASE_URL` in the local environment file; do not commit or print it.

Start the combined application from the repository root:

```bash
uv run --env-file backend/.env uvicorn services.main:app --reload
```

Seed the local development inventory after registering an active TinyDB user:

```bash
uv run --env-file backend/.env seed-inventory
```

All `/inventory` routes require a bearer token. Stock is calculated per SKU and warehouse from inbound entries minus outbound exits; it is never stored or set directly. The inventory tests use isolated SQLite and never connect to Supabase.