-- ENGINE: MySQL

-- slice-34: user-defined functions used inside the app's queries. Each one
-- declares what kind of SQL it runs: Aiven has binary logging on, and MySQL
-- refuses CREATE FUNCTION without that (error 1418). Each is dropped first so
-- the migration can be applied again.

DELIMITER //

DROP FUNCTION IF EXISTS fn_chunk_count //

-- Number of chunks stored for a document (0 if it has none)
CREATE FUNCTION fn_chunk_count(p_doc_id INT)
RETURNS INT
READS SQL DATA
BEGIN
    DECLARE total INT;
    SELECT COUNT(*) INTO total FROM chunks WHERE doc_id = p_doc_id;
    RETURN total;
END //

DROP FUNCTION IF EXISTS fn_similarity //

-- Cosine similarity from a cosine distance: 1 - distance, and NULL stays NULL
CREATE FUNCTION fn_similarity(p_distance DOUBLE)
RETURNS DOUBLE
DETERMINISTIC
NO SQL
RETURN 1 - p_distance //

DELIMITER ;
