# slice-07 — Embedding and pgvector insert

**Sprint:** 2 — Document pipeline
**Module:** documents

## What to build

After chunking (slice-06), embed each chunk using `sentence-transformers/all-MiniLM-L6-v2` and insert the resulting 384-dimensional vectors into the pgvector `chunk_vectors` table. Run as part of the same background task.

## Acceptance criteria

- Each chunk in MySQL `chunks` has a corresponding row in pgvector `chunk_vectors` with a 384-dim vector
- Embedding model is loaded once at Flask startup — not re-loaded per request
- Entire upload pipeline (upload → chunk → embed) completes within 60 seconds for a 20-page PDF
- `documents.status` is updated to `ready` once all chunks are embedded successfully
- If embedding fails mid-way, already-inserted vectors are cleaned up and `documents.status` is set to `error`
- The whole operation runs inside a transaction — partial inserts do not persist

## Out of scope

- No model swapping
- No batch queue — `threading.Thread` is sufficient for v1

## Assigned To

Dev A

## Human review required?

No.
