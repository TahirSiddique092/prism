# ADR-018 — Reuse Redis and Postgres connections

## Context

The search cache worked, but a cache hit still took about 1.5 s. `get_redis_client()` built a new client on every call, so each cache read and write opened a new TCP + TLS + AUTH connection to Upstash. Search and the worker also opened a new Postgres connection to Neon for every query, which takes about 1.75 s. MySQL (Aiven) connects in about 90 ms, so it is left as it is.

## Decision

- **Redis:** one client per process, created lazily under a lock (the same pattern as the Neo4j driver). Its connection pool is reused by every request and thread.
  - `health_check_interval=30` checks a connection that has been idle for 30 s before using it.
  - One retry (`Retry(NoBackoff(), 1)`) replaces a dropped connection. It is set explicitly because the default differs across redis-py versions.
  - 3 s socket timeouts stop an unreachable Redis from stalling searches.
- **Postgres:** `backend/modules/postgres.py` keeps up to 5 idle connections, and `run_pg(work)` lends one out.
  - Connections idle for more than 240 s are closed rather than reused, because Neon suspends idle compute after 5 minutes.
  - If a connection was dropped anyway, `work` runs once more on a new connection. This applies only when psycopg2 marks the connection closed, so ordinary SQL errors are not retried.
  - Pooled connections use autocommit, so a read is one round trip and returning a connection needs no rollback. The worker's vector insert uses `with conn:`, so it stays one transaction.
- The two copies of `get_postgres_conn()` are removed. Search, document delete and the worker all use `run_pg`.

## Measurements

Taken from the backend container on a home network against the live services. "Before" is 29 Oct 2026 on the old code; "after" is the same queries on the new code.

| | Before | After |
|---|---|---|
| Search, cache hit | 1,505 ms | 228 ms |
| Search, cache miss (connections already open) | 6,445 ms | 956 ms |
| Redis read inside a search | 1,383 ms | 224 ms |
| Redis write inside a search | 1,380 ms | 227 ms |
| pgvector query inside a search | 3,058 ms | 274 ms |
| `redis.from_url` calls for 26 searches | one per cache call (28) | 1 |

The first search after the backend starts still opens the connections once (4.8 s). Replacing a connection that the server dropped costs about 1.6 s for Redis and 2.0 s for Postgres, once.

## Consequences

- Repeat searches are fast, and the remaining time is mostly network round trips to Upstash and Neon (about 230–275 ms each).
- The pool assumes one backend process, as in ADR-015. Each extra process would keep its own pool.
- Follow-up, not part of this change: the worker inserts vectors with `executemany`, which makes one round trip per chunk. A 156-chunk PDF spends about 40 s on that alone, and a single multi-row insert (`psycopg2.extras.execute_values`) would cut it to one round trip.
- Follow-up: when Redis is unreachable, each cache call waits up to its timeout and the one retry before the search goes on without it.
