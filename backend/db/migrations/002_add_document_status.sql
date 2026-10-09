-- ENGINE: MySQL
ALTER TABLE documents ADD COLUMN status VARCHAR(50) DEFAULT 'processing';
