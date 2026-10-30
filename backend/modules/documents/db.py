"""Database operations for the documents module using raw SQL."""

try:
    from backend.modules.auth.db import get_db_connection
    from backend.modules.postgres import run_pg
    from backend.modules.timeutils import to_utc_iso
except ImportError:
    from modules.auth.db import get_db_connection
    from modules.postgres import run_pg
    from modules.timeutils import to_utc_iso

def insert_document(user_id: int, title: str, minio_key: str, conn=None) -> int:
    """Insert a new document record into MySQL using raw SQL.
    
    Returns the newly generated doc_id.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        # Prepared statement: user text is sent apart from the SQL (ADR-017).
        cursor = conn.cursor(prepared=True)
        query = "INSERT INTO documents (user_id, title, minio_key) VALUES (%s, %s, %s)"
        cursor.execute(query, (user_id, title, minio_key))
        conn.commit()
        doc_id = cursor.lastrowid
        cursor.close()
        return doc_id
    finally:
        if should_close and conn:
            conn.close()

def update_document_status(doc_id: int, status: str, conn=None):
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        query = "UPDATE documents SET status = %s WHERE doc_id = %s"
        cursor.execute(query, (status, doc_id))
        conn.commit()
        cursor.close()
    finally:
        if should_close and conn:
            conn.close()

def claim_for_retry(doc_id: int, user_id: int, conn=None) -> bool:
    """Move one of the user's failed documents back to 'processing' (slice-28).

    A single conditional UPDATE, so two retries at the same time can't both
    start processing: only the first one changes the row.
    Returns True if the document was 'error' and is now 'processing'.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        query = (
            "UPDATE documents SET status = 'processing' "
            "WHERE doc_id = %s AND user_id = %s AND status = 'error'"
        )
        cursor.execute(query, (doc_id, user_id))
        conn.commit()
        claimed = cursor.rowcount == 1
        cursor.close()
        return claimed
    finally:
        if should_close and conn:
            conn.close()


def mark_interrupted_processing_failed(conn=None) -> int:
    """Set every document still 'processing' to 'error' (slice-28).

    Called when the backend starts. Processing only runs in background threads
    of the backend process, so at start-up nothing can still be in progress: a
    'processing' document was interrupted by a restart. As 'error' it can be
    retried. Assumes a single backend process (ADR-015).
    Returns the number of documents changed.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE documents SET status = 'error' WHERE status = 'processing'")
        conn.commit()
        changed = cursor.rowcount
        cursor.close()
        return changed
    finally:
        if should_close and conn:
            conn.close()


# Rows per multi-row INSERT in insert_chunks. 5 placeholders per row keeps each
# statement far below MySQL's 65,535 prepared-statement placeholder limit.
CHUNK_INSERT_BATCH = 500


def insert_chunks(doc_id: int, chunks_list: list, conn=None, pages=None):
    """Bulk insert chunks for a document.

    ``pages`` is a list of (page_start, page_end) per chunk, 1-based (slice-27).
    Without it, or for a chunk whose pages are unknown, they are stored as NULL.

    Uses a prepared multi-row INSERT per batch instead of executemany():
    executemany() inlines the PDF text into the SQL string, and the driver
    rewrites any statement whose text contains "DELIMITER ..." (common in
    DBMS notes), corrupting or breaking the INSERT (ADR-017).
    """
    if not chunks_list:
        return
    if pages is None:
        pages = [(None, None)] * len(chunks_list)

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor(prepared=True)
        # chunks_list is a list of strings
        rows = [
            (doc_id, text, idx, page_start, page_end)
            for idx, (text, (page_start, page_end)) in enumerate(zip(chunks_list, pages))
        ]
        for start in range(0, len(rows), CHUNK_INSERT_BATCH):
            batch = rows[start:start + CHUNK_INSERT_BATCH]
            placeholders = ", ".join(["(%s, %s, %s, %s, %s)"] * len(batch))
            query = (
                "INSERT INTO chunks (doc_id, chunk_text, chunk_index, page_start, page_end) "
                f"VALUES {placeholders}"
            )
            cursor.execute(query, [value for row in batch for value in row])
        conn.commit()
        cursor.close()
    finally:
        if should_close and conn:
            conn.close()

def insert_document_topics(doc_id: int, topic_names: list, conn=None):
    """Store a document's topic tags in topics / doc_topics (Slice 24).

    ``topic_names`` must already be normalised (graph.normalize_topics) so MySQL
    and Neo4j hold identical names. INSERT IGNORE makes both statements
    idempotent: an existing topic or doc_topics pair is left as is.
    """
    if not topic_names:
        return

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        # Prepared statements: user text is sent apart from the SQL (ADR-017).
        cursor = conn.cursor(prepared=True)
        cursor.execute(
            "INSERT IGNORE INTO topics (name) VALUES " + ", ".join(["(%s)"] * len(topic_names)),
            list(topic_names),
        )
        placeholders = ",".join(["%s"] * len(topic_names))
        query = f"""
            INSERT IGNORE INTO doc_topics (doc_id, topic_id)
            SELECT %s, topic_id FROM topics WHERE name IN ({placeholders})
        """
        cursor.execute(query, (doc_id, *topic_names))
        conn.commit()
        cursor.close()
    finally:
        if should_close and conn:
            conn.close()

def get_document_owner(doc_id: int, conn=None):
    """Return the user_id that owns a document, or None if it does not exist."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM documents WHERE doc_id = %s", (doc_id,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return row[0]
    finally:
        if should_close and conn:
            conn.close()


def get_existing_doc_ids(user_id: int, doc_ids: list, conn=None) -> set:
    """Return the subset of ``doc_ids`` that still exist for this user (Slice 24).

    MySQL is the source of truth, so graph results are filtered through this
    before being returned to the client.
    """
    if not doc_ids:
        return set()

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        placeholders = ",".join(["%s"] * len(doc_ids))
        query = f"SELECT doc_id FROM documents WHERE user_id = %s AND doc_id IN ({placeholders})"
        cursor.execute(query, (user_id, *doc_ids))
        rows = cursor.fetchall()
        cursor.close()
        return {row[0] for row in rows}
    finally:
        if should_close and conn:
            conn.close()


def get_chunk(doc_id: int, chunk_id: int, user_id: int, conn=None) -> dict | None:
    """One chunk of one of the user's documents, with its pages (slice-27).

    Returns None unless the chunk belongs to ``doc_id`` and that document
    belongs to ``user_id``.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        query = """
            SELECT c.chunk_id, c.chunk_text, c.page_start, c.page_end
            FROM chunks c
            JOIN documents d ON c.doc_id = d.doc_id
            WHERE c.chunk_id = %s AND c.doc_id = %s AND d.user_id = %s
        """
        cursor.execute(query, (chunk_id, doc_id, user_id))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return {"chunk_id": row[0], "chunk_text": row[1], "page_start": row[2], "page_end": row[3]}
    finally:
        if should_close and conn:
            conn.close()


def get_chunks_for_document(doc_id: int, conn=None):
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT chunk_id, chunk_text FROM chunks WHERE doc_id = %s ORDER BY chunk_index", (doc_id,))
        results = cursor.fetchall()
        cursor.close()
        return results
    finally:
        if should_close and conn:
            conn.close()

def delete_chunks(doc_id: int, conn=None):
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
        conn.commit()
        cursor.close()
    finally:
        if should_close and conn:
            conn.close()

def get_user_documents(user_id: int, conn=None) -> list[dict]:
    """Retrieve all documents belonging to a user with their chunk counts.
    
    Returns list of dicts: [{ doc_id, title, uploaded_at, status, chunk_count }]
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        try:
            cursor = conn.cursor(dictionary=True)
        except TypeError:
            cursor = conn.cursor()

        query = """
            SELECT 
                d.doc_id, 
                d.title, 
                d.uploaded_at, 
                d.status, 
                COUNT(c.chunk_id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON d.doc_id = c.doc_id
            WHERE d.user_id = %s
            GROUP BY d.doc_id, d.title, d.uploaded_at, d.status
            ORDER BY d.uploaded_at DESC
        """
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        cursor.close()

        results = []
        for row in rows:
            if isinstance(row, dict):
                doc_id = row["doc_id"]
                title = row["title"]
                uploaded_at_val = row["uploaded_at"]
                status_val = row.get("status")
                chunk_count = row["chunk_count"]
            else:
                doc_id, title, uploaded_at_val, status_val, chunk_count = (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                )

            results.append({
                "doc_id": doc_id,
                "title": title,
                "uploaded_at": to_utc_iso(uploaded_at_val),
                "status": status_val or "ready",
                "chunk_count": int(chunk_count) if chunk_count is not None else 0,
            })
        return results
    finally:
        if should_close and conn:
            conn.close()

def get_document_chunk_count(doc_id: int, conn=None) -> int:
    """Return the number of chunks stored for a document (Slice 20).

    Kept as its own explicit query so the document-detail endpoint can report a
    chunk count without pulling the whole document list.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE doc_id = %s", (doc_id,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return 0
        count = row[0]
        return int(count) if count is not None else 0
    finally:
        if should_close and conn:
            conn.close()

def get_document_by_id(doc_id: int, user_id: int = None, conn=None) -> dict | None:
    """Retrieve document details by doc_id, optionally scoping by user_id."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        try:
            cursor = conn.cursor(dictionary=True)
        except TypeError:
            cursor = conn.cursor()

        if user_id is not None:
            query = "SELECT doc_id, user_id, title, minio_key, uploaded_at, status FROM documents WHERE doc_id = %s AND user_id = %s"
            cursor.execute(query, (doc_id, user_id))
        else:
            query = "SELECT doc_id, user_id, title, minio_key, uploaded_at, status FROM documents WHERE doc_id = %s"
            cursor.execute(query, (doc_id,))

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        if isinstance(row, dict):
            return row
        return {
            "doc_id": row[0],
            "user_id": row[1],
            "title": row[2],
            "minio_key": row[3],
            "uploaded_at": row[4],
            "status": row[5] if len(row) > 5 else "ready",
        }
    finally:
        if should_close and conn:
            conn.close()

def delete_document(doc_id: int, user_id: int = None, conn=None) -> bool:
    """Delete a document row from MySQL.
    
    This activates the MySQL trigger before_document_delete which logs to deletion_audit,
    and ON DELETE CASCADE automatically deletes corresponding chunks.
    Returns True if a row was deleted, False if no document matched.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        if user_id is not None:
            query = "DELETE FROM documents WHERE doc_id = %s AND user_id = %s"
            cursor.execute(query, (doc_id, user_id))
        else:
            query = "DELETE FROM documents WHERE doc_id = %s"
            cursor.execute(query, (doc_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()
        return deleted
    finally:
        if should_close and conn:
            conn.close()

def delete_chunk_vectors(doc_id: int, conn=None):
    """Delete vectors for the document from pgvector chunk_vectors table.

    Uses ``conn`` if given, otherwise a pooled connection (slice-29).
    """
    def delete_vectors(pg_conn):
        with pg_conn.cursor() as cursor:
            cursor.execute("DELETE FROM chunk_vectors WHERE doc_id = %s", (doc_id,))
        pg_conn.commit()

    if conn is not None:
        delete_vectors(conn)
    else:
        run_pg(delete_vectors)
