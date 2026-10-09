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

def insert_chunks(doc_id: int, chunks_list: list, conn=None):
    """Bulk insert chunks for a document."""
    if not chunks_list:
        return
        
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        query = "INSERT INTO chunks (doc_id, chunk_text, chunk_index) VALUES (%s, %s, %s)"
        # chunks_list is a list of strings
        data = [(doc_id, text, idx) for idx, text in enumerate(chunks_list)]
        cursor.executemany(query, data)
        conn.commit()
        cursor.close()
    finally:
        if should_close and conn:
            conn.close()

import os
import psycopg2

def get_postgres_conn():
    url = os.getenv("POSTGRES_URL")
    if url:
        return psycopg2.connect(url)
    return None

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
