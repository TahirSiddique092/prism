# slice-34 — Stored functions

**Sprint:** 8 — DBMS features and admin
**Module:** documents, analytics, frontend, infra (migrations)
**Depends on:** slice-32 (logging helper), slice-33 (migration runner handles several routines)

## What to build

Add two user-defined MySQL functions and use them inside the queries the app already runs.

| Function | Returns | Used in |
|---|---|---|
| `fn_chunk_count(p_doc_id INT)`, `READS SQL DATA` | INT: how many chunks the document has | The document list (`get_user_documents`) and document detail (`get_document_chunk_count`) |
| `fn_similarity(p_distance DOUBLE)`, `DETERMINISTIC NO SQL` | DOUBLE: `1 − p_distance`, or NULL when the distance is NULL | Top Documents (`get_top_documents`), as `avg_similarity` |

## Changes

### 1. Migration `009_stored_functions.sql`
- Create both functions, each as `DROP FUNCTION IF EXISTS …` followed by `CREATE FUNCTION …`, so the migration can be applied again.
- Each function must declare its characteristic (`READS SQL DATA`, or `DETERMINISTIC NO SQL`). Aiven runs MySQL with binary logging, and without these declarations `CREATE FUNCTION` is refused (error 1418).

### 2. Use `fn_chunk_count`
- **Document list:** the `LEFT JOIN chunks … GROUP BY` becomes:
  ```sql
  SELECT d.doc_id, d.title, d.uploaded_at, d.status, fn_chunk_count(d.doc_id) AS chunk_count
  FROM documents d
  WHERE d.user_id = %s
  ORDER BY d.uploaded_at DESC;
  ```
- **Document detail:** `SELECT fn_chunk_count(%s)` replaces the separate `COUNT(*)` query.

### 3. Use `fn_similarity`
- The Top Documents query also returns `fn_similarity(avg_score) AS avg_similarity`.
- The API response gains `avg_similarity`, and the Top Documents page shows it instead of computing `1 − avg_score` in the browser.
- The Search page is unchanged, because its distances come from pgvector, not MySQL.

### 4. Logs and docs
- Each query that uses a function logs a `[DB] FUNCTION` line (slice-32).
- In `relational-schema.md` § 5, add a "Stored functions" part, and update the affected Key queries (§ 7). Update the ADD API table for `avg_similarity`.

## Acceptance criteria

- After migrating, `SHOW FUNCTION STATUS WHERE Db = DATABASE()` lists `fn_chunk_count` and `fn_similarity`
- The document list and document detail report the same chunk counts as before, including 0 for a document with no chunks
- `fn_similarity(0.4634)` returns 0.5366, and `fn_similarity(NULL)` returns NULL
- `/api/analytics/top-documents` includes `avg_similarity`, and the page shows the same value as before (e.g. 0.5366)
- Each query using a function prints a `[DB] FUNCTION` line with the function name, the user ID, the row count and the time
- Applying the migration a second time does not fail
- An opt-in integration test (`PRISM_MYSQL_INTEGRATION=1`) checks both functions on a real MySQL server
- All existing tests still pass

## Out of scope

- Moving other calculations into functions
- Changing how pgvector distances are computed or shown on the Search page

## Assigned To

Unassigned

## Human review required?

Yes. It adds a schema migration (new routines).
