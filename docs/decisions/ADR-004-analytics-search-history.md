# ADR-004 — Analytics search history via window functions (slice-14)

## Context

slice-14 adds `GET /api/analytics/history`, returning the authenticated user's
past search queries ranked by frequency using SQL window functions over the
`search_log` table in MySQL.

## Decisions

- **Single aggregation + window function query.** We execute the slice's exact SQL
  statement:
  `RANK() OVER (ORDER BY COUNT(*) DESC)` to rank queries by descending search count,
  `MAX(searched_at)` for the latest search timestamp, and
  `SUM(COUNT(*)) OVER ()` for the user's grand total searches. Window functions
  evaluate over the grouped result set, returning all required metrics in one query
  without separate scalar lookups or subqueries.
- **Strict user scoping in SQL.** The query filters `WHERE user_id = %s` using the
  authenticated `g.user_id` injected by JWT middleware, ensuring a user never
  sees another user's queries.
- **Empty list on zero search history.** If a user has performed no searches, the
  query yields zero rows and returns `[]` with HTTP 200, consistent with the rest
  of the PRISM analytics API contract.
- **Dedicated analytics module.** Established `backend/modules/analytics` with
  raw SQL operations in `db.py` and route handling in `routes.py`, registered under
  the `/api/analytics` blueprint prefix in `create_app()`.

## Out of scope

No date filtering, pagination, or history deletion in v1 (per the slice).
