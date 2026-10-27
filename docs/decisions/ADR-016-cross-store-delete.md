# ADR-016 — Cross-store delete is run by the route, not the trigger (slice-24)

## Context

A document's data lives in five stores: MySQL, pgvector, Neo4j, Redis and
object storage. slice-02 and slice-08 describe the `before_document_delete`
trigger as also removing `chunk_vectors`. A MySQL trigger cannot reach
PostgreSQL, Neo4j or object storage, so that was never possible.

## Decisions

- **The trigger only audits.** `before_document_delete` writes one row to
  `deletion_audit`. Within MySQL, `ON DELETE CASCADE` removes `chunks`,
  `doc_topics` and, through `chunks`, `search_results`.
- **The route orchestrates the other stores**, in this order:
  MySQL → pgvector → Neo4j → object storage → Redis. MySQL goes first because
  it is the source of truth. Once its row is gone, the document no longer
  exists for every read path, which checks ownership in MySQL. The later steps
  are best-effort: each is logged on failure and never turns the delete into
  an error. This replaces the slice-02 / slice-08 wording about the trigger.
- **Search analytics follow the documents that exist.** The cascade through
  `chunks` removes a deleted document's `search_results` rows, so it drops out
  of `top_documents` and the "unsearched" check, while `search_log` (the user's
  query history) is kept. This is intended.
- **Leftovers are cleaned by `backend/db/reconcile.py`.** It compares pgvector,
  Neo4j and object storage against MySQL and removes orphans. It is a dry run
  unless `--apply` is passed. It refuses to run without MySQL, and skips
  storage objects younger than 10 minutes so an upload in progress is never
  mistaken for an orphan.

## Out of scope

No scheduled or automatic reconciliation. The script is run by hand.
