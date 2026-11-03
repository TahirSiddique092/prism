-- ENGINE: MySQL

-- slice-33: the two analytics queries as stored procedures, called with
-- cursor.callproc from backend/modules/analytics/db.py. Each one is dropped
-- first so the migration can be applied again. Strings use single quotes:
-- Aiven runs MySQL with ANSI_QUOTES, where double quotes mean identifiers.

DELIMITER //

DROP PROCEDURE IF EXISTS sp_search_history //

-- Search history ranked by frequency, using window functions
CREATE PROCEDURE sp_search_history(IN p_user_id INT)
READS SQL DATA
BEGIN
    SELECT
        query_text,
        COUNT(*)                             AS search_count,
        RANK() OVER (ORDER BY COUNT(*) DESC) AS query_rank,
        MAX(searched_at)                     AS last_searched,
        SUM(COUNT(*)) OVER ()                AS total_searches
    FROM search_log
    WHERE user_id = p_user_id
    GROUP BY query_text
    ORDER BY query_rank;
END //

DROP PROCEDURE IF EXISTS sp_unsearched_documents //

-- Ready documents that never appeared in the user's search results, using a CTE
CREATE PROCEDURE sp_unsearched_documents(IN p_user_id INT)
READS SQL DATA
BEGIN
    WITH searched_docs AS (
        SELECT DISTINCT d.doc_id
        FROM search_results sr
        JOIN chunks c ON sr.chunk_id = c.chunk_id
        JOIN documents d ON c.doc_id = d.doc_id
        JOIN search_log sl ON sr.log_id = sl.log_id
        WHERE sl.user_id = p_user_id
    )
    SELECT doc_id, title, uploaded_at
    FROM documents
    WHERE user_id = p_user_id
      AND status = 'ready'
      AND doc_id NOT IN (SELECT doc_id FROM searched_docs);
END //

DELIMITER ;
