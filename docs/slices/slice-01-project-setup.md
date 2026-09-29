# slice-01 — Project setup and docker-compose

**Sprint:** 1 — Foundation
**Module:** infra

## What to build

Initialise the repo structure, create a `docker-compose.yml` that spins up all backend services locally, and add a `.env.example` with every variable the project needs.

## Acceptance criteria

- `docker-compose up` starts MySQL 8.0, PostgreSQL + pgvector, Neo4j, Redis, and MinIO with no manual config
- pgvector extension is enabled automatically on Postgres startup
- All services are reachable on localhost with ports defined in `.env.example`
- `.env.example` lists every env variable used across the project — no actual values committed
- `backend/` has a basic Flask app (`app.py`) that returns `{ "status": "ok" }` on `GET /health`
- `frontend/` is a bootstrapped Next.js app (App Router) with a single placeholder home page

## Out of scope

- No auth, no routes beyond `/health`
- No data, no migrations yet — that's slice-02
- No Vercel or OCI config — that's sprint 6

## Assigned To

Dev A

## Human review required?

Yes — touches `docker-compose.yml` and `.env` configuration.
