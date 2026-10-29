# slice-29 — Make cached searches fast (connection reuse)

**Sprint:** 7 — Hardening and UX
**Module:** cache, search, documents

## What to build

The Redis search cache works: repeating a query returns `"cached": true`. But a cache hit still takes about 1.5 s, because every cache read and write opens a new TLS connection to Upstash. Postgres (Neon) has the same problem. This slice reuses connections so a cached search is quick and an uncached one is several seconds faster.

## Measurements (backend container, home network, 29 Oct 2026)

| What | Time |
|---|---|
| Redis command, new connection per call (current code) | ~1,370 ms |
| Redis command on a reused connection | ~230 ms |
| Postgres connect (Neon) | ~1,750 ms |
| Postgres `SELECT 1` on an open connection | ~550 ms |
| MySQL connect (Aiven) | ~90 ms |
| **Search, cache miss** | **6,445 ms** = Redis read 1,383 + MySQL doc ids 431 + embedding 63 + pgvector 3,058 + MySQL metadata 129 + Redis write 1,380 |
| **Search, cache hit** | **1,505 ms**, all of it the Redis read |

## Changes

### 1. One Redis client per process
**Problem:** `get_redis_client()` (`backend/modules/cache/service.py`) calls `redis.from_url` every time. That creates a new connection pool, so each `get`, `set` and invalidation pays for TCP + TLS + AUTH.

**Change:**
- `get_redis_client()` returns a module-level client, created on first use. Its connection pool is reused across requests and threads.
- Set `health_check_interval` (e.g. 30 s) and retry once on a connection error, so connections Upstash closes while idle are replaced without the caller noticing.
- Add `reset_redis_client()` for tests, like `graph.client.reset_driver()`.
- Keep the current behaviour when Redis is down: search still works and simply isn't cached.

### 2. Pool Postgres connections
**Problem:** `search_chunk_vectors` opens and closes a new Neon connection for every search (~1.75 s). The same `get_postgres_conn()` helper is duplicated in `documents/db.py` and `search/db.py`.

**Change:**
- Keep one `get_postgres_conn()` backed by a small `psycopg2.pool.ThreadedConnectionPool` (min 1, max 5), used by search, the worker and document delete. Callers return connections to the pool instead of closing them.
- Neon closes idle connections and scales to zero. A pooled connection that fails on first use is therefore discarded, and the query runs once more on a fresh connection.

### 3. Record the result
Add `docs/decisions/ADR-018-connection-reuse.md` with the table above and the same measurements taken after the change.

## Acceptance criteria

- With Redis reachable, the second identical search returns `cached: true`, and the backend spends under 400 ms on it (measured in the container as above)
- On the same network, a cache miss is at least 3 s faster than the 6.4 s baseline
- Over 20 consecutive searches in one process, `redis.from_url` is called once
- If Redis drops the connection between searches, the next search still succeeds
- If Redis is unreachable, search still returns results with `cached: false`, as today
- After Neon closes an idle pooled connection, the next search still succeeds
- Cache invalidation on upload, on processing finished and on delete still works (existing tests pass)
- ADR-018 contains the before/after table

## Out of scope

- Moving Upstash or Neon to a nearer region (sprint 7 open question 3)
- Pooling MySQL connections (connecting takes ~90 ms)
- Changing what is cached or the TTL

## Assigned To

Unassigned

## Human review required?

No.
