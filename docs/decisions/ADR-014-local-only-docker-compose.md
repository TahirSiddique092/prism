# ADR-014: Local-only delivery via docker-compose (no cloud deployment)

## Status
Accepted (supersedes ADR-013; the Hugging Face / managed-free-tier migration is
no longer pursued).

## Context
PRISM is a mini DBMS course project. We explored deploying the backend to a free
cloud host (OCI → ADR-011; then Hugging Face Spaces + managed free tiers →
ADR-013). In practice every path hit a wall: free hosts large enough to run the
in-process `sentence-transformers` model now require a paid plan (Hugging Face
Spaces Docker) or a credit card (Koyeb, Fly, Google Cloud Run, OCI signup), and
we did not want to supply card details or pay.

## Decision
**Do not deploy the application to the cloud.** Instead:

1. The entire stack — Next.js frontend, Flask backend, MySQL, pgvector/Postgres,
   Neo4j, Redis, and MinIO — runs locally with a single command:
   `docker compose up`. A fresh clone "just works" with no external accounts.
2. A small **static landing page** (hosted free on GitHub Pages) presents the
   project and links to the GitHub repo with the clone-and-run instructions.

The backend keeps the simple Flask development server (`python app.py`) — it is
only ever run locally, so a production WSGI server is unnecessary.

## Consequences
- No third-party database/storage/compute accounts, no credit card, nothing to
  keep awake or within free-tier quotas.
- The demo reproduces identically on any machine with Docker (~4–6 GB free RAM
  for all containers + the embedding model).
- No always-on public URL for the app itself; the public artifact is the static
  landing page, and anyone can run the real app locally in one command.
- The cloud-deployment docs (`DEPLOYMENT.md`, `deploy/huggingface/*`,
  `deploy/huggingface-setup.md`) are removed. `docker-compose.yml` /
  `backend/Dockerfile` / `backend/entrypoint.sh` remain and are now the primary
  (local) runtime. `deploy/` retains the OCI/Vercel references only because the
  slice-22/23 acceptance tests assert those files exist.

## Implementation
- `docker-compose.yml` gains a `frontend` service (Next.js standalone image,
  `frontend/Dockerfile`); it reaches the backend over the compose network via
  `API_URL=http://backend:5000`.
- Local correctness fixes: MinIO pre-signed view URLs are signed against a
  browser-reachable endpoint (`MINIO_PUBLIC_ENDPOINT`) so the inline PDF viewer
  loads; the auth cookie's `Secure` flag is disabled for local http via
  `COOKIE_SECURE=false`.
- `README.md` documents the one-command quick start.
