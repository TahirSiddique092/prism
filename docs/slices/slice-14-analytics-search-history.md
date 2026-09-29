# slice-14 — Analytics — search history with window functions

**Sprint:** 4 — Graph and analytics
**Module:** analytics

## What to build

`GET /api/analytics/history` — return the authenticated user's search history ranked by frequency using SQL window functions.

## SQL

```sql
SELECT
    query_text,
    COUNT(*)                                             AS search_count,
    RANK() OVER (ORDER BY COUNT(*) DESC)                 AS query_rank,
    MAX(searched_at)                                     AS last_searched,
    SUM(COUNT(*)) OVER ()                                AS total_searches
FROM search_log
WHERE user_id = :user_id
GROUP BY query_text
ORDER BY query_rank;
```

## Acceptance criteria

- Response includes `query_text`, `search_count`, `query_rank`, `last_searched`, `total_searches`
- Queries are ranked correctly — most searched query has rank 1
- `total_searches` is the same across all rows (it's a grand total)
- Returns an empty list if the user has no search history
- Only returns the current user's queries — never another user's

## Out of scope

- No date filtering or pagination in v1
- No deletion of search history

## Assigned To

Dev B

## Human review required?

No.
