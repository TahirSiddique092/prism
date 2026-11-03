"""Slice 33: stored procedures for the analytics queries.

1. The migration runner splits a MySQL script into statements, running any
   number of DELIMITER blocks (triggers, procedures, functions) in order
2. Migration 008 creates sp_search_history and sp_unsearched_documents
3. The analytics module calls them with callproc and logs [DB] PROCEDURE lines

The integration test at the bottom is opt-in (PRISM_MYSQL_INTEGRATION=1 plus
MYSQL_URL). It only reads: for every user it compares each procedure with the
inline query it replaced.
"""
import datetime
import logging
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, call

import mysql.connector
import pytest

from backend.db.migrate import apply_mysql_script, split_mysql_script
from backend.modules.analytics.db import call_procedure, get_search_history, get_unsearched_documents

MIGRATIONS = Path(__file__).parent.parent / "db" / "migrations"


def _mysql_part(name):
    return (MIGRATIONS / name).read_text().split("-- ENGINE: ")[1][len("MySQL"):].strip()


# ============================================================================
# 1. Migration runner
# ============================================================================

def test_plain_statements_split_on_semicolons_and_comment_only_pieces_are_dropped():
    script = "-- a note\nCREATE TABLE a (x INT);\n-- only a comment;\nCREATE INDEX i ON a(x);\n"
    assert split_mysql_script(script) == [
        ("-- a note\nCREATE TABLE a (x INT)", False),
        ("CREATE INDEX i ON a(x)", False),
    ]


def test_trigger_in_001_is_the_same_statement_as_before():
    stmts = split_mysql_script(_mysql_part("001_init.sql"))
    trigger, in_block = stmts[-1]
    assert in_block is True
    assert trigger.startswith("CREATE TRIGGER before_document_delete")
    assert trigger.endswith("END;")
    # The 11 plain statements before it: 8 tables, 2 indexes, 1 view
    assert [b for _, b in stmts].count(False) == 11


def test_several_blocks_and_statements_after_a_block_all_run():
    script = (
        "CREATE TABLE t (x INT);\n"
        "DELIMITER //\nCREATE PROCEDURE p1() BEGIN SELECT 1; END //\nDELIMITER ;\n"
        "CREATE INDEX i ON t(x);\n"
        "DELIMITER //\nDROP FUNCTION IF EXISTS f //\nCREATE FUNCTION f() RETURNS INT DETERMINISTIC NO SQL RETURN 1 //\nDELIMITER ;\n"
    )
    assert split_mysql_script(script) == [
        ("CREATE TABLE t (x INT)", False),
        ("CREATE PROCEDURE p1() BEGIN SELECT 1; END", True),
        ("CREATE INDEX i ON t(x)", False),
        ("DROP FUNCTION IF EXISTS f", True),
        ("CREATE FUNCTION f() RETURNS INT DETERMINISTIC NO SQL RETURN 1", True),
    ]


def _mysql_error(errno):
    return mysql.connector.Error(msg="already exists", errno=errno)


def test_runner_tolerates_already_exists_only_where_expected():
    cursor = MagicMock()
    cursor.execute.side_effect = [_mysql_error(1050), _mysql_error(1304), None]
    apply_mysql_script(cursor, "CREATE TABLE t (x INT);\nDELIMITER //\nCREATE TRIGGER g BEFORE DELETE ON t FOR EACH ROW BEGIN END //\nDELIMITER ;\nSELECT 1;")
    assert cursor.execute.call_count == 3

    cursor = MagicMock()
    cursor.execute.side_effect = _mysql_error(1304)  # a plain statement must not swallow 1304
    with pytest.raises(mysql.connector.Error):
        apply_mysql_script(cursor, "CREATE TABLE t (x INT);")


def test_importing_the_runner_does_not_load_env():
    """Tests and scripts import migrate.py; only running it as a script reads .env."""
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[2]
    probe = (
        "import os, sys; sys.path.insert(0, '.'); before = set(os.environ); "
        "import backend.db.migrate; print(sorted(set(os.environ) - before))"
    )
    out = subprocess.run([sys.executable, "-I", "-c", probe], cwd=repo, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


# ============================================================================
# 2. Migration 008
# ============================================================================

def test_migration_008_creates_both_procedures_safely():
    stmts = split_mysql_script(_mysql_part("008_stored_procedures.sql"))
    assert [(s.splitlines()[-1] if s.startswith("DROP") else re.search(r"CREATE PROCEDURE (\w+)", s).group(1), b)
            for s, b in stmts] == [
        ("DROP PROCEDURE IF EXISTS sp_search_history", True),
        ("sp_search_history", True),
        ("DROP PROCEDURE IF EXISTS sp_unsearched_documents", True),
        ("sp_unsearched_documents", True),
    ]
    for sql, _ in stmts:
        if "CREATE PROCEDURE" in sql:
            assert "(IN p_user_id INT)" in sql
            assert "READS SQL DATA" in sql
            assert '"' not in sql  # Aiven runs with ANSI_QUOTES: strings need single quotes


# ============================================================================
# 3. Calling the procedures
# ============================================================================

def _proc_conn(columns, rows):
    conn = MagicMock()
    result = MagicMock()
    result.column_names = columns
    result.fetchall.return_value = rows
    conn.cursor.return_value.stored_results.return_value = [result]
    return conn


def test_call_procedure_returns_rows_by_column_name_and_logs(caplog):
    caplog.set_level(logging.INFO, logger="prism.db")
    conn = _proc_conn(("doc_id", "title"), [(4, "a.pdf"), (5, "b.pdf")])

    rows = call_procedure(conn, "sp_unsearched_documents", 9)

    cursor = conn.cursor.return_value
    assert cursor.mock_calls[:2] == [call.callproc("sp_unsearched_documents", (9,)), call.stored_results()]
    cursor.close.assert_called_once()
    assert rows == [{"doc_id": 4, "title": "a.pdf"}, {"doc_id": 5, "title": "b.pdf"}]
    (line,) = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[DB]")]
    assert re.fullmatch(r"\[DB\] PROCEDURE sp_unsearched_documents\(user_id=9\) → 2 rows in \d+ ms", line)


def test_stored_results_as_a_property_also_works():
    """Newer mysql-connector releases turn stored_results into a property."""
    class Result:
        column_names = ("doc_id",)

        def fetchall(self):
            return [(7,)]

    class Cursor:
        stored_results = [Result()]

        def callproc(self, name, args):
            pass

        def close(self):
            pass

    conn = MagicMock()
    conn.cursor.return_value = Cursor()
    assert call_procedure(conn, "sp_unsearched_documents", 1) == [{"doc_id": 7}]


def test_analytics_endpoints_use_the_procedures(caplog):
    caplog.set_level(logging.INFO, logger="prism.db")
    history_conn = _proc_conn(
        ("query_text", "search_count", "query_rank", "last_searched", "total_searches"),
        [("weak entity", 2, 1, datetime.datetime(2026, 11, 3, 9, 0), 2)],
    )
    unsearched_conn = _proc_conn(("doc_id", "title", "uploaded_at"), [])

    assert get_search_history(2, conn=history_conn)[0]["search_count"] == 2
    assert get_unsearched_documents(2, conn=unsearched_conn) == []

    history_conn.cursor.return_value.callproc.assert_called_once_with("sp_search_history", (2,))
    unsearched_conn.cursor.return_value.callproc.assert_called_once_with("sp_unsearched_documents", (2,))
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("[DB]")]
    assert [line.split(" → ")[0] for line in lines] == [
        "[DB] PROCEDURE sp_search_history(user_id=2)",
        "[DB] PROCEDURE sp_unsearched_documents(user_id=2)",
    ]
    assert "→ 0 rows" in lines[1]


# ============================================================================
# Integration (opt-in): real MySQL, read-only
# ============================================================================

integration = pytest.mark.skipif(
    os.getenv("PRISM_MYSQL_INTEGRATION") != "1" or not os.getenv("MYSQL_URL"),
    reason="set PRISM_MYSQL_INTEGRATION=1 and MYSQL_URL to run against a real MySQL server",
)

# The inline queries the procedures replaced, frozen to prove the output is unchanged.
OLD_SEARCH_HISTORY = """
SELECT query_text, COUNT(*) AS search_count, RANK() OVER (ORDER BY COUNT(*) DESC) AS query_rank,
       MAX(searched_at) AS last_searched, SUM(COUNT(*)) OVER () AS total_searches
FROM search_log WHERE user_id = %s GROUP BY query_text ORDER BY query_rank
"""
OLD_UNSEARCHED = """
WITH searched_docs AS (
    SELECT DISTINCT d.doc_id FROM search_results sr
    JOIN chunks c ON sr.chunk_id = c.chunk_id JOIN documents d ON c.doc_id = d.doc_id
    JOIN search_log sl ON sr.log_id = sl.log_id WHERE sl.user_id = %s
)
SELECT doc_id, title, uploaded_at FROM documents
WHERE user_id = %s AND status = 'ready' AND doc_id NOT IN (SELECT doc_id FROM searched_docs)
"""


@integration
def test_integration_procedures_exist_and_match_the_old_queries():
    from backend.modules.auth.db import get_db_config

    conn = mysql.connector.connect(**get_db_config())
    try:
        cur = conn.cursor()
        cur.execute("SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                    "WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE'")
        assert {"sp_search_history", "sp_unsearched_documents"} <= {r[0] for r in cur.fetchall()}

        cur.execute("SELECT user_id FROM users")
        user_ids = [r[0] for r in cur.fetchall()] + [-1]
        for uid in user_ids:
            cur.execute(OLD_SEARCH_HISTORY, (uid,))
            old_history = [dict(zip(cur.column_names, r)) for r in cur.fetchall()]
            assert call_procedure(conn, "sp_search_history", uid) == old_history

            cur.execute(OLD_UNSEARCHED, (uid, uid))
            old_unsearched = sorted((dict(zip(cur.column_names, r)) for r in cur.fetchall()), key=lambda d: d["doc_id"])
            new_unsearched = sorted(call_procedure(conn, "sp_unsearched_documents", uid), key=lambda d: d["doc_id"])
            assert new_unsearched == old_unsearched
        cur.close()
    finally:
        conn.close()
