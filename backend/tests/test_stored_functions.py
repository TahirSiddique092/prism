"""Slice 34: stored functions fn_chunk_count and fn_similarity.

1. Migration 009 creates both, each declaring its characteristic
2. The document list and detail count chunks with fn_chunk_count
3. Top Documents returns avg_similarity from fn_similarity
4. Each use logs a [DB] FUNCTION line

The integration test at the bottom is opt-in (PRISM_MYSQL_INTEGRATION=1 plus
MYSQL_URL) and only reads.
"""
import logging
import os
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.db.migrate import split_mysql_script
from backend.modules.analytics.db import TOP_DOCUMENTS_QUERY, get_top_documents
from backend.modules.dblog import logged_db_call
from backend.modules.documents.db import get_document_chunk_count, get_user_documents

MIGRATION_009 = Path(__file__).parent.parent / "db" / "migrations" / "009_stored_functions.sql"


@pytest.fixture
def db_lines(caplog):
    caplog.set_level(logging.INFO, logger="prism.db")
    return lambda: [r.getMessage() for r in caplog.records if r.getMessage().startswith("[DB]")]


# ============================================================================
# 1. Migration 009
# ============================================================================

def test_migration_009_creates_both_functions_safely():
    script = MIGRATION_009.read_text().split("-- ENGINE: ")[1][len("MySQL"):].strip()
    stmts = split_mysql_script(script)
    assert [b for _, b in stmts] == [True] * 4
    assert stmts[0][0] == "DROP FUNCTION IF EXISTS fn_chunk_count"
    assert stmts[2][0] == "DROP FUNCTION IF EXISTS fn_similarity"

    chunk_count, similarity = stmts[1][0], stmts[3][0]
    assert "CREATE FUNCTION fn_chunk_count(p_doc_id INT)" in chunk_count
    assert "RETURNS INT" in chunk_count and "READS SQL DATA" in chunk_count
    assert "CREATE FUNCTION fn_similarity(p_distance DOUBLE)" in similarity
    assert "DETERMINISTIC" in similarity and "NO SQL" in similarity
    assert "RETURN 1 - p_distance" in similarity
    for sql, _ in stmts:
        assert '"' not in sql  # ANSI_QUOTES: strings need single quotes


# ============================================================================
# 2. fn_chunk_count
# ============================================================================

def test_document_list_counts_chunks_with_the_function(db_lines):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = [
        {"doc_id": 3, "title": "a.pdf", "uploaded_at": None, "status": "ready", "chunk_count": 26},
        {"doc_id": 4, "title": "b.pdf", "uploaded_at": None, "status": "processing", "chunk_count": 0},
    ]

    docs = get_user_documents(2, conn=conn)

    sql, params = cursor.execute.call_args.args
    assert "fn_chunk_count(d.doc_id) AS chunk_count" in sql
    assert "LEFT JOIN" not in sql and "GROUP BY" not in sql
    assert params == (2,)
    assert [d["chunk_count"] for d in docs] == [26, 0]
    (line,) = db_lines()
    assert re.fullmatch(r"\[DB\] FUNCTION  fn_chunk_count in the document list: user_id=2 → 2 rows in \d+ ms", line)


def test_document_detail_calls_the_function_and_logs_its_value(db_lines):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (43,)

    assert get_document_chunk_count(4, conn=conn) == 43

    cursor.execute.assert_called_once_with("SELECT fn_chunk_count(%s)", (4,))
    (line,) = db_lines()
    assert re.fullmatch(r"\[DB\] FUNCTION  fn_chunk_count\(doc_id=4\) = 43 in \d+ ms", line)


def test_a_logged_value_of_zero_is_still_shown(db_lines):
    with logged_db_call("FUNCTION", "fn_chunk_count(doc_id=9)") as call:
        call.result = 0
    (line,) = db_lines()
    assert re.fullmatch(r"\[DB\] FUNCTION  fn_chunk_count\(doc_id=9\) = 0 in \d+ ms", line)


# ============================================================================
# 3. fn_similarity
# ============================================================================

def test_top_documents_returns_similarity_from_the_function(db_lines):
    assert "fn_similarity(avg_score) AS avg_similarity" in TOP_DOCUMENTS_QUERY
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [
        {"doc_id": 2, "title": "er-model.pdf", "search_count": 3, "appearance_count": 25,
         "avg_score": 0.4634, "avg_similarity": 0.5366},
        {"doc_id": 5, "title": "fulltext-only.pdf", "search_count": 1, "appearance_count": 1,
         "avg_score": None, "avg_similarity": None},
    ]

    docs = get_top_documents(2, conn=conn)

    assert [d["avg_similarity"] for d in docs] == [0.5366, None]
    assert db_lines()[-1] == "[DB] FUNCTION  fn_similarity in the same top_documents query: 2 values"


# ============================================================================
# Integration (opt-in): real MySQL, read-only
# ============================================================================

integration = pytest.mark.skipif(
    os.getenv("PRISM_MYSQL_INTEGRATION") != "1" or not os.getenv("MYSQL_URL"),
    reason="set PRISM_MYSQL_INTEGRATION=1 and MYSQL_URL to run against a real MySQL server",
)

# The document-list query fn_chunk_count replaced, frozen to prove counts are unchanged.
OLD_DOCUMENT_LIST = """
SELECT d.doc_id, COUNT(c.chunk_id) AS chunk_count
FROM documents d LEFT JOIN chunks c ON d.doc_id = c.doc_id
WHERE d.user_id = %s GROUP BY d.doc_id
"""


@integration
def test_integration_functions_exist_and_give_the_same_answers():
    import mysql.connector

    from backend.modules.auth.db import get_db_config

    conn = mysql.connector.connect(**get_db_config())
    try:
        cur = conn.cursor()
        cur.execute("SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                    "WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'FUNCTION'")
        assert {"fn_chunk_count", "fn_similarity"} <= {r[0] for r in cur.fetchall()}

        cur.execute("SELECT fn_similarity(0.4634), fn_similarity(NULL), fn_chunk_count(-1)")
        similarity, null_similarity, no_chunks = cur.fetchone()
        assert round(similarity, 4) == 0.5366
        assert null_similarity is None
        assert no_chunks == 0

        cur.execute("SELECT user_id FROM users")
        for (uid,) in cur.fetchall():
            cur.execute(OLD_DOCUMENT_LIST, (uid,))
            old_counts = dict(cur.fetchall())
            new_counts = {d["doc_id"]: d["chunk_count"] for d in get_user_documents(uid, conn=conn)}
            assert new_counts == old_counts
        cur.close()
    finally:
        conn.close()
