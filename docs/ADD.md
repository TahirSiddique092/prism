# Architecture

## Stack

Hosting follows [ADR-015](decisions/ADR-015-hybrid-local-compute-managed-data.md): compute runs locally in Docker, data services are managed free tiers.

- **Frontend:** Next.js — local Docker container
- **Backend:** Python + Flask (REST API) — local Docker container
- **Relational DB:** MySQL 8.0 — Aiven
- **Vector DB:** PostgreSQL + pgvector extension — Neon
- **Graph DB:** Neo4j — Neo4j Aura
- **Cache:** Redis — Upstash
- **File storage:** S3-compatible object storage — Neon Object Storage
- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` — runs in the Flask process
- **Auth:** JWT (issued by Flask, verified on every protected request)

---

## System flow

```mermaid
flowchart LR
    Client["Next.js (local)"]
    API["Flask API (local)"]
    MySQL[("MySQL")]
    PG[("pgvector")]
    Neo4j[("Neo4j")]
    Redis[("Redis")]
    MinIO[("Object storage")]
    Embed["Embedding model"]

    Client -->|HTTPS + JWT| API
    API --> MySQL
    API --> PG
    API --> Neo4j
    API --> Redis
    API --> MinIO
    API --> Embed
```

---

## Modules

- `auth` — register, login, logout. Issues and verifies JWTs. Handles password hashing with bcrypt. Owns the `users` table, including each account's role (`user` or `admin`), which `require_admin` reads from MySQL on every admin request (ADR-023).
- `documents` — receives PDF upload from client, stores the file in MinIO, parses text with PyMuPDF, splits into sentence-boundary-aware chunks, embeds each chunk via the embedding model, writes document metadata to MySQL and chunk vectors to pgvector. Also handles document deletion and listing.
- `search` — accepts a plain-English query, embeds it, runs cosine similarity search on pgvector. If the best match distance exceeds 0.75, falls back to MySQL FULLTEXT search; otherwise drops matches beyond 0.60 distance, keeping the best (ADR-020). Logs every search to `search_log` and writes top results to `search_results`. Calls `cache` before hitting pgvector.
- `cache` — Redis read/write/invalidate layer. Key format: `search:{user_id}:{md5(query)}`. TTL: 3600s. Invalidates a user's cache on new document upload. Used by `search`; reusable across other modules.
- `graph` — on document upload, writes `(Document)-[:ABOUT]->(Topic)` nodes and relationships to Neo4j using manually assigned topic tags. Exposes a query to find related documents by shared topics.
- `analytics` — read-only reporting module. Serves search history ranked with window functions, unsearched documents via CTE, and top documents via the `top_documents` view. No writes.
- `admin` — read-only, admins only. Lists every user with their counts, system-wide totals (stored procedures) and the deletion log written by the `before_document_delete` trigger. Never returns password hashes, search text or document text.

---

## API contract

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | `{ name, email, password }` | `{ user_id, token }` |
| POST | `/api/auth/login` | `{ email, password }` | `{ user_id, token }` |
| POST | `/api/auth/logout` | — | `{ message }` |
| GET | `/api/auth/me` | — | `{ user_id, name, email, role }` |
| GET | `/api/documents` | — | `[{ doc_id, title, uploaded_at, status, chunk_count }]` |
| GET | `/api/documents/:doc_id` | — | `{ doc_id, title, uploaded_at, status, chunk_count, topics }` |
| GET | `/api/documents/:doc_id/url` | — | `{ view_url }` |
| POST | `/api/documents/upload` | `form-data: file, topics[]` | `{ doc_id, minio_key }` |
| DELETE | `/api/documents/:doc_id` | — | `{ message }` |
| POST | `/api/documents/:doc_id/retry` | — | `202 { doc_id, status: "processing" }`; 409 unless the document is in `error` |
| GET | `/api/documents/:doc_id/related` | — | `[{ doc_id, title, shared_topics }]` |
| GET | `/api/documents/:doc_id/chunks/:chunk_id` | — | `{ chunk_id, chunk_text, page_start, page_end }` |
| POST | `/api/search` | `{ query, log? }` (`log: false` = don't record in search history) | `{ results: [{ chunk_id, doc_id, doc_title, snippet, score, page }], cached }` |
| GET | `/api/analytics/history` | — | `[{ query_text, search_count, query_rank, last_searched, total_searches }]` |
| GET | `/api/analytics/unsearched` | — | `[{ doc_id, title, uploaded_at }]` |
| GET | `/api/analytics/top-documents` | — | `[{ doc_id, title, search_count, appearance_count, avg_score, avg_similarity }]` |
| GET | `/api/admin/users` | — (admin) | `[{ user_id, name, email, role, created_at, documents, chunks, searches, last_search_at }]` |
| GET | `/api/admin/stats` | — (admin) | `{ users, admins, documents, documents_processing, documents_ready, documents_error, chunks, searches, searches_today, deletions }` |
| GET | `/api/admin/deletions` | — (admin) | `[{ audit_id, doc_id, title, user_id, deleted_at }]` (latest 50) |

All protected routes require `Authorization: Bearer <token>` header. `/api/admin/*` also requires the `admin` role: 401 without a session, 403 for a `user`.

Timestamps (`uploaded_at`, `last_searched`, `created_at`, `last_search_at`, `deleted_at`) are UTC in ISO 8601 with a `Z` suffix, e.g. `2026-10-29T16:00:09Z`; the frontend shows them in the viewer's time zone. `score` is the cosine distance (lower is closer), or `null` for FULLTEXT results; the frontend shows it as similarity, 1 − distance.

---

## Data model

Full schema, diagrams and data flows: [relational-schema.md](data/relational-schema.md) (MySQL) and [nosql-schema.md](data/nosql-schema.md) (pgvector, Neo4j, Redis, object storage).

- `User` — has a role (`user` or `admin`), has many `Documents`, has many `SearchLogs`
- `Document` — belongs to `User`, has many `Chunks`, has many `Topics` (via `DocTopics`)
- `Chunk` — belongs to `Document`, carries the embedding vector, appears in many `SearchResults`
- `Topic` — has many `Documents` (via `DocTopics`)
- `SearchLog` — belongs to `User`, has many `SearchResults`
- `SearchResult` — belongs to `SearchLog`, references a `Chunk`, carries rank and similarity score

---

## Constraints

- **Scale:** Single-user to small group (~10 users, ~500 documents max). No horizontal scaling needed.
- **Performance:** Search must return results within 3 seconds end-to-end including embedding. Upload processing can be async — user gets a confirmation immediately, chunking happens in the background.
- **Security:** All API routes are JWT-protected except `/register` and `/login`. Flask CORS restricted to the frontend origin (`FRONTEND_URL`) only. Passwords hashed with bcrypt, never stored plain.
- **Chunking:** Sentence-boundary aware, targeting ~200 words per chunk with 1–2 sentence overlap. Implemented with `nltk.sent_tokenize`.
- **Similarity threshold:** Cosine distance > 0.75 triggers FULLTEXT fallback. Hardcoded for v1, extractable to config later.
- **Result cutoff:** Vector results with cosine distance > 0.60 are dropped, except the best match (ADR-020).
- **No offline support, no mobile, no multi-tenancy** — out of scope for v1.