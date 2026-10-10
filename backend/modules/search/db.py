"""Raw SQL database operations for the search module (Slice 09).

Executes explicit SQL queries across MySQL (metadata, documents, chunks)
and PostgreSQL pgvector (vector similarity search).
"""
import json
import os
import psycopg2

try:
    from backend.modules.auth.db import get_db_connection
except ImportError:
    from modules.auth.db import get_db_connection


def get_postgres_conn():
    """Return a new connection to PostgreSQL."""
    url = os.getenv("POSTGRES_URL")
    if url:
        return psycopg2.connect(url)
    return None


def get_user_document_ids(user_id: int, conn=None) -> list[int]:
    """Retrieve all document IDs belonging to a user from MySQL."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        query = "SELECT doc_id FROM documents WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        return [row[0] for row in rows]
    finally:
        if should_close and conn:
            conn.close()


def search_chunk_vectors(
    query_embedding: list[float],
    doc_ids: list[int],
    limit: int = 10,
    pg_conn=None,
) -> list[dict]:
    """Execute cosine distance search in pgvector filtered to doc_ids.
    
    Operator <=> returns cosine distance (lower = more similar).
    Returns list of dicts: [{ chunk_id, doc_id, score }].
    """
    if not doc_ids:
        return []

    should_close = False
    if pg_conn is None:
        pg_conn = get_postgres_conn()
        should_close = True

    if not pg_conn:
        raise RuntimeError("PostgreSQL connection unavailable")

    try:
        vec_str = json.dumps(query_embedding)

        with pg_conn.cursor() as cursor:
            query = """
                SELECT chunk_id, doc_id, (embedding <=> %s::vector) AS score
                FROM chunk_vectors
                WHERE doc_id = ANY(%s)
                ORDER BY score ASC
                LIMIT %s
            """
            cursor.execute(query, (vec_str, doc_ids, limit))
            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                "chunk_id": int(row[0]),
                "doc_id": int(row[1]),
                "score": float(row[2]),
            })
        return results
    finally:
        if should_close and pg_conn:
            pg_conn.close()


def get_chunks_metadata(chunk_ids: list[int], conn=None) -> dict[int, dict]:
    """Retrieve snippet and document title metadata for chunk_ids from MySQL."""
    if not chunk_ids:
        return {}

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        try:
            cursor = conn.cursor(dictionary=True)
        except TypeError:
            cursor = conn.cursor()

        format_strings = ",".join(["%s"] * len(chunk_ids))
        query = f"""
            SELECT 
                c.chunk_id, 
                c.doc_id, 
                c.chunk_text AS snippet, 
                d.title AS doc_title
            FROM chunks c
            JOIN documents d ON c.doc_id = d.doc_id
            WHERE c.chunk_id IN ({format_strings})
        """
        cursor.execute(query, tuple(chunk_ids))
        rows = cursor.fetchall()
        cursor.close()

        metadata = {}
        for row in rows:
            if isinstance(row, dict):
                c_id = row["chunk_id"]
                metadata[c_id] = {
                    "chunk_id": c_id,
                    "doc_id": row["doc_id"],
                    "snippet": row["snippet"],
                    "doc_title": row["doc_title"],
                }
            else:
                c_id = row[0]
                metadata[c_id] = {
                    "chunk_id": c_id,
                    "doc_id": row[1],
                    "snippet": row[2],
                    "doc_title": row[3],
                }
        return metadata
    finally:
        if should_close and conn:
            conn.close()


def search_chunks_fulltext(
    user_id: int,
    query: str,
    limit: int = 10,
    conn=None,
) -> list[dict]:
    """Execute MySQL FULLTEXT search against chunks table filtered to user's documents (Slice 10).
    
    AC:
    - Triggered when best cosine distance from pgvector exceeds 0.75.
    - Run: SELECT chunk_id, chunk_text FROM chunks WHERE MATCH(chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE)
    - Filter to current user's documents only.
    - Return results in same response shape as semantic search:
      [{ chunk_id, doc_id, doc_title, snippet, score: None }]
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        try:
            cursor = conn.cursor(dictionary=True)
        except TypeError:
            cursor = conn.cursor()

        query_sql = """
            SELECT 
                c.chunk_id, 
                c.doc_id, 
                d.title AS doc_title, 
                c.chunk_text AS snippet
            FROM chunks c
            JOIN documents d ON c.doc_id = d.doc_id
            WHERE d.user_id = %s
              AND MATCH(c.chunk_text) AGAINST(%s IN NATURAL LANGUAGE MODE)
            LIMIT %s
        """
        cursor.execute(query_sql, (user_id, clean_query, limit))
        rows = cursor.fetchall()
        cursor.close()

        results = []
        for row in rows:
            if isinstance(row, dict):
                results.append({
                    "chunk_id": int(row["chunk_id"]),
                    "doc_id": int(row["doc_id"]),
                    "doc_title": str(row["doc_title"]),
                    "snippet": str(row["snippet"]),
                    "score": None,
                })
            else:
                results.append({
                    "chunk_id": int(row[0]),
                    "doc_id": int(row[1]),
                    "doc_title": str(row[2]),
                    "snippet": str(row[3]),
                    "score": None,
                })
        return results
    finally:
        if should_close and conn:
            conn.close()


def insert_search_log(user_id: int, query_text: str, conn=None) -> int:
    """Insert a single search record into search_log in MySQL (Slice 10).
    
    Returns the generated log_id.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        query = "INSERT INTO search_log (user_id, query_text) VALUES (%s, %s)"
        cursor.execute(query, (user_id, query_text))
        if hasattr(conn, "commit"):
            conn.commit()
        log_id = cursor.lastrowid
        cursor.close()
        return log_id
    finally:
        if should_close and conn:
            conn.close()


def insert_search_results(log_id: int, results: list[dict], conn=None) -> None:
    """Insert search result rows into search_results linked to log_id with rank 1..10 (Slice 10).
    
    Each result dict contains chunk_id and optional score (None for fallback).
    """
    if not results or not log_id:
        return

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO search_results (log_id, chunk_id, rank, similarity_score)
            VALUES (%s, %s, %s, %s)
        """
        records = [
            (log_id, res["chunk_id"], rank, res.get("score"))
            for rank, res in enumerate(results[:10], start=1)
        ]
        cursor.executemany(query, records)
        if hasattr(conn, "commit"):
            conn.commit()
        cursor.close()
    finally:
        if should_close and conn:
            conn.close()

