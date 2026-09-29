# Sprint-03-search

> A sprint is a feature-level chunk of the Architecture — sized to however much you'll realistically tackle in one work block (a few hours, an all-nighter, a weekend). Not tied to a calendar week.

## Goal

End-to-end search pipeline working — semantic vector search via pgvector, FULLTEXT fallback when similarity is low, search logging, and Redis caching of results.

## Slices in this sprint

- [ ]  `slice-09-semantic-search` — Semantic search via pgvector — **Dev B**
- [ ]  `slice-10-fulltext-fallback-logging` — FULLTEXT fallback and search logging — **Dev B**
- [ ]  `slice-11-redis-cache` — Redis cache layer — **Dev A**

## Depends on

Sprint 2 — document chunks and embeddings must exist in pgvector.

## Notes for next time

*(Leave blank unless something actually broke, a slice was mis-sized, or the agent went off-script.)*
