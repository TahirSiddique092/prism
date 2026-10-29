# slice-24 — Cross-store consistency fixes

**Sprint:** 7 — Hardening and UX
**Module:** documents, graph, infra

## What to build

A document's data is spread over five stores (MySQL, pgvector, Neo4j, Redis, object storage), but a few write and delete paths do not keep them in step. This slice closes those gaps so every store agrees with MySQL, the source of truth. It also brings `docs/ADD.md` back in line with the code.

## Changes

### 1. Remove the document from Neo4j on delete
**Problem:** `DELETE /api/documents/:doc_id` (`backend/modules/documents/routes.py`, `delete_document_route`) cleans up MySQL, pgvector, object storage and Redis, but never touches Neo4j. The `Document` node and its `ABOUT` edges stay in the graph. `RELATED_CYPHER` therefore keeps returning deleted documents as "related", and clicking one gives a 404.

**Change:**
- Add `delete_document_from_graph(doc_id, user_id)` to `backend/modules/graph/service.py`, using the same never-raises, log-and-continue style as `get_related_documents`:
  ```cypher
  MATCH (:User {user_id: $user_id})-[:UPLOADED]->(d:Document {doc_id: $doc_id})
  DETACH DELETE d
  WITH 1 AS _
  MATCH (t:Topic) WHERE NOT (t)<-[:ABOUT]-()
  DELETE t
  ```
- Export it from `backend/modules/graph/__init__.py`. Call it in `delete_document_route` as a new best-effort step after the pgvector cleanup, wrapped in `try/except` + `logger.warning` like the other steps.
- As a second safeguard, in `get_related_documents_route`, keep only the related `doc_id`s that still exist in MySQL for this user (one `SELECT doc_id FROM documents WHERE user_id = %s AND doc_id IN (...)`).

### 2. Mirror topic tags into MySQL `topics` / `doc_topics`
**Problem:** The relational schema defines `topics` and `doc_topics`, but the upload path writes topic tags only to Neo4j (ADR-002), so these tables are always empty.

**Change:**
- Add `insert_document_topics(doc_id, topic_names, conn=None)` to `backend/modules/documents/db.py` (raw SQL):
  ```sql
  INSERT IGNORE INTO topics (name) VALUES (%s);                -- executemany, one row per name
  INSERT IGNORE INTO doc_topics (doc_id, topic_id)
  SELECT %s, topic_id FROM topics WHERE name IN (%s, %s, ...);
  ```
- In `upload_document`, after `insert_document`, normalise the parsed topics with the existing `normalize_topics` (graph module), so MySQL and Neo4j hold identical names, then call `insert_document_topics`. A failure is logged and must not fail the upload.
- Reads stay on Neo4j. This change is only about keeping the relational model populated.

### 3. Remove the stored PDF if the MySQL insert fails on upload
**Problem:** `upload_document` writes the PDF to object storage first and inserts into MySQL second. If the insert fails, the PDF remains in the bucket with no `documents` row pointing to it.

**Change:** In the `except` branch around `insert_document`, call `delete_file(minio_key)` (best-effort, logged) before returning the 500.

### 4. Reconciliation script for leftovers
**Problem:** Several cleanup steps are best-effort (pgvector delete, storage delete, and now the graph delete). When one of them fails, or for data left over from before this slice, orphans remain with nothing to remove them.

**Change:** Add `backend/db/reconcile.py`, a manual CLI using the same connection helpers as `migrate.py`. It **dry-runs by default** and prints what it would do. `--apply` executes:
- deletes `chunk_vectors` rows whose `doc_id` is not in MySQL `documents`;
- `DETACH DELETE`s Neo4j `Document` nodes whose `doc_id` is not in MySQL, then removes `Topic` nodes with no `ABOUT` edges;
- deletes storage objects whose key does not match any `documents.minio_key`;
- backfills `topics` / `doc_topics` from Neo4j `ABOUT` edges for documents that existed before change 2.

Document how to run it in `README.md` (one short section).

### 5. Document the delete design (ADR-016)
Add `docs/decisions/ADR-016-cross-store-delete.md` (a few lines) recording:
- the MySQL trigger `before_document_delete` only writes `deletion_audit`. A MySQL trigger cannot reach PostgreSQL, Neo4j or object storage, so those deletes are run by the route, in order: MySQL → pgvector → Neo4j → object storage → Redis. This replaces the wording in slice-02 and slice-08 that has the trigger removing `chunk_vectors`;
- deleting a document cascades `chunks → search_results`, so its rows disappear from `top_documents` and from the "unsearched" check, while the `search_log` rows (query history) are kept. This is intended: the analytics describe documents that still exist;
- `reconcile.py` cleans up any best-effort step that failed.

### 6. Bring `docs/ADD.md` in line with the code
Update the **API contract** table to the responses the code actually returns:

| Method | Path | Response |
|---|---|---|
| GET | `/api/documents` | `[{ doc_id, title, uploaded_at, status, chunk_count }]` |
| GET | `/api/documents/:doc_id` | `{ doc_id, title, uploaded_at, status, chunk_count, topics }` (row missing today) |
| GET | `/api/documents/:doc_id/url` | `{ view_url }` (row missing today) |
| POST | `/api/documents/upload` | `{ doc_id, minio_key }` |
| POST | `/api/search` | `{ results: [{ chunk_id, doc_id, doc_title, snippet, score }], cached }` |
| GET | `/api/analytics/history` | `[{ query_text, search_count, query_rank, last_searched, total_searches }]` |
| GET | `/api/analytics/top-documents` | `[{ doc_id, title, appearance_count, avg_score }]` |

Also update the **Stack** section so its hosting matches ADR-015: backend and frontend run locally, and the data services are managed (Aiven / Neon / Aura / Upstash / Neon Object Storage). Also add a pointer to `docs/data/relational-schema.md` and `docs/data/nosql-schema.md`.

## Acceptance criteria

- After `DELETE /api/documents/:doc_id`, Neo4j has no `Document {doc_id}` node, and `Topic` nodes left with no `ABOUT` edges are removed
- `GET /api/documents/:other_id/related` never returns a document that has been deleted, even if the Neo4j delete failed
- The delete endpoint still returns 200 when Neo4j is unreachable (graph delete is best-effort and logged)
- Uploading with topics `["SQL", " sql ", "Joins"]` creates exactly two rows in `topics` (`sql`, `joins`) and two in `doc_topics` for that document, and the same two names in Neo4j
- Deleting that document removes its `doc_topics` rows via the existing cascade
- If `insert_document` raises during upload, `delete_file` is called with the generated `minio_key`, and the response is still 500
- `python backend/db/reconcile.py` with no flags changes nothing and lists the orphan vectors, graph nodes and storage objects it finds
- `python backend/db/reconcile.py --apply` removes exactly those orphans and leaves every row and object that belongs to an existing document untouched
- `ADR-016-cross-store-delete.md` exists, and the `ADD.md` API table matches the routes above
- All existing tests still pass. New tests cover each criterion above, using mocks for Neo4j and storage like the existing tests.

## Out of scope

- No switching topic reads from Neo4j to MySQL
- No scheduled or automatic reconciliation (the script is run by hand)
- No change to the cascade from `chunks` to `search_results`
- No Neo4j uniqueness constraints or schema migrations for the graph

## Assigned To

Unassigned

## Human review required?

Yes — adds data-deletion paths (Neo4j delete, compensating storage delete, and a reconciliation script that deletes across all stores).
