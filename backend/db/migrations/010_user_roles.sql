-- ENGINE: MySQL

-- slice-35: role-based access control and the admin view.
-- Every account is 'user' or 'admin'. The CHECK constraint is added in the
-- same statement as the column, so re-running the migration only meets the
-- tolerated duplicate-column error.
ALTER TABLE users
    ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user',
    ADD CONSTRAINT chk_users_role CHECK (role IN ('user', 'admin'));

-- The deletion log also records who owned the deleted document and its title.
-- Rows written before this migration keep NULL in both.
ALTER TABLE deletion_audit
    ADD COLUMN user_id INT NULL,
    ADD COLUMN title VARCHAR(255) NULL;

DELIMITER //

DROP TRIGGER IF EXISTS before_document_delete //

CREATE TRIGGER before_document_delete
BEFORE DELETE ON documents
FOR EACH ROW
BEGIN
    INSERT INTO deletion_audit (doc_id, user_id, title, deleted_at)
    VALUES (OLD.doc_id, OLD.user_id, OLD.title, NOW());
END //

DROP FUNCTION IF EXISTS fn_user_document_count //

-- Number of documents a user has uploaded
CREATE FUNCTION fn_user_document_count(p_user_id INT)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE total INT;
    SELECT COUNT(*) INTO total FROM documents WHERE user_id = p_user_id;
    RETURN total;
END //

DROP FUNCTION IF EXISTS fn_user_search_count //

-- Number of searches a user has run
CREATE FUNCTION fn_user_search_count(p_user_id INT)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE total INT;
    SELECT COUNT(*) INTO total FROM search_log WHERE user_id = p_user_id;
    RETURN total;
END //

DROP PROCEDURE IF EXISTS sp_admin_user_overview //

-- Every user with their activity counts (no password hash, no search text)
CREATE PROCEDURE sp_admin_user_overview()
READS SQL DATA
BEGIN
    SELECT
        u.user_id,
        u.name,
        u.email,
        u.role,
        u.created_at,
        fn_user_document_count(u.user_id) AS documents,
        (SELECT COALESCE(SUM(fn_chunk_count(d.doc_id)), 0)
           FROM documents d WHERE d.user_id = u.user_id) AS chunks,
        fn_user_search_count(u.user_id) AS searches,
        (SELECT MAX(sl.searched_at)
           FROM search_log sl WHERE sl.user_id = u.user_id) AS last_search_at
    FROM users u
    ORDER BY u.created_at;
END //

DROP PROCEDURE IF EXISTS sp_admin_system_stats //

-- System-wide totals in one row. Today means the current UTC day.
CREATE PROCEDURE sp_admin_system_stats()
READS SQL DATA
BEGIN
    SELECT
        (SELECT COUNT(*) FROM users)                                   AS users,
        (SELECT COUNT(*) FROM users WHERE role = 'admin')              AS admins,
        (SELECT COUNT(*) FROM documents)                               AS documents,
        (SELECT COUNT(*) FROM documents WHERE status = 'processing')   AS documents_processing,
        (SELECT COUNT(*) FROM documents WHERE status = 'ready')        AS documents_ready,
        (SELECT COUNT(*) FROM documents WHERE status = 'error')        AS documents_error,
        (SELECT COUNT(*) FROM chunks)                                  AS chunks,
        (SELECT COUNT(*) FROM search_log)                              AS searches,
        (SELECT COUNT(*) FROM search_log WHERE searched_at >= UTC_DATE()) AS searches_today,
        (SELECT COUNT(*) FROM deletion_audit)                          AS deletions;
END //

DELIMITER ;
