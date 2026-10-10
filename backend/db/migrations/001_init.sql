-- ENGINE: MySQL

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    doc_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    minio_key VARCHAR(255) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE topics (
    topic_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE doc_topics (
    doc_id INT NOT NULL,
    topic_id INT NOT NULL,
    PRIMARY KEY (doc_id, topic_id),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE,
    FOREIGN KEY (topic_id) REFERENCES topics(topic_id) ON DELETE CASCADE
);

CREATE TABLE chunks (
    chunk_id INT AUTO_INCREMENT PRIMARY KEY,
    doc_id INT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_index INT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);
CREATE FULLTEXT INDEX ft_chunk_text ON chunks(chunk_text);

CREATE TABLE search_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    query_text TEXT NOT NULL,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX idx_search_log_user_time ON search_log(user_id, searched_at);

CREATE TABLE search_results (
    result_id INT AUTO_INCREMENT PRIMARY KEY,
    log_id INT NOT NULL,
    chunk_id INT NOT NULL,
    rank INT NOT NULL,
    similarity_score FLOAT,
    FOREIGN KEY (log_id) REFERENCES search_log(log_id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE
);

CREATE OR REPLACE VIEW top_documents AS
SELECT
    d.user_id,
    d.doc_id,
    d.title,
    COUNT(sr.result_id)          AS appearance_count,
    AVG(sr.similarity_score)     AS avg_score
FROM search_results sr
JOIN chunks c ON sr.chunk_id = c.chunk_id
JOIN documents d ON c.doc_id = d.doc_id
GROUP BY d.doc_id, d.user_id, d.title;

CREATE TABLE deletion_audit (
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    doc_id INT NOT NULL,
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DELIMITER //
CREATE TRIGGER before_document_delete
BEFORE DELETE ON documents
FOR EACH ROW
BEGIN
    INSERT INTO deletion_audit (doc_id, deleted_at) VALUES (OLD.doc_id, NOW());
END; //
DELIMITER ;


-- ENGINE: Postgres

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunk_vectors (
    chunk_id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL,
    embedding VECTOR(384)
);

CREATE INDEX idx_chunk_vectors_embedding ON chunk_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
