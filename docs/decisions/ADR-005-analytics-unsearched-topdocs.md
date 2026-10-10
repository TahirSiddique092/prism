# ADR-005 — Analytics unsearched docs CTE and top documents view (slice-15)

## Context

slice-15 adds two read-only analytics endpoints:
1. `GET /api/analytics/unsearched` — returns documents the user uploaded that have never appeared in any search result.
2. `GET /api/analytics/top-documents` — returns documents ranked by how often their chunks appear in search results.

## Decisions

- **Unsearched documents via CTE.** We implement the slice's exact Common Table
  Expression (CTE):
  `WITH searched_docs AS (...) SELECT doc_id, title, uploaded_at FROM documents ...`.
  Both the CTE (`sl.user_id = %s`) and outer query (`user_id = %s`) bind the
  authenticated `user_id`, guaranteeing full user isolation so users never see
  another user's documents.
- **Top documents via pre-created SQL view.** Per acceptance criterion 5, the
  `top_documents` SQL view (`CREATE OR REPLACE VIEW top_documents AS ...`) belongs
  in the migration script (`backend/db/migrations/001_init.sql`), not dynamically
  created in slice-15 code. The endpoint queries:
  `SELECT * FROM top_documents WHERE user_id = %s ORDER BY appearance_count DESC LIMIT 10;`.
- **Empty list on zero results.** When a user has no uploaded documents, all
  documents have been surfaced, or no search appearances exist, endpoints return
  `[]` with HTTP 200, matching the analytics contract.

## Out of scope

No pagination or time-range filtering in v1 (per the slice).
