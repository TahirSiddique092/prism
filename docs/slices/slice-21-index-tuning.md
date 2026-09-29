# slice-21 — Index tuning and EXPLAIN analysis

**Sprint:** 6 — Polish and deployment
**Module:** infra

## What to build

Run `EXPLAIN ANALYZE` on the two most expensive queries, add missing indexes, and document the before/after results in `docs/decisions/ADR-001-indexing.md`.

## Queries to analyse

1. The `search_log` history query (window function) — currently scans all rows for a user
2. The `search_results` join chain used in the unsearched docs CTE

## Acceptance criteria

- `EXPLAIN` output captured before any new indexes are added
- Composite index added on `search_log(user_id, searched_at)` if not already present from slice-02
- Index added on `search_results(log_id)` and `search_results(chunk_id)` if missing
- `EXPLAIN` output captured after — estimated rows scanned must decrease for both queries
- Before/after outputs saved in `docs/decisions/ADR-001-indexing.md`
- No indexes added speculatively — only the two queries above

## Out of scope

- No pgvector index tuning — ivfflat index was set in slice-02
- No query rewriting

## Assigned To

Dev B

## Human review required?

No.
