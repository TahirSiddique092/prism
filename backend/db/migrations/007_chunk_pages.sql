-- ENGINE: MySQL

-- slice-27: the PDF pages each chunk starts and ends on (1-based), so a search
-- result can open the document at its passage. NULL means unknown, which is
-- the case for chunks stored before this migration until they are backfilled
-- (backend/db/backfill_chunk_pages.py).
ALTER TABLE chunks
    ADD COLUMN page_start INT NULL,
    ADD COLUMN page_end INT NULL;
