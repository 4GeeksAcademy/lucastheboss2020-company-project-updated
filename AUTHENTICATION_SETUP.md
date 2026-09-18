# TrackFlow authentication setup

## Configure the API

Copy `.env.example` to `.env.local` and set the secured API base URL:

```env
NEXT_PUBLIC_API_URL=https://your-api.example.com
```

Do not include `/auth/login` in the value. Restart Next.js after changing environment variables:

```bash
npm run dev
```

## Expected API contract

- `POST /users`: accepts `email`, `password`, and optional `name`, `phone`, `address`.
- `POST /auth/login`: accepts `email` and `password`; returns `{ "token": "..." }` or `{ "access_token": "..." }`.
- `GET /auth/me`: returns a flat user/profile object or `{ user, profile }`.
- `PUT /profiles/me`: accepts `{ name, phone, address }` and requires the Bearer token.

Protected requests send:

```http
Authorization: Bearer <jwt>
```

## Acceptance test

1. Register and confirm `POST /users`, then `POST /auth/login` succeed.
2. Confirm `localStorage.getItem('trackflow_access_token')` is populated.
3. Remove the token and visit `/candidates`, `/candidates/new`, `/candidates/<id>`, `/account/profile`, and `/uis/backoffice`; each must redirect to `/login`.
4. With no token, confirm `/` and `/uis/website` remain public.
5. Open `/account/profile`, verify email and profile fields, edit them, and confirm `PUT /profiles/me` succeeds.
6. Log out and confirm the token is removed and the browser is redirected to `/login`.
7. Replace the token with an invalid value; a protected API `401` must clear storage and redirect to `/login`.

The API must allow the browser origin (normally `http://localhost:3000`) and the `Authorization` request header through CORS.
