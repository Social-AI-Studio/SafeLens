# SafeLens Auth Service (auth-service/)

A minimal OIDC provider for SafeLens, built with Next.js and Better Auth. This guide gets you running locally with Google OAuth and a registered client for the frontend.

## Requirements

- Node.js 20 LTS (or ≥ 18.18) and pnpm 8+
- Docker (for PostgreSQL)

## 1) Environment

```bash
cd auth-service
cp .env.example .env
```

Fill `.env` (local defaults):

```env
# Public URL of this service (must include /api/auth, no trailing slash)
NEXT_PUBLIC_BETTER_AUTH_URL=http://localhost:3001/api/auth
AUTH_BASE_URL=http://localhost:3001/api/auth

# Postgres for this service
DATABASE_URL=postgres://user:password@localhost:5433/safelens_auth_db

# Secret for Better Auth
BETTER_AUTH_SECRET=<run: openssl rand -hex 32>

# Google OAuth (required)
GOOGLE_CLIENT_ID=<from Google Cloud console>
GOOGLE_CLIENT_SECRET=<from Google Cloud console>
```

## 2) Database (Docker)

```bash
docker run --name safelens_auth_db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=safelens_auth_db \
  -p 5433:5432 \
  -v safelens_auth_data:/var/lib/postgresql/data \
  -d postgres:17.5
```

Ensure `DATABASE_URL` matches the credentials/port above.

## 3) Install & set up DB schema

Quick start (fresh install):

```bash
pnpm install
pnpm run db:push      # creates schema directly from src/db/schema.ts
```

Prefer migration‑driven setup (teams/CI/prod) instead:

```bash
pnpm install
pnpm run db:migrate   # applies versioned SQL in src/db/migrations/
```

## 4) Run the service

```bash
PORT=3001 pnpm dev      # http://localhost:3001
# or
pnpm build && PORT=3001 pnpm start
```

## 5) Google OAuth (required)

1. Google Cloud → APIs & Services → OAuth consent screen
    - Select "Get Started"
    - Fill in App name & user support email
    - Set "Audience" to External.
    - Fill in "Contact Information"
2. Select "Clients" -> "+ Create Client"
    - Application Type: Web application
    - Name: <Fill in app name>
    - Authorized JavaScript origins:
        - Dev: `http://localhost:3001`
        - Prod: `https://auth.example.com`
    - Authorized redirect URIs:
        - Dev: `http://localhost:3001/api/auth/callback/google`
        - Prod: `https://auth.example.com/api/auth/callback/google`
4. Put GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET into `.env` and restart.

## 6) Connect to Postgres

From host (psql):

```bash
psql "postgres://user:password@localhost:5433/safelens_auth_db"
```

Or inside the container:

```bash
docker exec -it safelens_auth_db psql -U user -d safelens_auth_db
```

Useful SQL (PostgreSQL; table name "user" is quoted):

```sql
-- Recent users
SELECT id, email, role FROM "user" ORDER BY created_at DESC LIMIT 20;

-- Promote yourself to ADMIN (required for /admin/apps)
UPDATE "user" SET role = 'ADMIN' WHERE email = 'you@example.com';
```

## 7) Register an OAuth client (recommended: CLI)

Local dev (frontend at http://localhost:3000):

```bash
pnpm run register-client -- \
  --name "SafeLens Frontend (local)" \
  --redirect "http://localhost:3000/api/auth/callback/socialai-studio-auth" \
  --type web
```

Important: The trailing path segment in the redirect (here `socialai-studio-auth`) is your provider ID. It must match the value of `AUTH_PROVIDER_ID` in `web/frontend/.env.example` (and your local `.env`). The default in this repo is `socialai-studio-auth`.

Production:

```bash
pnpm run register-client -- \
  --name "SafeLens Frontend" \
  --redirect "https://app.example.com/api/auth/callback/socialai-studio-auth" \
  --type web
```

Note: Ensure the provider ID used in the callback path (`/api/auth/callback/<provider-id>`) matches `AUTH_PROVIDER_ID` in the frontend environment.

Env alternative:

```bash
CLIENT_NAME="SafeLens Frontend" \
REDIRECT_URIS="https://app.example.com/api/auth/callback/socialai-studio-auth" \
CLIENT_TYPE=web \
pnpm run register-client
```

Copy the outputs into your consuming app (e.g., web/frontend/.env):

```env
AUTH_CLIENT_ID=...
AUTH_CLIENT_SECRET=...
AUTH_ISSUER_URL=https://auth.example.com/api/auth
```

## 8) Optional: Admin UI

If you prefer the UI, first sign in at http://localhost:3001/sign-in, promote your user to ADMIN (see step 6), then visit:

- http://localhost:3001/admin/apps/new (register a client; copy client_id/secret)

## 9) Verify

- OIDC Discovery: http://localhost:3001/api/auth/.well-known/openid-configuration
    - `issuer` will be the server ORIGIN (e.g., `http://localhost:3001`). This is expected.
    - Endpoints use `AUTH_BASE_URL` as base:
        - token_endpoint: `${AUTH_BASE_URL}/oauth2/token`
        - userinfo_endpoint: `${AUTH_BASE_URL}/oauth2/userinfo`
        - jwks_uri: `${AUTH_BASE_URL}/jwks`
- Sign‑in page: http://localhost:3001/sign-in

Issuer note
- Better Auth reports `issuer` as the origin even when `AUTH_BASE_URL` includes `/api/auth`. Your frontend config should set `AUTH_ISSUER_URL` to `${ORIGIN}/api/auth`; the app derives the issuer origin automatically.

OIDC compliance
- The legacy `/token` route is disabled and the JWT header is not set; use `/oauth2/token` and `/oauth2/userinfo`.
