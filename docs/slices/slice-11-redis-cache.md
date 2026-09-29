# slice-11 — Redis cache layer

**Sprint:** 3 — Search
**Module:** cache

## What to build

A reusable cache module that wraps Redis. Used by `search` to cache query results and invalidated by `documents` on upload or deletion.

## Cache design

- Key format: `search:{user_id}:{md5(query.strip().lower())}`
- Value: JSON-serialised list of result objects
- TTL: 3600 seconds
- Invalidation: delete all keys matching `search:{user_id}:*` when user uploads or deletes a document

## Acceptance criteria

- A repeated identical query (same user, same string) returns the cached result without hitting pgvector
- Cache key is normalised — "Joins in SQL" and "joins in sql" resolve to the same key
- TTL is set on every write — keys expire automatically after 1 hour
- Uploading or deleting a document clears all of that user's search cache
- Cache read/write errors are caught and logged — a Redis failure must not crash the search endpoint (degrade gracefully to a live query)
- `GET /api/search` response includes a `cached: true/false` field so the frontend can display it

## Out of scope

- No global cache invalidation across users
- No cache warming

## Assigned To

Dev A

## Human review required?

No.
