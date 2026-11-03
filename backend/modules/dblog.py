"""One-line logs for the database objects the backend uses (slice-32).

Every line starts with "[DB]" and names the kind of object (TRIGGER,
PROCEDURE, FUNCTION or VIEW), so they can be followed during a demo with
`docker compose logs -f backend`:

    [DB] TRIGGER   before_document_delete fired: doc_id=12 → deletion_audit.audit_id=7 (cascade removed 43 chunks)
    [DB] VIEW      top_documents read: user_id=2 → 2 rows in 18 ms

Lines carry IDs, counts and timings only: never passwords, tokens, email
addresses, search text or document text.
"""
import logging
import time
import warnings
from contextlib import contextmanager

logger = logging.getLogger("prism.db")


def log_db_event(kind: str, description: str, level: int = logging.INFO) -> None:
    """Log one line: "[DB] KIND      description"."""
    logger.log(level, "[DB] %-9s %s", kind, description)


class _Call:
    rows = None
    result = None


@contextmanager
def logged_db_call(kind: str, description: str):
    """Time the block and log "<description> → N rows in M ms" when it ends.

    Set ``call.rows`` inside the block to report a row count, or
    ``call.result`` to report a single value ("<description> = 43 in M ms").
    Nothing is logged if the block raises.

        with logged_db_call("VIEW", f"top_documents read: user_id={user_id}") as call:
            rows = cursor.fetchall()
            call.rows = len(rows)
    """
    call = _Call()
    start = time.perf_counter()
    yield call
    elapsed_ms = round((time.perf_counter() - start) * 1000)
    if call.result is not None:
        outcome = f" = {call.result}"
    elif call.rows is not None:
        outcome = f" → {call.rows} row{'' if call.rows == 1 else 's'}"
    else:
        outcome = ""
    log_db_event(kind, f"{description}{outcome} in {elapsed_ms} ms")


def _stored_results(cursor):
    """The result sets of the last callproc.

    stored_results is a method in the mysql-connector releases we support and is
    becoming a property (calling the method now warns), so both forms work.
    """
    results = cursor.stored_results
    if callable(results):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            results = results()
    return results


def call_procedure(conn, name: str, **params) -> list[dict]:
    """CALL a stored procedure and return its rows as dicts (slice-33).

    ``params`` are passed in order as the procedure's arguments and shown in
    the [DB] PROCEDURE line, e.g. "sp_search_history(user_id=2)". Pass
    integers only: free text must go through a prepared statement (ADR-017).
    """
    args = ", ".join(f"{key}={value}" for key, value in params.items())
    cursor = conn.cursor()
    with logged_db_call("PROCEDURE", f"{name}({args})") as call:
        cursor.callproc(name, tuple(params.values()))
        rows = []
        for result in _stored_results(cursor):
            columns = result.column_names
            rows.extend(dict(zip(columns, row)) for row in result.fetchall())
        call.rows = len(rows)
    cursor.close()
    return rows
