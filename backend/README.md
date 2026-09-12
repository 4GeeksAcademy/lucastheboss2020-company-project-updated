# TrackFlow FastAPI backend

This backend implements stateless JWT authentication and stores users/profiles in TinyDB only. It does not create SQLModel, PostgreSQL, or Supabase user/profile tables.

## Run

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET_KEY='use-a-long-random-secret'
export ACCESS_TOKEN_EXPIRE_MINUTES=30
uvicorn backend.main:app --reload --app-dir ..
```

Open `/docs`, register with `POST /users`, log in at `POST /auth/login`, click **Authorize**, and use the bearer token on protected operations.

`POST /candidates` remains public for website lead capture. Candidate listing, detail, updates, and note operations require authentication. User/profile/auth-me routes are protected as specified.

The legacy Next.js candidate API follows the same policy: `POST /api/candidates` remains public, while its GET, PATCH, PUT, note POST, and note DELETE handlers require an HS256 bearer token signed with the same `JWT_SECRET_KEY`. Configure that variable in the Next.js runtime as well as the FastAPI runtime.

TinyDB data is written to `backend/data/app.json`; this directory should not be committed in production.
