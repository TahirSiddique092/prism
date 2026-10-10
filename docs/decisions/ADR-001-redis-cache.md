# ADR-001 — Redis search cache (slice-11)

## Context

Slice-11 adds a reusable `cache` module wrapping Redis, consumed by `search`
and invalidated by `documents`.

## Decisions

- **SCAN over KEYS for invalidation.** `invalidate_user_cache` uses
  `scan_iter(match="search:{user_id}:*")` instead of `KEYS`, which blocks Redis
  on large keyspaces. Correctness is identical for our access pattern.
- **Graceful degradation everywhere.** Every Redis call is wrapped in
  try/except. Reads return `None` (treated as a miss), writes and invalidation
  become no-ops. A Redis outage can never 500 a consuming endpoint
  (slice-11 acceptance criterion).
- **Built standalone, ahead of consumers.** Slice-09 (search) and the slice-08
  delete endpoint do not exist yet. This slice ships the fully unit-tested cache
  module plus the one invalidation hook that exists today (document upload).
  `get_cached_search` / `set_cached_search` are the seam slice-09 plugs into;
  `invalidate_user_cache` is the seam slice-08's delete plugs into.

## Open / to reconcile

- **`GET` vs `POST /api/search`.** slice-11 references `GET /api/search` with a
  `cached: true/false` field; slice-09 defines `POST /api/search`. The
  `cached` field and the "repeated query skips pgvector" criterion must be
  implemented and tested when slice-09 wires in `get_cached_search` /
  `set_cached_search`. Resolve the verb when building slice-09.
