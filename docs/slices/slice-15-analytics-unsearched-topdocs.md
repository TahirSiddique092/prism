# slice-15 — Analytics — unsearched docs CTE and top documents view

**Sprint:** 4 — Graph and analytics
**Module:** analytics

## What to build

Two read-only endpoints powered by a CTE and a SQL view respectively.

---

### GET /api/analytics/unsearched

Documents the user uploaded that have never appeared in any search result.

**CTE:**
```sql
WITH searched_docs AS (
    SELECT DISTINCT d.doc_id
    FROM search_results sr
    JOIN chunks c ON sr.chunk_id = c.chunk_id
    JOIN documents d ON c.doc_id = d.doc_id
    JOIN search_log sl ON sr.log_id = sl.log_id
    WHERE sl.user_id = :user_id
)
SELECT doc_id, title, uploaded_at
FROM documents
WHERE user_id = :user_id
  AND doc_id NOT IN (SELECT doc_id FROM searched_docs);
```

---

### GET /api/analytics/top-documents

Documents ranked by how often their chunks appear in search results.

**View (created in migrations):**
```sql
CREATE VIEW top_documents AS
SELECT
    d.user_id,
    d.doc_id,
    d.title,
    COUNT(sr.result_id)          AS appearance_count,
    AVG(sr.similarity_score)     AS avg_score
FROM search_results sr
JOIN chunks c ON sr.chunk_id = c.chunk_id
JOIN documents d ON c.doc_id = d.doc_id
GROUP BY d.doc_id, d.user_id, d.title;
```

Query: `SELECT * FROM top_documents WHERE user_id = :user_id ORDER BY appearance_count DESC LIMIT 10`

---

## Acceptance criteria

- `/unsearched` returns only documents with zero appearances in `search_results` for this user
- `/top-documents` returns documents ordered by `appearance_count` descending
- Both endpoints return empty lists (not errors) when no data exists
- Neither endpoint ever returns another user's documents
- `top_documents` view is created in the migration script from slice-02, not here

## Out of scope

- No pagination
- No time-range filtering

## Assigned To

Dev B

## Human review required?

No.
