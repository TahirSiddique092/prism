# ADR-001 — Redis search cache: use SCAN for invalidation (slice-11)

## Context

The Redis search cache (`backend/modules/cache/service.py`) landed as part of
slice-09 and is consumed by `search` (cache read/write) and `documents`
(invalidation on upload and delete). slice-11's acceptance criteria are already
satisfied by that module.

While reconciling slice-11 against `main`, one production-safety issue remained
in `invalidate_user_cache`: it enumerated keys with `KEYS search:{user_id}:*`.

## Decision

Replace `KEYS` with `SCAN` (`redis.scan_iter(match=..., count=100)`) in
`invalidate_user_cache`.

`KEYS` is O(N) over the entire keyspace and blocks the Redis server for the
duration — on a production instance with many keys this can stall all clients.
`SCAN` iterates incrementally without blocking and returns the same set of keys
for our pattern. Behaviour is otherwise identical: matched keys are deleted,
errors are caught and logged, and the function never raises.

## Status

Accepted. This is the only change in this branch over `main`; the rest of the
cache module, its consumers, and invalidation hooks are unchanged.
