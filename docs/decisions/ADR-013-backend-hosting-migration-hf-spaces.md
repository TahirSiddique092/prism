# ADR-013: Backend hosting migration — OCI VM → Hugging Face Spaces + managed free tiers

## Status
Accepted (supersedes ADR-011 OCI deployment as the production target).

## Context
The backend was deployed as an all-in-one `docker-compose` stack (Flask + MySQL
+ pgvector + Neo4j + Redis + MinIO) on an OCI Always-Free VM. We needed to move
off OCI to a different free provider. The hard constraint is the in-process
`sentence-transformers/all-MiniLM-L6-v2` model (PyTorch, ~1–2 GB RAM), which
does not fit the 256–512 MB that most free PaaS (Render/Koyeb free) offer, and
Fly.io no longer has a free tier (2026).

## Decision
Split the single VM into a compute host + managed data services (Path B):

- **Compute:** Hugging Face Spaces (Docker SDK), free CPU tier (2 vCPU / 16 GB
  RAM, HTTPS). Fits the model; sleeps after 48h idle.
- **Data (managed free tiers):** Neon (pgvector), Aiven (MySQL + FULLTEXT),
  Neo4j AuraDB Free, Upstash (Redis), and Neon Object Storage (S3-compatible,
  built into the same Neon project — no separate account or credit card; a
  Cloudflare R2 bucket is an equivalent drop-in alternative).

Run the API under **gunicorn** (not the Flask dev server), fail-fast on bad
config / failed migrations, and serve everything over HTTPS.

### Alternatives considered
- **Whole stack in one HF Space (Path A):** simplest (reuse compose) but the
  Space's disk is ephemeral — data resets on every restart/48h sleep. Rejected
  for a project that must demonstrate persistent databases.
- **Render/Koyeb/Fly free:** 512 MB RAM (or no free tier) — too small for the
  model. Rejected.

## Consequences
- Data survives Space restarts/sleeps (lives in managed services).
- HTTPS end-to-end incidentally fixes two audit findings: cleartext
  credentials/JWT (backend was plain HTTP) and the mixed-content PDF viewer
  (pre-signed object URLs are now HTTPS).
- New moving parts: five external services to provision and keep within free
  quotas; AuraDB pauses after 3 days idle; cold starts ~30–60s after sleep.
- `docker-compose.yml` + `backend/Dockerfile` + `backend/entrypoint.sh` are
  retained for **local development** only (and the slice-22 acceptance tests).
- `storage.py` now speaks generic S3 (`S3_*` env, HTTPS default for remote
  hosts) with `MINIO_*` kept as fallback.

## Implementation
- `deploy/huggingface/` — production `Dockerfile`, `entrypoint.sh` (gunicorn +
  fail-fast), and Space `README.md` template.
- `deploy/huggingface-setup.md` — end-to-end runbook.
- `backend/requirements.txt` — add `gunicorn`.
- Frontend: set `API_URL` (and `NEXT_PUBLIC_API_URL`) to the Space URL on Vercel.
