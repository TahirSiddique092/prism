"""Database operations for the admin module (slice-35), raw SQL via mysql-connector-python.

The user list and the system totals come from the stored procedures
sp_admin_user_overview and sp_admin_system_stats (migrations/010_user_roles.sql).
The deletion log is a plain query on deletion_audit, the table the
before_document_delete trigger writes.

Admins see account details and counts only: never a password hash, search
text or document text.
"""
try:
    from backend.modules.auth.db import get_db_connection
    from backend.modules.timeutils import to_utc_iso
    from backend.modules.dblog import call_procedure, log_db_event, logged_db_call
except ImportError:
    from modules.auth.db import get_db_connection
    from modules.timeutils import to_utc_iso
    from modules.dblog import call_procedure, log_db_event, logged_db_call

DELETION_LOG_LIMIT = 50

DELETION_LOG_QUERY = """
SELECT audit_id, doc_id, title, user_id, deleted_at
FROM deletion_audit
ORDER BY deleted_at DESC, audit_id DESC
LIMIT %s;
"""


def get_user_overview(conn=None) -> list[dict]:
    """Every user with their document, chunk and search counts.

    Runs sp_admin_user_overview, which calls fn_user_document_count,
    fn_user_search_count and fn_chunk_count for each user.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        rows = call_procedure(conn, "sp_admin_user_overview")
        log_db_event(
            "FUNCTION",
            "fn_user_document_count, fn_user_search_count and fn_chunk_count "
            f"inside sp_admin_user_overview: {len(rows)} user{'' if len(rows) == 1 else 's'}",
        )
        return [
            {
                "user_id": int(row["user_id"]),
                "name": str(row["name"]),
                "email": str(row["email"]),
                "role": str(row["role"]),
                "created_at": to_utc_iso(row["created_at"]),
                "documents": int(row["documents"]),
                "chunks": int(row["chunks"]),
                "searches": int(row["searches"]),
                "last_search_at": to_utc_iso(row["last_search_at"]),
            }
            for row in rows
        ]
    finally:
        if should_close and conn:
            conn.close()


STAT_FIELDS = (
    "users",
    "admins",
    "documents",
    "documents_processing",
    "documents_ready",
    "documents_error",
    "chunks",
    "searches",
    "searches_today",
    "deletions",
)


def get_system_stats(conn=None) -> dict:
    """System-wide totals from sp_admin_system_stats, as one dict of integers."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        rows = call_procedure(conn, "sp_admin_system_stats")
        row = rows[0] if rows else {}
        return {field: int(row.get(field) or 0) for field in STAT_FIELDS}
    finally:
        if should_close and conn:
            conn.close()


def get_deletion_log(conn=None) -> list[dict]:
    """The latest deletion_audit rows written by the before_document_delete trigger."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        with logged_db_call("TRIGGER", "deletion_audit read (rows written by before_document_delete)") as call:
            cursor.execute(DELETION_LOG_QUERY, (DELETION_LOG_LIMIT,))
            rows = cursor.fetchall()
            call.rows = len(rows)
        cursor.close()
        return [
            {
                "audit_id": int(audit_id),
                "doc_id": int(doc_id),
                "title": title,
                "user_id": int(user_id) if user_id is not None else None,
                "deleted_at": to_utc_iso(deleted_at),
            }
            for audit_id, doc_id, title, user_id, deleted_at in rows
        ]
    finally:
        if should_close and conn:
            conn.close()
