"""Database operations for the analytics module using raw SQL with mysql-connector-python.

As per project guidelines (AGENTS.md):
- No ORMs (no SQLAlchemy, no abstractions)
- Explicit, visible SQL queries
- Raw SQL via mysql-connector-python
"""
import logging

try:
    from backend.modules.auth.db import get_db_connection
    from backend.modules.timeutils import to_utc_iso
except ImportError:
    from modules.auth.db import get_db_connection
    from modules.timeutils import to_utc_iso

logger = logging.getLogger(__name__)

# Search history ranked by frequency using SQL window functions (Slice 14)
SEARCH_HISTORY_QUERY = """
SELECT
    query_text,
    COUNT(*)                                             AS search_count,
    RANK() OVER (ORDER BY COUNT(*) DESC)                 AS query_rank,
    MAX(searched_at)                                     AS last_searched,
    SUM(COUNT(*)) OVER ()                                AS total_searches
FROM search_log
WHERE user_id = %s
GROUP BY query_text
ORDER BY query_rank;
"""

# Unsearched documents using Common Table Expression (CTE) (Slice 15).
# Only 'ready' documents: ones still processing or failed can't appear in results (slice-25).
UNSEARCHED_DOCS_QUERY = """
WITH searched_docs AS (
    SELECT DISTINCT d.doc_id
    FROM search_results sr
    JOIN chunks c ON sr.chunk_id = c.chunk_id
    JOIN documents d ON c.doc_id = d.doc_id
    JOIN search_log sl ON sr.log_id = sl.log_id
    WHERE sl.user_id = %s
)
SELECT doc_id, title, uploaded_at
FROM documents
WHERE user_id = %s
  AND status = 'ready'
  AND doc_id NOT IN (SELECT doc_id FROM searched_docs);
"""

# Top documents queried from top_documents SQL view (Slice 15). Ranked by the
# number of searches a document appeared in, then by passage hits (slice-25).
TOP_DOCUMENTS_QUERY = """
SELECT doc_id, title, search_count, appearance_count, avg_score
FROM top_documents
WHERE user_id = %s
ORDER BY search_count DESC, appearance_count DESC
LIMIT 10;
"""


def get_search_history(user_id: int, conn=None) -> list[dict]:
    """Retrieve search history ranked by frequency using SQL window functions (Slice 14).

    Acceptance criteria:
    - Response includes query_text, search_count, query_rank, last_searched, total_searches
    - Queries are ranked correctly — most searched query has rank 1
    - total_searches is the same across all rows (it's a grand total)
    - Returns an empty list if the user has no search history
    - Only returns the current user's queries — never another user's
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        try:
            cursor = conn.cursor(dictionary=True)
        except (TypeError, AttributeError):
            cursor = conn.cursor()

        cursor.execute(SEARCH_HISTORY_QUERY, (user_id,))
        rows = cursor.fetchall()
        cursor.close()

        results = []
        for row in rows:
            if isinstance(row, dict):
                query_text = row["query_text"]
                search_count = row["search_count"]
                query_rank = row["query_rank"]
                last_searched_val = row["last_searched"]
                total_searches = row["total_searches"]
            else:
                query_text, search_count, query_rank, last_searched_val, total_searches = (
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                )

            results.append({
                "query_text": str(query_text),
                "search_count": int(search_count),
                "query_rank": int(query_rank),
                "last_searched": to_utc_iso(last_searched_val),
                "total_searches": int(total_searches),
            })

        return results
    finally:
        if should_close and conn:
            conn.close()


def get_unsearched_documents(user_id: int, conn=None) -> list[dict]:
    """Retrieve documents the user uploaded that never appeared in search results (Slice 15).

    Acceptance criteria:
    - /unsearched returns only documents with zero appearances in search_results for this user
    - Returns an empty list if no unsearched documents exist
    - Never returns another user's documents
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        try:
            cursor = conn.cursor(dictionary=True)
        except (TypeError, AttributeError):
            cursor = conn.cursor()

        cursor.execute(UNSEARCHED_DOCS_QUERY, (user_id, user_id))
        rows = cursor.fetchall()
        cursor.close()

        results = []
        for row in rows:
            if isinstance(row, dict):
                doc_id = row["doc_id"]
                title = row["title"]
                uploaded_at_val = row["uploaded_at"]
            else:
                doc_id, title, uploaded_at_val = row[0], row[1], row[2]

            results.append({
                "doc_id": int(doc_id),
                "title": str(title),
                "uploaded_at": to_utc_iso(uploaded_at_val),
            })

        return results
    finally:
        if should_close and conn:
            conn.close()


def get_top_documents(user_id: int, conn=None) -> list[dict]:
    """Retrieve documents ranked by search appearances via top_documents view (Slice 15).

    Acceptance criteria:
    - /top-documents returns documents ordered by search_count, then appearance_count,
      descending (LIMIT 10). search_count is the number of searches the document
      appeared in; appearance_count the number of its passages returned (slice-25)
    - Returns an empty list when no data exists
    - Never returns another user's documents
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        try:
            cursor = conn.cursor(dictionary=True)
        except (TypeError, AttributeError):
            cursor = conn.cursor()

        cursor.execute(TOP_DOCUMENTS_QUERY, (user_id,))
        rows = cursor.fetchall()
        cursor.close()

        results = []
        for row in rows:
            if isinstance(row, dict):
                doc_id = row["doc_id"]
                title = row["title"]
                search_count = row["search_count"]
                appearance_count = row["appearance_count"]
                avg_score_val = row.get("avg_score")
            else:
                # Columns as selected: (doc_id, title, search_count, appearance_count, avg_score)
                doc_id, title, search_count, appearance_count, avg_score_val = row[:5]

            results.append({
                "doc_id": int(doc_id),
                "title": str(title),
                "search_count": int(search_count),
                "appearance_count": int(appearance_count),
                "avg_score": float(avg_score_val) if avg_score_val is not None else None,
            })

        return results
    finally:
        if should_close and conn:
            conn.close()
