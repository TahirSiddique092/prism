# slice-02 — MySQL + pgvector schema and migrations

**Sprint:** 1 — Foundation
**Module:** infra

## What to build

Write and run all DDL for MySQL and pgvector. This is the single source of truth for the database schema — all other slices depend on this.

## MySQL tables

```sql
users(user_id PK, name, email UNIQUE, password_hash, created_at)
documents(doc_id PK, user_id FK, title, minio_key, uploaded_at)
topics(topic_id PK, name UNIQUE)
doc_topics(doc_id FK, topic_id FK)
chunks(chunk_id PK, doc_id FK, chunk_text FULLTEXT, chunk_index)
search_log(log_id PK, user_id FK, query_text, searched_at)
search_results(result_id PK, log_id FK, chunk_id FK, rank, similarity_score)
deletion_audit(audit_id PK, doc_id, deleted_at)
```

## pgvector table

```sql
chunk_vectors(chunk_id PK, doc_id, embedding VECTOR(384))
```

## Trigger to add

```sql
-- Auto-delete chunk_vectors and log to deletion_audit when a document is deleted
BEFORE DELETE ON documents FOR EACH ROW
```

## Acceptance criteria

- All MySQL tables created with correct PKs, FKs, and constraints
- `chunks.chunk_text` has a FULLTEXT index
- `search_log` has a composite index on `(user_id, searched_at)`
- pgvector table created with `VECTOR(384)` column and an ivfflat index
- Trigger exists and fires correctly — deleting a document removes its chunks and logs to `deletion_audit`
- All DDL lives in `backend/db/migrations/001_init.sql` — runnable as a single script

## Out of scope

- No seed data
- No ORM — raw SQL only

## Assigned To

Dev A

## Human review required?

Yes — destructive migrations (DDL with triggers and cascading deletes).
