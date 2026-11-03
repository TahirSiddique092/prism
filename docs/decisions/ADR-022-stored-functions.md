# ADR-022 — Stored functions in the app's queries

## Context

The project guide asked for stored functions. Two small calculations were done outside MySQL or with a join that existed only to count rows:
- the chunk count per document, a `LEFT JOIN chunks … GROUP BY` in the document list and a separate `COUNT(*)` for the detail page;
- the similarity on Top Documents, `1 − avg_score`, computed in the browser.

## Decision

- **`fn_chunk_count(p_doc_id INT) RETURNS INT READS SQL DATA`** replaces the join in the document list, and the `COUNT(*)` on the detail page (`SELECT fn_chunk_count(%s)`).
- **`fn_similarity(p_distance DOUBLE) RETURNS DOUBLE DETERMINISTIC NO SQL`** returns `1 − distance`, keeping NULL as NULL. Top Documents selects `fn_similarity(avg_score) AS avg_similarity`, and the page shows that value. The Search page still converts pgvector distances in the browser, because those never pass through MySQL.
- **Declared characteristics are required.** Aiven runs MySQL with binary logging, which refuses `CREATE FUNCTION` without `DETERMINISTIC`, `NO SQL` or `READS SQL DATA` (error 1418).
- **Logging:** each query that uses a function logs a `[DB] FUNCTION` line. A single-value call logs its result, e.g. `fn_chunk_count(doc_id=4) = 43`.

## Consequences

- `fn_chunk_count` runs once per listed document. For a single user's library that's a handful of indexed lookups. For very large lists, the old `LEFT JOIN … GROUP BY` would scale better.
- Both functions are created by migration 009, using the multi-routine migration runner from slice-33.
