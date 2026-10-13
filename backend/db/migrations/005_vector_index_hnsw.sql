-- Replace the ivfflat vector index with HNSW.
--
-- ivfflat trains its centroid lists from existing rows at CREATE INDEX time.
-- 001_init.sql builds it on an empty chunk_vectors table, so the lists are
-- trained on zero rows and every subsequent search uses a poorly-formed index
-- (degraded recall) until a manual REINDEX after data load. HNSW is a graph
-- index that does not require training data and builds correctly on an empty
-- table, so it stays correct as rows are inserted incrementally.

-- ENGINE: Postgres

DROP INDEX IF EXISTS idx_chunk_vectors_embedding;

CREATE INDEX idx_chunk_vectors_embedding
    ON chunk_vectors
    USING hnsw (embedding vector_cosine_ops);
