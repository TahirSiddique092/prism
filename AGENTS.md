# AGENTS.md

> Instructions for AI coding agents working in this repo. Read this before starting any slice.

## What this project is

PRISM (Personal Relational Intelligent Search Machine) is a web app where users upload PDFs and search them using plain English via semantic vector search. Full context lives in `docs/PRD.md` and `docs/ADD.md` — read those first if you're unfamiliar with the project.

## Repo structure

```
/
├── frontend/          # Next.js app — deployed on Vercel
├── backend/           # Flask REST API — deployed on OCI VM
│   ├── modules/
│   │   ├── auth/
│   │   ├── documents/
│   │   ├── search/
│   │   ├── cache/
│   │   ├── graph/
│   │   └── analytics/
│   └── app.py
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── sprints.md
│   ├── slices/
│   └── slices/
├── .env.example
├── AGENTS.md
└── docker-compose.yml  # spins up MySQL, pgvector, Neo4j, Redis, MinIO locally

```

## How work is structured

Work is broken into **slices** (`docs/slices/`), grouped into **sprints** (`docs/sprints.md`) and **slices** (`docs/slices/`). Each slice has:

- A module it belongs to (see `docs/ADD.md`)
- Acceptance criteria written as testable statements — treat these as the test plan
- An "out of scope" note — do not build beyond it

**Only work on the slice you've been given.** Do not expand scope, add extras, or refactor unrelated code unless explicitly asked.

## Commit / PR convention

Reference the slice ID in every commit message and PR title.
Example: `slice-03-document-upload: add chunking and pgvector insert`

## Human review required — do not merge without it

- Any change to `auth` module or JWT logic
- Data deletion or destructive migrations
- Changes to `docker-compose.yml` or any infra config
- Anything touching `.env` or secrets

For everything else, open a PR and proceed normally.

## Secrets & environment

Never read, log, or commit actual secret values. Reference `.env.example` for all expected variables. Ask the human to supply actual values if needed.

Variables the project uses:
```
MYSQL_URL
POSTGRES_URL
NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD
REDIS_URL
MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY
JWT_SECRET
NEXT_PUBLIC_API_URL
```

## Stack rules

- **Backend:** Flask only — no FastAPI, no Django
- **Frontend:** Next.js (App Router) — no plain React, no Vite
- **ORM:** Raw SQL via `mysql-connector-python` and `psycopg2` — no SQLAlchemy, no ORM abstractions. This is a DBMS course project; queries must be visible and explicit.
- **Embedding:** `sentence-transformers/all-MiniLM-L6-v2` — do not swap models without an ADR
- **Chunking:** `nltk.sent_tokenize` with ~200 word target and 1–2 sentence overlap
- **Similarity threshold:** 0.75 cosine distance triggers FULLTEXT fallback — hardcoded for v1

## Testing

Acceptance criteria in each slice doc are the test contract. Write tests that verify those criteria, not just tests that pass against your own implementation.

## If something is ambiguous

Stop and ask. If the slice, architecture, or PRD doesn't answer your question, flag it — don't assume.

## CI / Docker / release pipelines

Do not add CI workflows or a release pipeline as a side effect of another task. Only set these up if explicitly asked. `docker-compose.yml` is for local dev only.

## Decisions log

If you make a non-obvious architectural choice while executing a slice, note it in `docs/decisions/ADR-XXX-<short-name>.md` (a few lines is enough). Not every choice needs one — only ones that would be confusing to revisit later without the reasoning.
