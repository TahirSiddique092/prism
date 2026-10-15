# PRISM — Personal Relational Intelligent Search Machine

Upload your PDFs and search them in **plain English**. PRISM chunks and embeds
your documents, finds the most relevant passages with semantic vector search
(with a MySQL FULLTEXT fallback), builds a topic graph of what you've read, and
shows it all through a clean web UI with an inline PDF reader and search
analytics.

It's a DBMS course project that deliberately spans **five datastores** working
together — MySQL, PostgreSQL + pgvector, Neo4j, Redis, and MinIO — all behind a
Flask API and a Next.js frontend.

---

## Quick start — one command

Everything runs locally in Docker. You need **Docker Desktop** (or Docker Engine
+ Compose v2) and ~**4–6 GB of free RAM**.

```bash
git clone https://github.com/TahirSiddique092/prism.git
cd prism
docker compose up          # add --build the first time if needed
```

First run takes a few minutes (it builds the images and downloads the embedding
model). When it's up, open:

- **App:** http://localhost:3000
- MinIO console: http://localhost:9001 (user/pass: `minioadmin` / `minioadmin`)

Then: **register an account → upload a PDF → search it**. Stop everything with
`Ctrl+C`, and `docker compose down` to remove the containers (add `-v` to also
wipe the databases and start fresh).

No accounts, no API keys, no cloud — the whole stack is self-contained.

---

## What's running

| Service    | Port(s)        | Role |
|------------|----------------|------|
| frontend   | 3000           | Next.js (App Router) web UI |
| backend    | 5000           | Flask REST API + embedding model |
| mysql      | 3306           | Users, documents, chunks, FULLTEXT, analytics |
| postgres   | 5432           | pgvector embeddings (semantic search) |
| neo4j      | 7474 / 7687    | Topic graph (related documents / topics) |
| redis      | 6379           | Search result cache |
| minio      | 9000 / 9001    | Uploaded PDF storage (S3-compatible) |

The frontend talks only to the backend (server-side); the backend owns all the
datastores. Database migrations run automatically on backend startup.

## How it works (high level)

1. **Upload** → the PDF is stored in MinIO; text is extracted and chunked
   (~200 words, sentence overlap) into MySQL; each chunk is embedded with
   `all-MiniLM-L6-v2` into pgvector; topics are written to a Neo4j graph.
2. **Search** → your query is embedded and matched by cosine distance in
   pgvector; if nothing is close enough (distance > 0.75) it falls back to MySQL
   FULLTEXT; results are cached in Redis.
3. **Explore** → view a document with its topics, related documents (via Neo4j),
   an inline PDF viewer, and analytics on what you've searched.

## Project layout

```
frontend/   Next.js app (Dockerfile + standalone build)
backend/    Flask API, modules (auth, documents, search, cache, graph, analytics)
            db/migrations/  — raw SQL migrations (MySQL + pgvector)
docs/       PRD, architecture, slices, and decision records (ADRs)
docker-compose.yml   — the whole stack
```

See `docs/` for the full product/architecture docs and `AGENTS.md` for the
project conventions. Deployment decision: this project runs **locally only** —
see `docs/decisions/ADR-014-local-only-docker-compose.md`.

## Running the tests

```bash
# Backend (Python): a lightweight stub lets the suite run without the ML model
cd backend && python -m pytest

# Frontend (Node test runner)
cd frontend && npm test
```
