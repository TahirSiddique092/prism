"""Database operations for the documents module using raw SQL."""

try:
    from backend.modules.auth.db import get_db_connection
except ImportError:
    from modules.auth.db import get_db_connection

def insert_document(user_id: int, title: str, minio_key: str, conn=None) -> int:
    """Insert a new document record into MySQL using raw SQL.
    
    Returns the newly generated doc_id.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        query = "INSERT INTO documents (user_id, title, minio_key) VALUES (%s, %s, %s)"
        cursor.execute(query, (user_id, title, minio_key))
        conn.commit()
        doc_id = cursor.lastrowid
        cursor.close()
        return doc_id
    finally:
        if should_close and conn:
            conn.close()
