# slice-09 — Semantic search via pgvector

**Sprint:** 3 — Search
**Module:** search

## What to build

`POST /api/search` — embed the query, run cosine similarity search against pgvector, return the top-10 most relevant chunks with metadata.

## Endpoint

**POST /api/search**
- Request: `{ query }` (plain English string)
- Response: `[{ chunk_id, doc_id, doc_title, snippet, score }]`

## Search logic

1. Check Redis cache — if hit, return cached result immediately
2. Embed the query using the same model (`all-MiniLM-L6-v2`)
3. Run pgvector query: `SELECT ... ORDER BY embedding <=> query_vec LIMIT 10`
4. Filter results to only chunks belonging to the authenticated user's documents
5. If best score > 0.75 — hand off to FULLTEXT fallback (slice-10)
6. Log the search and results (slice-10 also handles this)

## Acceptance criteria

- A query with zero overlapping words with the target chunk still returns a relevant result
- Results are filtered to the current user's documents only — never surface other users' content
- Cache is checked before any embedding is computed
- Response time under 3 seconds for a cold cache hit
- `score` in response is the raw cosine distance (lower = more similar)

## Out of scope

- No fallback logic here — that's slice-10
- No logging here — that's slice-10

## Assigned To

Dev B

## Human review required?

No.
