# ADR-002 — Neo4j topic graph on upload (slice-12)

## Context

slice-12 writes `(User)-[:UPLOADED]->(Document)-[:ABOUT]->(Topic)` to Neo4j when
a document is uploaded with topic tags. New `backend/modules/graph/` module,
wired into the existing `/api/documents/upload` route.

## Decisions

- **Non-blocking, graceful write.** The graph write runs in a background daemon
  thread (via `write_document_to_graph_async`, mirroring slice-10's
  `log_search_async(sync=...)`) and `sync_document_to_graph` swallows every
  error. Together these satisfy the criterion that an unreachable Neo4j neither
  blocks nor fails the upload. Tests flip `GRAPH_WRITE_SYNC=True` to run the
  write inline for assertions. The driver uses a 5s acquisition timeout so a
  down server fails fast.
- **Single idempotent Cypher.** One statement uses `MERGE` for User/Document/
  Topic and both relationships, so repeated uploads create no duplicates.
  `UNWIND $topics` over an empty list is a no-op, so User/Document/UPLOADED are
  still written when a document has no topics.
- **Topic normalisation in the module.** `normalize_topics` trims, lowercases,
  and de-duplicates, so "Normalization" and "normalization" collapse to one
  `Topic` node. The route forwards raw strings; the graph module owns
  normalisation.
- **Flexible topic parsing.** The upload form accepts repeated `topics` /
  `topics[]` fields, a JSON-array string, or comma-separated values
  (`_parse_topics_from_form`).

## In scope vs out of scope

- **Neo4j only.** The MySQL `topics`/`doc_topics` tables (from slice-02) are
  intentionally NOT populated here — slice-12 is scoped to the graph. If a later
  slice needs relational topic storage, that is its own change.
- **No graph cleanup on delete.** slice-08's delete does not remove Neo4j nodes;
  slice-12 does not add that. Worth revisiting when graph-backed features grow,
  but out of scope here.
