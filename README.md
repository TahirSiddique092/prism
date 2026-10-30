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

## Quick start

PRISM uses a **hybrid** deployment (see `docs/decisions/ADR-015`): the
compute-heavy parts — the Flask backend with its in-process embedding model, and
the Next.js frontend — run locally in Docker, while the five datastores are
managed free-tier services (Aiven, Neon, Neo4j Aura, Upstash). You need **Docker
Desktop** (or Docker Engine + Compose v2) and accounts on those providers.

```bash
git clone https://github.com/TahirSiddique092/prism.git
cd prism
cp .env.example .env       # then fill in the managed-service connection strings
docker compose up --build  # --build on the first run (also downloads the model)
```

When it's up, open **http://localhost:3000**, then **register an account →
upload a PDF → search it**. Stop with `Ctrl+C`; `docker compose down` removes the
containers (your data lives in the managed services, not local volumes).

---

## What's running

**Local (Docker):**

| Service    | Port(s)        | Role |
|------------|----------------|------|
| frontend   | 3000           | Next.js (App Router) web UI |
| backend    | 5000           | Flask REST API + embedding model |

**Managed (configured via `.env`):**

| Datastore              | Provider           | Role |
|------------------------|--------------------|------|
| MySQL                  | Aiven              | Users, documents, chunks, FULLTEXT, analytics |
| PostgreSQL + pgvector  | Neon               | pgvector embeddings (semantic search) |
| Neo4j                  | Neo4j Aura         | Topic graph (related documents / topics) |
| Redis                  | Upstash            | Search result cache |
| Object storage (S3)    | Neon Object Storage| Uploaded PDF storage |

The frontend talks only to the backend (server-side); the backend owns all the
datastores. Database migrations run automatically on backend startup.

## How it works (high level)

1. **Upload** → the PDF is stored in MinIO; text is extracted and chunked
   (~200 words, sentence overlap) into MySQL; each chunk is embedded with
   `all-MiniLM-L6-v2` into pgvector; topics are written to a Neo4j graph.
2. **Search** → your query is embedded and matched by cosine distance in
   pgvector; weak matches (distance > 0.60) are left out, and if nothing is
   close enough (distance > 0.75) it falls back to MySQL FULLTEXT; results are
   cached in Redis.
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
project conventions. Deployment decision: **hybrid — local compute + managed
data services** — see `docs/decisions/ADR-015-hybrid-local-compute-managed-data.md`.

## Reconciling the data stores

Deleting a document cleans up every store, but the steps after MySQL are best-effort (see [ADR-016](docs/decisions/ADR-016-cross-store-delete.md)). To find, and optionally remove, anything left behind in pgvector, Neo4j or object storage, and to backfill topic tags into MySQL:

```bash
docker compose exec backend python backend/db/reconcile.py           # dry run: report only
docker compose exec backend python backend/db/reconcile.py --apply   # remove the orphans it reported
```

MySQL is the source of truth, so the script refuses to run without `MYSQL_URL`. Always read the dry-run report before running `--apply`.

## Backfilling passage pages

Search results open the PDF at the passage's page (slice-27). Documents processed before that change have no page numbers stored, so their results open at page 1. To fill them in:

```bash
docker compose exec backend python backend/db/backfill_chunk_pages.py           # dry run: report only
docker compose exec backend python backend/db/backfill_chunk_pages.py --apply   # write the pages
```

The script re-splits each PDF exactly as the worker does and only writes pages when the result matches the stored chunks; anything else is reported and left alone.

## Running the tests

```bash
# Backend (Python): a lightweight stub lets the suite run without the ML model
cd backend && python -m pytest

# Frontend (Node test runner)
cd frontend && npm test
```
