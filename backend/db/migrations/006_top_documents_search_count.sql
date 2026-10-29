-- ENGINE: MySQL

-- slice-25: also count the searches a document appeared in.
-- appearance_count counts search_results rows, and each search stores up to
-- 10 passages, so one search could add 10 to a single document.
-- search_count counts each search (log_id) once.
CREATE OR REPLACE VIEW top_documents AS
SELECT
    d.user_id,
    d.doc_id,
    d.title,
    COUNT(sr.result_id)          AS appearance_count,
    AVG(sr.similarity_score)     AS avg_score,
    COUNT(DISTINCT sr.log_id)    AS search_count
FROM search_results sr
JOIN chunks c ON sr.chunk_id = c.chunk_id
JOIN documents d ON c.doc_id = d.doc_id
GROUP BY d.doc_id, d.user_id, d.title;
