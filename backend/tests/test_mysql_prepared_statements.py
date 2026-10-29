"""Regression tests: free-text MySQL queries use prepared statements (ADR-017).

mysql-connector-python inlines plain-cursor parameters into the SQL string and
then runs its client-side script splitter over the whole statement whenever it
finds "delimiter <something>" in it, including inside the data. DBMS notes
with trigger examples ("DELIMITER //") therefore broke chunk inserts with
error 1064, and a search like "what's the delimiter in codd's rules" was
silently stored as "what's the;\\ncodd's rules". Prepared statements send the
values separately from the SQL, so the splitter never sees them.

The unit tests below check every free-text query uses a prepared cursor. The
integration tests reproduce the original failure against a real MySQL server;
they only run when PRISM_MYSQL_INTEGRATION=1 and MYSQL_URL are set, and write
only to TEMPORARY tables that shadow the real ones for that one connection.
"""
import os
from unittest.mock import MagicMock

import pytest

from backend.modules.auth.db import create_user, find_user_by_email, get_db_config
from backend.modules.documents.db import (
    CHUNK_INSERT_BATCH,
    insert_chunks,
    insert_document,
    insert_document_topics,
)
from backend.modules.search.db import insert_search_log, search_chunks_fulltext

# Text that broke the old code paths: a trigger example with DELIMITER lines,
# SQL comments, apostrophes and non-ASCII characters.
TRIGGER_NOTES = (
    "Code:\nDELIMITER //\nCREATE TRIGGER CheckMarks\nBEFORE INSERT ON Marks_sample\n"
    "FOR EACH ROW BEGIN -- reject bad marks\nIF NEW.marks > 100 THEN\n"
    "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid marks: Marks must be between 0 and 100';\n"
    "END IF;\nEND;//\nDELIMITER ;\n# Triggers - How it works"
)
HIERARCHY_NOTES = "●A typical example of hierarchical data is a table that includes a list of employees — it's Codd's 😀"
DELIMITER_QUERY = "what's the delimiter in codd's rules"


def _mock_conn(row=None, column_names=(), lastrowid=None):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = row
    cursor.column_names = column_names
    cursor.lastrowid = lastrowid
    return conn, cursor


# ============================================================================
# Unit tests: every free-text query goes through a prepared cursor
# ============================================================================

def test_find_user_by_email_uses_prepared_cursor_and_returns_dict():
    columns = ("user_id", "name", "email", "password_hash", "created_at")
    conn, cursor = _mock_conn(row=(7, "Ada", "ada@example.com", "$2b$hash", None), column_names=columns)

    user = find_user_by_email("ada@example.com", conn=conn)

    conn.cursor.assert_called_once_with(prepared=True)
    assert cursor.execute.call_args.args[1] == ("ada@example.com",)
    assert user == {
        "user_id": 7, "name": "Ada", "email": "ada@example.com",
        "password_hash": "$2b$hash", "created_at": None,
    }


def test_find_user_by_email_returns_none_when_missing():
    conn, _ = _mock_conn(row=None)
    assert find_user_by_email("nobody@example.com", conn=conn) is None


def test_create_user_uses_prepared_cursor():
    conn, cursor = _mock_conn(lastrowid=12)
    assert create_user("O'Brien", "ob@example.com", "$2b$hash", conn=conn) == 12
    conn.cursor.assert_called_once_with(prepared=True)
    assert cursor.execute.call_args.args[1] == ("O'Brien", "ob@example.com", "$2b$hash")


def test_insert_document_uses_prepared_cursor():
    conn, cursor = _mock_conn(lastrowid=5)
    assert insert_document(1, "dbms notes.pdf", "1/x.pdf", conn=conn) == 5
    conn.cursor.assert_called_once_with(prepared=True)
    assert cursor.execute.call_args.args[1] == (1, "dbms notes.pdf", "1/x.pdf")


def test_insert_chunks_sends_one_prepared_multi_row_insert():
    conn, cursor = _mock_conn()

    insert_chunks(3, [TRIGGER_NOTES, HIERARCHY_NOTES], conn=conn)

    conn.cursor.assert_called_once_with(prepared=True)
    cursor.executemany.assert_not_called()
    sql, params = cursor.execute.call_args.args
    assert sql == (
        "INSERT INTO chunks (doc_id, chunk_text, chunk_index, page_start, page_end) "
        "VALUES (%s, %s, %s, %s, %s), (%s, %s, %s, %s, %s)"
    )
    # The text is a parameter, never part of the SQL string
    assert "DELIMITER" not in sql
    # No pages given: stored as NULL (slice-27)
    assert params == [3, TRIGGER_NOTES, 0, None, None, 3, HIERARCHY_NOTES, 1, None, None]
    conn.commit.assert_called_once()


def test_insert_chunks_stores_pages_with_each_chunk():
    conn, cursor = _mock_conn()

    insert_chunks(3, [TRIGGER_NOTES, HIERARCHY_NOTES], conn=conn, pages=[(4, 5), (5, 5)])

    _, params = cursor.execute.call_args.args
    assert params == [3, TRIGGER_NOTES, 0, 4, 5, 3, HIERARCHY_NOTES, 1, 5, 5]


def test_insert_chunks_batches_large_documents_and_keeps_indexes():
    conn, cursor = _mock_conn()
    total = CHUNK_INSERT_BATCH * 2 + 7
    chunks = [f"chunk {i}" for i in range(total)]

    insert_chunks(9, chunks, conn=conn)

    calls = cursor.execute.call_args_list
    assert [len(c.args[1]) // 5 for c in calls] == [CHUNK_INSERT_BATCH, CHUNK_INSERT_BATCH, 7]
    indexes = [v for c in calls for v in c.args[1][2::5]]
    assert indexes == list(range(total))
    texts = [v for c in calls for v in c.args[1][1::5]]
    assert texts == chunks
    conn.commit.assert_called_once()


def test_insert_chunks_empty_list_does_nothing():
    conn, _ = _mock_conn()
    insert_chunks(1, [], conn=conn)
    conn.cursor.assert_not_called()


def test_insert_document_topics_uses_prepared_cursor():
    conn, cursor = _mock_conn()
    insert_document_topics(4, ["delimiter in sql"], conn=conn)
    conn.cursor.assert_called_once_with(prepared=True)
    cursor.executemany.assert_not_called()


def test_insert_search_log_uses_prepared_cursor():
    conn, cursor = _mock_conn(lastrowid=31)
    assert insert_search_log(2, DELIMITER_QUERY, conn=conn) == 31
    conn.cursor.assert_called_once_with(prepared=True)
    assert cursor.execute.call_args.args[1] == (2, DELIMITER_QUERY)


def test_search_chunks_fulltext_uses_prepared_cursor():
    conn, cursor = _mock_conn()
    cursor.fetchall.return_value = [(15, 6, "Guide.pdf", "Snippet text")]

    results = search_chunks_fulltext(user_id=2, query=DELIMITER_QUERY, limit=5, conn=conn)

    conn.cursor.assert_called_once_with(prepared=True)
    assert cursor.execute.call_args.args[1] == (2, DELIMITER_QUERY, 5)
    assert results[0]["chunk_id"] == 15


# ============================================================================
# Integration tests against a real MySQL server (opt-in)
# ============================================================================

integration = pytest.mark.skipif(
    os.getenv("PRISM_MYSQL_INTEGRATION") != "1" or not os.getenv("MYSQL_URL"),
    reason="set PRISM_MYSQL_INTEGRATION=1 and MYSQL_URL to run against a real MySQL server",
)

# TEMPORARY tables shadow the real tables of the same name for this connection
# only, so nothing is written to the real schema. InnoDB temporary tables cannot
# carry FULLTEXT indexes (and managed servers may disable MyISAM), so the
# FULLTEXT query is checked read-only against the real table instead.
SHADOW_TABLES = [
    "CREATE TEMPORARY TABLE users (user_id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255) NOT NULL,"
    " email VARCHAR(255) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL,"
    " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TEMPORARY TABLE documents (doc_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,"
    " title VARCHAR(255) NOT NULL, minio_key VARCHAR(255) NOT NULL,"
    " uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status VARCHAR(50) DEFAULT 'processing')",
    "CREATE TEMPORARY TABLE chunks (chunk_id INT AUTO_INCREMENT PRIMARY KEY, doc_id INT NOT NULL,"
    " chunk_text TEXT NOT NULL, chunk_index INT NOT NULL, page_start INT NULL, page_end INT NULL)",
    "CREATE TEMPORARY TABLE topics (topic_id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255) NOT NULL UNIQUE)",
    "CREATE TEMPORARY TABLE doc_topics (doc_id INT NOT NULL, topic_id INT NOT NULL, PRIMARY KEY (doc_id, topic_id))",
    "CREATE TEMPORARY TABLE search_log (log_id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL,"
    " query_text TEXT NOT NULL, searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
]


@pytest.fixture
def shadow_conn():
    import mysql.connector

    conn = mysql.connector.connect(**get_db_config())
    cursor = conn.cursor()
    for ddl in SHADOW_TABLES:
        cursor.execute(ddl)
    cursor.close()
    try:
        yield conn
    finally:
        conn.close()  # TEMPORARY tables are dropped with the session


def _fetch(conn, sql, params=()):
    cursor = conn.cursor(prepared=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


@integration
def test_integration_chunks_with_delimiter_text_round_trip(shadow_conn):
    chunks = ["Relational model basics; keys and -- comments", TRIGGER_NOTES, HIERARCHY_NOTES]
    insert_chunks(1, chunks, conn=shadow_conn)

    rows = _fetch(shadow_conn, "SELECT chunk_index, chunk_text FROM chunks ORDER BY chunk_index")
    assert [(i, t) for i, t in rows] == list(enumerate(chunks))


@integration
def test_integration_search_log_stores_query_unchanged(shadow_conn):
    log_id = insert_search_log(1, DELIMITER_QUERY, conn=shadow_conn)

    rows = _fetch(shadow_conn, "SELECT query_text FROM search_log WHERE log_id = %s", (log_id,))
    assert rows == [(DELIMITER_QUERY,)]


@integration
def test_integration_user_round_trip(shadow_conn):
    name = "O'Brien, delimiter in chief"
    user_id = create_user(name, "obrien@example.com", "$2b$hash", conn=shadow_conn)

    user = find_user_by_email("obrien@example.com", conn=shadow_conn)
    assert user["user_id"] == user_id
    assert user["name"] == name


@integration
def test_integration_document_and_topics_round_trip(shadow_conn):
    doc_id = insert_document(1, "dbms_unit2.pdf", "1/u2.pdf", conn=shadow_conn)
    insert_document_topics(doc_id, ["triggers", "delimiter in sql"], conn=shadow_conn)

    names = _fetch(
        shadow_conn,
        "SELECT t.name FROM doc_topics dt JOIN topics t ON dt.topic_id = t.topic_id WHERE dt.doc_id = %s ORDER BY t.name",
        (doc_id,),
    )
    assert [n for (n,) in names] == ["delimiter in sql", "triggers"]


@integration
def test_integration_fulltext_query_runs_as_prepared_statement():
    """Read-only: MATCH ... AGAINST(?) is accepted as a prepared statement.

    Runs against the real chunks table (it has the FULLTEXT index) for a user
    id that cannot exist, so it returns no rows and writes nothing.
    """
    import mysql.connector

    conn = mysql.connector.connect(**get_db_config())
    try:
        assert search_chunks_fulltext(user_id=-1, query=DELIMITER_QUERY, limit=5, conn=conn) == []
    finally:
        conn.close()
