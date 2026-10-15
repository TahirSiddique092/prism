# ADR-014: Local-only delivery via docker-compose (no cloud deployment)

## Status
Accepted. Supersedes the earlier cloud-deployment explorations (OCI VM, then
Hugging Face Spaces + managed free tiers), whose ADRs and deploy artifacts have
been removed as no longer relevant.

## Context
PRISM is a mini DBMS course project. We explored deploying the backend to a free
cloud host — an OCI VM, then Hugging Face Spaces with managed free-tier
databases. In practice every path hit a wall: free hosts large enough to run the
in-process `sentence-transformers` model now require a paid plan (Hugging Face
Spaces Docker) or a credit card (Koyeb, Fly, Google Cloud Run, OCI signup), and
we did not want to supply card details or pay.

## Decision
**Do not deploy the application to the cloud.** Instead:

1. The entire stack — Next.js frontend, Flask backend, MySQL, pgvector/Postgres,
   Neo4j, Redis, and MinIO — runs locally with a single command:
   `docker compose up`. A fresh clone "just works" with no external accounts.
2. A small **landing page** (a standalone Next.js site in `landing/`, statically
   exported and deployed separately, e.g. on Vercel) presents the project and
   links to the GitHub repo with the clone-and-run instructions.

The backend keeps the simple Flask development server (`python app.py`) — it is
only ever run locally, so a production WSGI server is unnecessary.

## Consequences
- No third-party database/storage/compute accounts, no credit card, nothing to
  keep awake or within free-tier quotas.
- The demo reproduces identically on any machine with Docker (~4–6 GB free RAM
  for all containers + the embedding model).
- No always-on public URL for the app itself; the public artifact is the static
  landing page, and anyone can run the real app locally in one command.
- All cloud-deployment artifacts are removed — the `deploy/` folder (OCI/Vercel
  guides), `DEPLOYMENT.md`, the root/`frontend` `vercel.json`, and the OCI/Vercel/
  Hugging Face ADRs. `docker-compose.yml` / `backend/Dockerfile` /
  `backend/entrypoint.sh` remain and are now the primary (local) runtime.

## Implementation
- `docker-compose.yml` gains a `frontend` service (Next.js standalone image,
  `frontend/Dockerfile`); it reaches the backend over the compose network via
  `API_URL=http://backend:5000`.
- Local correctness fixes: MinIO pre-signed view URLs are signed against a
  browser-reachable endpoint (`MINIO_PUBLIC_ENDPOINT`) so the inline PDF viewer
  loads; the auth cookie's `Secure` flag is disabled for local http via
  `COOKIE_SECURE=false`.
- `README.md` documents the one-command quick start.
