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
    from backend.modules.dblog import call_procedure, log_db_event, logged_db_call
except ImportError:
    from modules.auth.db import get_db_connection
    from modules.timeutils import to_utc_iso
    from modules.dblog import call_procedure, log_db_event, logged_db_call

logger = logging.getLogger(__name__)

# The search-history (window functions) and unsearched-documents (CTE) queries
# live in MySQL as stored procedures sp_search_history and sp_unsearched_documents,
# created by migrations/008_stored_procedures.sql (slice-33).

# Top documents queried from top_documents SQL view (Slice 15). Ranked by the
# number of searches a document appeared in, then by passage hits (slice-25).
# avg_similarity comes from the stored function fn_similarity (slice-34).
TOP_DOCUMENTS_QUERY = """
SELECT doc_id, title, search_count, appearance_count, avg_score,
       fn_similarity(avg_score) AS avg_similarity
FROM top_documents
WHERE user_id = %s
ORDER BY search_count DESC, appearance_count DESC
LIMIT 10;
"""


def get_search_history(user_id: int, conn=None) -> list[dict]:
    """Retrieve search history ranked by frequency using SQL window functions (Slice 14).

    Runs the stored procedure sp_search_history (slice-33).

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
        rows = call_procedure(conn, "sp_search_history", user_id=user_id)
        return [
            {
                "query_text": str(row["query_text"]),
                "search_count": int(row["search_count"]),
                "query_rank": int(row["query_rank"]),
                "last_searched": to_utc_iso(row["last_searched"]),
                "total_searches": int(row["total_searches"]),
            }
            for row in rows
        ]
    finally:
        if should_close and conn:
            conn.close()


def get_unsearched_documents(user_id: int, conn=None) -> list[dict]:
    """Retrieve documents the user uploaded that never appeared in search results (Slice 15).

    Runs the stored procedure sp_unsearched_documents (a CTE query; slice-33).

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
        rows = call_procedure(conn, "sp_unsearched_documents", user_id=user_id)
        return [
            {
                "doc_id": int(row["doc_id"]),
                "title": str(row["title"]),
                "uploaded_at": to_utc_iso(row["uploaded_at"]),
            }
            for row in rows
        ]
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

        with logged_db_call("VIEW", f"top_documents read: user_id={user_id}") as call:
            cursor.execute(TOP_DOCUMENTS_QUERY, (user_id,))
            rows = cursor.fetchall()
            call.rows = len(rows)
        log_db_event(
            "FUNCTION",
            f"fn_similarity in the same top_documents query: {len(rows)} value{'' if len(rows) == 1 else 's'}",
        )
        cursor.close()

        results = []
        for row in rows:
            if isinstance(row, dict):
                doc_id = row["doc_id"]
                title = row["title"]
                search_count = row["search_count"]
                appearance_count = row["appearance_count"]
                avg_score_val = row.get("avg_score")
                avg_similarity_val = row.get("avg_similarity")
            else:
                # Columns as selected: (doc_id, title, search_count, appearance_count, avg_score, avg_similarity)
                doc_id, title, search_count, appearance_count, avg_score_val, avg_similarity_val = row[:6]

            results.append({
                "doc_id": int(doc_id),
                "title": str(title),
                "search_count": int(search_count),
                "appearance_count": int(appearance_count),
                "avg_score": float(avg_score_val) if avg_score_val is not None else None,
                "avg_similarity": float(avg_similarity_val) if avg_similarity_val is not None else None,
            })

        return results
    finally:
        if should_close and conn:
            conn.close()
