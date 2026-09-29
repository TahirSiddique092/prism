# slice-10 — FULLTEXT fallback and search logging

**Sprint:** 3 — Search
**Module:** search

## What to build

Two additions to the search pipeline: (1) MySQL FULLTEXT fallback when vector similarity is too low, and (2) logging every search and its results to `search_log` and `search_results`.

## Fallback logic

- Triggered when the best cosine distance from pgvector exceeds 0.75
- Run: `SELECT chunk_id, chunk_text FROM chunks WHERE MATCH(chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE)`
- Filter to the current user's documents only
- Return results in the same response shape as semantic search, with `score: null` to indicate fallback was used

## Logging logic

- After every search (semantic or fallback), insert one row into `search_log`
- Insert one row per result into `search_results` with rank and similarity score
- Logging must not block the response — write after sending results

## Acceptance criteria

- When all vector scores exceed 0.75, FULLTEXT results are returned instead
- FULLTEXT results are still filtered to the current user's documents
- Every `POST /api/search` call produces exactly one `search_log` row
- `search_results` rows are correctly linked to the `search_log` row with rank 1–10
- A search that returns zero results still logs to `search_log` (with no `search_results` rows)
- Logging failure does not cause the search response to fail

## Out of scope

- No hybrid merging of vector + fulltext results in v1
- No relevance tuning of FULLTEXT scoring

## Assigned To

Dev B

## Human review required?

No.
