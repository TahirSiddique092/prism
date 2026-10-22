# ADR-015: Hybrid deployment — local compute, managed data services

## Status
Accepted. Supersedes ADR-014 (local-only docker-compose).

## Context
ADR-014 ran the entire stack — frontend, backend, MySQL, Postgres/pgvector,
Neo4j, Redis, and MinIO — locally via `docker compose up`. On resource-constrained
machines that is ~4–6 GB of RAM across seven containers *plus* the in-process
`sentence-transformers` model, which is too heavy to run reliably alongside five
datastores.

The earlier cloud explorations (OCI, then Hugging Face Spaces) failed for the
opposite reason: free hosts large enough to run the embedding model in-process
require a paid plan or a credit card.

## Decision
Split the system by cost profile:

- **Run locally in Docker** only the two components that are either compute-heavy
  or trivial to host: the **Flask backend** (which loads the
  `all-MiniLM-L6-v2` model in-process) and the **Next.js frontend**. The frontend
  reaches the backend over the compose network (`API_URL=http://backend:5000`);
  nothing is publicly exposed.
- **Offload every stateful service** to a managed free tier, configured entirely
  through the backend's `.env`:
  - MySQL → **Aiven**
  - Postgres + pgvector → **Neon**
  - Neo4j → **Neo4j Aura**
  - Redis → **Upstash** (`rediss://` TLS)
  - Object storage (S3-compatible) → **Neon Object Storage**
- The public **landing page** (static Next.js site in `landing/`) stays on
  **Vercel**, unchanged and separate from this stack.

The frontend is intentionally kept local rather than on Vercel: a cloud frontend
would need a public HTTPS tunnel back to the local backend, adding a moving part
for no benefit. The Next.js standalone container is small, so running it locally
costs almost nothing.

## Consequences
- Local footprint drops to **two containers** (backend + frontend); the embedding
  model gets the host's RAM/CPU instead of competing with five datastores.
- The app is reachable only on the operator's machine (`http://localhost:3000`);
  the only always-on public artifact remains the Vercel landing page.
- The app now depends on five external accounts and their free-tier quotas /
  cold-start behavior. All backend modules already degrade or fail fast when a
  service is unreachable (short Neo4j timeouts; Redis cache misses are swallowed).
- Because `PRISM_ENV=production`, a strong `JWT_SECRET` is enforced at startup and
  `CORS_STRICT=true` trusts only `FRONTEND_URL` (`http://localhost:3000`).

## Implementation
- `docker-compose.yml`: removed the `mysql`, `postgres`, `neo4j`, `redis`, and
  `minio` services (and their volumes / `depends_on`). The `backend` service now
  loads all connection strings and secrets via `env_file: .env` — this also fixes
  a latent bug where the old `environment:` whitelist passed only `MINIO_*` vars,
  so managed `S3_*` credentials never reached boto3.
- `.env.example` documents the managed-service connection-string template;
  `frontend/.env.example` documents the two compose-provided frontend vars.
- Storage/DB/graph/cache code is unchanged — it was already provider-agnostic
  (`storage.py` reads `S3_*`, DB modules read `POSTGRES_URL`/`MYSQL_URL`, etc.).

## Open items
- MySQL TLS: `auth/db.py` and `db/migrate.py` parse `MYSQL_URL` and drop the
  `?ssl-mode=REQUIRED` query param. mysql-connector-python negotiates TLS by
  default, so Aiven connects, but if a future driver change tightens this, pass
  SSL explicitly. Verify on first `docker compose up`.
