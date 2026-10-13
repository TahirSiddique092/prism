# ADR-012 — Vercel deployment and CORS config (slice-23)

## Context

PRISM's frontend is built with Next.js (App Router) and deployed to Vercel, while the backend Flask API and datastores reside on an OCI VM (deployed in slice-22).

To protect the OCI Flask API from unauthorized cross-origin requests, browser abuse, and unauthorized third-party embeds, slice-23 requires configuring CORS on the Flask backend to strictly accept requests only from the Vercel domain, returning HTTP 403 Forbidden on all other origins. Furthermore, sensitive credentials (JWT_SECRET, database connection strings) must be strictly isolated from the Vercel environment and frontend bundle.

## Decisions

1. **Strict CORS Policy with HTTP 403 Enforcement**
   - Implemented custom CORS middleware in `backend/cors.py` registered via `register_cors_middleware(app)` in `backend/app.py`.
   - **Allowed Origins**:
     - Any origin matching `https://*.vercel.app` (covers production, branch previews, and deployment hashes).
     - Explicitly configured origins from `FRONTEND_URL`, `VERCEL_URL`, or `CORS_ALLOWED_ORIGINS`.
     - `http://localhost:3000` during testing or local development.
   - **Disallowed Origins**:
     - Any request providing an `Origin` header that does not match the whitelist is immediately rejected with **HTTP 403 Forbidden** (`{"error": "Forbidden", "message": "Origin not allowed by CORS policy"}`).
   - **Preflight `OPTIONS` Requests**:
     - Preflight requests from allowed origins return HTTP 204 No Content with `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`, and `Access-Control-Allow-Credentials: true`.
     - Preflight requests from disallowed origins return HTTP 403 Forbidden.
   - **Server-to-Server Requests**:
     - Requests without an `Origin` header (such as Next.js server route handlers, health probes, or direct curl) are permitted without CORS blocking.

2. **Next.js Server-Side Route Handler Proxy Architecture**
   - Browser client code communicates with Next.js route handlers (`/api/auth/*`, `/api/documents/*`, `/api/search`, `/api/analytics/*`) on the Vercel domain.
   - Route handlers extract the JWT from the `httpOnly` `prism_token` cookie, attach `Authorization: Bearer <token>`, and forward the call server-side to the Flask backend URL defined in `NEXT_PUBLIC_API_URL`.
   - This ensures:
     - Client JavaScript never has access to the JWT token or sensitive credentials.
     - Browser cookies remain protected with `httpOnly`, `sameSite: lax`, and `secure` in production.

3. **Complete Secret Isolation**
   - The Vercel deployment environment contains **only** `NEXT_PUBLIC_API_URL=http://<OCI_PUBLIC_IP>:5000`.
   - All datastore credentials (`MYSQL_URL`, `POSTGRES_URL`, `NEO4J_PASSWORD`, `REDIS_URL`, `MINIO_SECRET_KEY`) and `JWT_SECRET` are kept strictly on the OCI VM in the untracked `.env` file.
   - Audited the frontend bundle to guarantee zero secret leaks.

4. **Vercel Monorepo Configuration**
   - Added root [vercel.json](file:///Users/pavankishorm/Documents/My%20Projects/prism/vercel.json) orchestrating build commands (`npm run build --prefix frontend`) and output directory (`frontend/.next`).
   - Added [frontend/vercel.json](file:///Users/pavankishorm/Documents/My%20Projects/prism/frontend/vercel.json) to support both monorepo root imports and direct `frontend` root directory deployments.
   - Added [frontend/.env.example](file:///Users/pavankishorm/Documents/My%20Projects/prism/frontend/.env.example) and [deploy/vercel-setup.md](file:///Users/pavankishorm/Documents/My%20Projects/prism/deploy/vercel-setup.md).

## Out of Scope

- No custom domains in v1 (default `*.vercel.app` domain is used).
- No HTTPS on the OCI backend in v1 (HTTP port 5000 is used per slice specifications).

## Status

Accepted.
