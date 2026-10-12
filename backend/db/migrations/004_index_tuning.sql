-- ENGINE: MySQL

-- Slice 21: Index tuning
-- Note: Composite index idx_search_log_user_time on search_log(user_id, searched_at) was established in 001_init.sql
-- Add explicit secondary indexes on search_results foreign keys to optimize join chain queries
CREATE INDEX idx_search_results_log_id ON search_results(log_id);
CREATE INDEX idx_search_results_chunk_id ON search_results(chunk_id);
