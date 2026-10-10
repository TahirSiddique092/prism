"""Database operations for the analytics module using raw SQL with mysql-connector-python.

As per project guidelines (AGENTS.md):
- No ORMs (no SQLAlchemy, no abstractions)
- Explicit, visible SQL queries
- Raw SQL via mysql-connector-python
"""
import logging

try:
    from backend.modules.auth.db import get_db_connection
except ImportError:
    from modules.auth.db import get_db_connection

logger = logging.getLogger(__name__)

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

            if hasattr(last_searched_val, "isoformat"):
                last_searched_str = last_searched_val.isoformat()
            else:
                last_searched_str = str(last_searched_val) if last_searched_val is not None else None

            results.append({
                "query_text": str(query_text),
                "search_count": int(search_count),
                "query_rank": int(query_rank),
                "last_searched": last_searched_str,
                "total_searches": int(total_searches),
            })

        return results
    finally:
        if should_close and conn:
            conn.close()
